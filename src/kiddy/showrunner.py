"""The showrunner: invents the next episode from the channel's stem idea, with no prompt from you.

It sees every episode made so far, which letters are done, and your rejection notes, so it keeps
varying subjects and formats and never runs out of ideas when a series (like A-Z) ends.
"""

import string

from kiddy.prompts import as_yaml, system_prompt
from kiddy.providers.llm import BadModelOutput
from kiddy.puppet.models import EpisodeIdea
from kiddy.store import UPLOADED
from kiddy.studio import Studio


def letters_done(history: list[dict]) -> set[str]:
    # "ready": videos made before approvals existed
    made = ("approved", "awaiting_approval", "ready", *UPLOADED)
    return {row["topic"][-1] for row in history
            if row["format"] == "tracing" and row["status"] in made
            and (row["topic"] or "").startswith("letter ")}


def next_idea(studio: Studio, attempts: int = 2) -> tuple[EpisodeIdea, int]:
    cfg = studio.settings
    history = studio.store.recent(80)
    done = letters_done(history)
    request = {
        "stem_idea": cfg.concept,
        "audience_age": cfg.audience_age,
        "subjects": cfg.curriculum,
        "characters": [c.model_dump(include={"id", "name", "species", "personality"})
                       for c in cfg.characters],
        "formats": {
            "puppet": "the characters act out a short story that teaches the learning goal",
            "tracing": "an alphabet tracing video for one letter (A-Z)",
        },
        "tracing_rule": f"about one tracing video every {cfg.tracing_every} episodes, "
                        "and none if the last one was tracing",
        "letters_done": sorted(done) or "none yet",
        "past_episodes": [
            {"format": row["format"], "subject": row["subject"], "topic": row["topic"],
             "status": row["status"]}
            for row in history if row["topic"]
        ] or "none yet",
        "your_rejection_notes": [row["notes"] for row in history if row["notes"]] or "none",
    }
    tokens, taken = 0, {(row["topic"] or "").strip().lower() for row in history}
    for _ in range(attempts):
        idea, spent = studio.llm.structured(
            "episode_planner", EpisodeIdea, system_prompt("episode_planner"), as_yaml(request)
        )
        tokens += spent
        if idea.format == "tracing":
            letter = (idea.letter or "").strip().upper()[:1]
            if letter not in string.ascii_uppercase or letter in done:
                letter = next((c for c in string.ascii_uppercase if c not in done), "")
            if not letter:  # every letter is done: tracing is retired, a story instead
                request["formats"].pop("tracing", None)
                continue
            idea = idea.model_copy(update={"letter": letter, "topic": f"letter {letter}"})
        if idea.topic.strip().lower() not in taken:
            return idea, tokens
        request["avoid_repeating"] = idea.topic
    raise BadModelOutput("the showrunner kept proposing episodes that were already made")
