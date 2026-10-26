"""What the puppet-show agents hand to each other. Literal lists match video/src/puppet/types.ts."""

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from kiddy.state import QAReport, Review, YouTubeMetadata

Emotion = Literal["happy", "excited", "curious", "surprised", "sad", "calm"]
Action = Literal["wave", "jump", "nod", "point", "dance", "think", "clap", "spin"]
Place = Literal["left", "center", "right"]
Background = Literal["meadow", "forest", "pond", "night", "garden", "home"]
Format = Literal["puppet", "tracing"]


class EpisodeIdea(BaseModel):
    """The showrunner's pick for the next episode, made from the channel's stem idea alone."""

    format: Format
    subject: str = Field(description="The curriculum area it belongs to, from the list")
    topic: str = Field(description="What the episode is about, in a few words")
    learning_goal: str = Field(description="One short sentence a four-year-old could say back")
    letter: str | None = Field(description="Tracing only: the letter to teach. Null otherwise")
    why: str = Field(description="One sentence: why this is a good next episode")


# Beats have no defaults: strict structured output needs every field present (null when unused).
class Beat(BaseModel):
    kind: Literal["say", "act", "move", "card", "word"]
    character: str | None = Field(description="Character id. Needed for say, act and move")
    text: str | None = Field(
        description="say: the spoken line, at most 14 words. word: one word or number shown big"
    )
    emotion: Emotion | None = Field(description="say: how the line feels")
    action: Action | None = Field(description="act: what the character does")
    to: Place | None = Field(description="move: where the character walks to")
    card: str | None = Field(
        description="card: the picture shown on the easel, e.g. 'a toothbrush with blue bristles'"
    )


class PuppetScene(BaseModel):
    background: Background
    cast: list[str] = Field(description="1 to 3 character ids on stage, from left to right")
    beats: list[Beat]


class PuppetScript(BaseModel):
    title: str
    learning_goal: str
    fact_claims: list[str] = Field(description="The learning goal and every factual statement")
    scenes: list[PuppetScene]

    def spoken_words(self) -> int:
        return sum(len((b.text or "").split()) for s in self.scenes for b in s.beats
                   if b.kind == "say")


class SpokenLine(BaseModel):
    key: str  # "s2_b5": scene 2, beat 5
    character: str
    text: str
    path: str
    duration_s: float
    mouth: list[float]  # how open the mouth is on each frame


class CardPicture(BaseModel):
    index: int
    description: str
    path: str
    flagged: str | None = None


class PuppetState(TypedDict, total=False):
    episode_id: str
    idea: EpisodeIdea
    status: str
    script: PuppetScript
    review: Review
    script_attempts: int
    cards: Annotated[list[CardPicture], operator.add]  # last entry per card wins
    lines: list[SpokenLine]
    props_path: str
    video_path: str
    thumbnail_path: str
    metadata: YouTubeMetadata
    qa: QAReport
    feedback: Annotated[list[str], operator.add]
    tokens_used: Annotated[int, operator.add]
    youtube: dict  # what the publisher put on YouTube (kiddy.youtube.Progress)


class CardJob(TypedDict):
    """One card-painter task, handed over with Send."""

    episode_id: str
    index: int
    description: str


PUPPET_TYPES = (EpisodeIdea, Beat, PuppetScene, PuppetScript, SpokenLine, CardPicture)
