"""Scriptwriter: turns the brief into scenes, and revises them when the reviewer asks."""

from langgraph.runtime import Runtime

from kiddy.prompts import as_yaml, system_prompt
from kiddy.providers.llm import BadModelOutput
from kiddy.settings import Settings
from kiddy.state import Brief, EpisodeState, Script
from kiddy.store import save_json
from kiddy.studio import RunContext, get_studio

WORDS_PER_MINUTE = 110  # spoken words per minute of video: unhurried, for young kids
WORDS_PER_SCENE = 40  # about 20 seconds of speech under one picture


def scriptwriter(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    cfg = studio.settings
    brief = state["brief"]
    request = {
        "brief": brief.model_dump(),
        "audience_age": cfg.audience_age,
        "characters": [
            c.model_dump(include={"id", "name", "species", "look", "personality"})
            for c in cfg.characters
            if c.id in brief.characters
        ],
        "length_plan": length_plan(word_budget(brief)),
    }
    notes = revision_notes(state)
    if notes and "script" in state:
        request["previous_draft"] = state["script"].model_dump()
        request["revision_notes"] = notes
    script, tokens = studio.llm.structured(
        "scriptwriter", Script, system_prompt("scriptwriter"), as_yaml(request)
    )
    script = tidy(script, cfg)

    save_json(studio.episode_dir(state["episode_id"]) / "script.json", script)
    studio.store.update(state["episode_id"], title=script.title)
    return {
        "script": script,
        "script_attempts": state.get("script_attempts", 0) + 1,
        "tokens_used": tokens,
    }


def word_budget(brief: Brief) -> int:
    return round(brief.target_minutes * WORDS_PER_MINUTE)


def length_plan(budget: int) -> dict:
    """Models miss word totals but follow a per-scene plan, so the budget is split up front."""
    scenes = min(max(round(budget / WORDS_PER_SCENE), 8), 20)
    return {"total_words": budget, "scenes": scenes, "words_per_scene": round(budget / scenes)}


def short_scenes(script: Script, budget: int) -> list[str]:
    """Per-scene notes for a draft that came out short: the totals alone don't get it fixed."""
    target = length_plan(budget)["words_per_scene"]
    return [
        f"Scene {scene.id} has {words} spoken words; give it about {target}."
        for scene in script.scenes
        if (words := sum(len(line.text.split()) for line in scene.lines)) < target * 0.7
    ]


def revision_notes(state: EpisodeState) -> list[str]:
    """What the writer must fix: everything the last review found, plus any human notes."""
    notes = []
    review = state.get("review")
    if review:
        notes += [f"Hard fail: {rule}" for rule in review.hard_fails]
        notes += [
            f"Wrong fact ({check.verdict}): {check.claim} True version: {check.correction}"
            for check in review.wrong_facts
        ]
        notes += [
            f"Scene {issue.scene_id}: {issue.problem} Fix: {issue.fix}"
            if issue.scene_id
            else f"{issue.problem} Fix: {issue.fix}"
            for issue in review.issues
        ]
        if "script" in state and "brief" in state:
            notes += short_scenes(state["script"], word_budget(state["brief"]))
    return notes + state.get("feedback", [])


def tidy(script: Script, cfg: Settings) -> Script:
    """Make model output safe to build on: known speakers and characters, scenes numbered 1..N."""
    scenes = []
    for scene in script.scenes:
        lines = [line for line in scene.lines if line.text.strip()]
        if not lines:
            continue
        for line in lines:
            found = cfg.character(line.speaker)
            line.speaker = found.id if found else "narrator"
        visible = [found.id for ref in scene.characters if (found := cfg.character(ref))]
        scenes.append(scene.model_copy(update={
            "id": len(scenes) + 1, "lines": lines, "characters": list(dict.fromkeys(visible)),
        }))
    if not scenes:
        raise BadModelOutput("the script has no scenes with spoken lines")
    return script.model_copy(update={"scenes": scenes})
