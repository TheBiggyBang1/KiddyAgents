"""Publisher: uploads to YouTube. Milestone 1 only marks the episode ready; Milestone 5 uploads."""

from langgraph.runtime import Runtime

from kiddy.state import EpisodeState
from kiddy.studio import RunContext, get_studio


def publisher(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    get_studio(runtime).store.update(
        state["episode_id"], status="ready", tokens_used=state.get("tokens_used", 0)
    )
    return {"status": "ready"}
