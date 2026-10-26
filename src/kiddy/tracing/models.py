"""What the tracing agents hand to each other, and the stroke library they draw from."""

import json
import operator
from functools import cache
from pathlib import Path
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from kiddy.state import QAReport, YouTubeMetadata


class Stroke(BaseModel):
    d: str  # SVG path on the letter grid (see letters.json)
    say: str  # what the narrator says while it's drawn


@cache
def library() -> dict[str, list[Stroke]]:
    raw = json.loads((Path(__file__).parent / "letters.json").read_text(encoding="utf-8"))
    return {char: [Stroke(**s) for s in strokes] for char, strokes in raw.items()
            if not char.startswith("_")}


class WordIdea(BaseModel):
    word: str = Field(description="One concrete, drawable noun, e.g. Apple")
    sentence: str = Field(description="One short, cheerful sentence about it, at most 8 words")
    picture: str = Field(
        description="What to draw: the object alone, simply, e.g. 'a shiny red apple with a leaf'"
    )


class LetterPlan(BaseModel):
    words: list[WordIdea] = Field(description="Exactly 3 different words")


class WordPicture(BaseModel):
    index: int
    path: str
    flagged: str | None = None  # why the vision check is still unhappy after every redraw


class VoiceLine(BaseModel):
    key: str
    text: str
    path: str
    duration_s: float


class TracingState(TypedDict, total=False):
    episode_id: str
    letter: str  # the uppercase letter this video teaches
    status: str
    plan: LetterPlan
    pictures: Annotated[list[WordPicture], operator.add]  # last entry per word wins
    lines: list[VoiceLine]
    props_path: str
    video_path: str
    thumbnail_path: str
    metadata: YouTubeMetadata
    qa: QAReport
    tokens_used: Annotated[int, operator.add]
    youtube: dict  # what the publisher put on YouTube (kiddy.youtube.Progress)


class PictureJob(TypedDict):
    """One painter task, handed over with Send."""

    episode_id: str
    index: int
    idea: WordIdea


TRACING_TYPES = (Stroke, WordIdea, LetterPlan, WordPicture, VoiceLine)
