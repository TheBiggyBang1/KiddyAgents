"""Human approval: you watch the episode before it goes anywhere.

Milestone 1 approves on its own, because nothing is uploaded yet. Milestone 4 makes this an
interrupt() that waits for `kiddy approve` or `kiddy reject`.
"""

from kiddy.state import EpisodeState


def human_approval(state: EpisodeState) -> dict:
    return {"status": "approved"}
