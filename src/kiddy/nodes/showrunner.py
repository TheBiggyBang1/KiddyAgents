"""Showrunner: picks the next episode, never repeating an old one."""

from langgraph.runtime import Runtime

from kiddy.prompts import as_yaml, system_prompt
from kiddy.state import Brief, EpisodeState
from kiddy.store import save_json
from kiddy.studio import RunContext, get_studio


def showrunner(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    cfg = studio.settings
    past = [
        {"topic": row["topic"], "format": row["format"]}
        for row in studio.store.recent(50)
        if row["topic"] and row["id"] != state["episode_id"]
    ]
    request = {
        "channel": {
            "name": cfg.channel_name,
            "audience_age": cfg.audience_age,
            "format": cfg.format,
            "video_minutes": list(cfg.video_minutes),
        },
        "characters": [
            c.model_dump(include={"id", "name", "species", "personality"}) for c in cfg.characters
        ],
        "past_episodes": past or "none yet",
        "requested_topic": state.get("topic") or "none: you choose",
    }
    brief, tokens = studio.llm.structured(
        "showrunner", Brief, system_prompt("showrunner"), as_yaml(request)
    )
    cast = [found.id for ref in brief.characters if (found := cfg.character(ref))]
    brief.characters = list(dict.fromkeys(cast)) or [cfg.characters[0].id]
    shortest, longest = cfg.video_minutes
    brief.target_minutes = min(max(brief.target_minutes, shortest), longest)

    save_json(studio.episode_dir(state["episode_id"]) / "brief.json", brief)
    studio.store.update(
        state["episode_id"], topic=brief.topic, format=brief.format,
        learning_goal=brief.learning_goal, status="writing",
    )
    return {"brief": brief, "status": "writing", "tokens_used": tokens}
