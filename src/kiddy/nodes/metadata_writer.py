"""Metadata writer: title, description and tags for YouTube.

Milestone 1 builds them straight from the script. Milestone 4 has a model write them, with chapters.
"""

from langgraph.runtime import Runtime

from kiddy.state import EpisodeState, YouTubeMetadata
from kiddy.store import save_json
from kiddy.studio import RunContext, get_studio


def metadata_writer(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    script, brief = state["script"], state["brief"]
    metadata = YouTubeMetadata(
        title=script.title[:100],
        description=f"{script.logline}\n\nToday we learn: {script.learning_goal}",
        tags=list(dict.fromkeys([brief.topic, brief.format, "kids", "learning", "story"])),
        chapters=[],
        default_language=studio.settings.language,
    )
    save_json(studio.episode_dir(state["episode_id"]) / "metadata.json", metadata)
    return {"metadata": metadata}
