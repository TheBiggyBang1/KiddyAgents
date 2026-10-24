"""Escalate: where an automatic loop gives up and a human decides.

Milestone 1 stops the run and leaves the reason on disk (review.json). Milestone 4 turns this
into an interrupt() that waits for your answer.
"""

from langgraph.runtime import Runtime

from kiddy.state import EpisodeState
from kiddy.studio import RunContext, get_studio


def escalate(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    get_studio(runtime).store.update(
        state["episode_id"], status="needs_human", tokens_used=state.get("tokens_used", 0)
    )
    return {"status": "needs_human"}
