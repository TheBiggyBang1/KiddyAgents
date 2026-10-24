"""What the agents hand to each other: typed pieces plus the shared graph state."""

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field, computed_field


class Brief(BaseModel):
    """The showrunner's pick for one episode."""

    topic: str = Field(description="What the episode is about, in a few words")
    angle: str = Field(description="The fresh way into the topic for this episode")
    learning_goal: str = Field(description="One short sentence a five-year-old could say back")
    format: str = Field(description='"story", "rhyme", "why-question" or "counting-game"')
    mood: str = Field(description="The overall feeling, e.g. cozy, playful, curious")
    characters: list[str] = Field(description="Ids of the characters in this episode")
    target_minutes: float = Field(description="Planned video length in minutes")


class Line(BaseModel):
    speaker: str = Field(description='"narrator" or a character id')
    text: str
    # No default: strict structured output needs every field required.
    emotion: str = Field(description="One or two words: warm, excited, curious...")


class Scene(BaseModel):
    id: int
    lines: list[Line] = Field(description="Narration and dialogue, in speaking order")
    visual: str = Field(
        description="ONE still picture: who, where, doing what, mood and light. No words in it."
    )
    characters: list[str] = Field(description="Ids of the characters visible in the picture")
    target_seconds: float


class Script(BaseModel):
    title: str
    logline: str
    learning_goal: str
    fact_claims: list[str] = Field(description="Every factual statement the script makes")
    scenes: list[Scene]

    def spoken_words(self) -> int:
        return sum(len(line.text.split()) for scene in self.scenes for line in scene.lines)


class Scores(BaseModel):
    age_fit: int = Field(ge=1, le=5, description="Words, pace and sentence length suit the age")
    clarity: int = Field(ge=1, le=5, description="The story is easy to follow")
    warmth: int = Field(ge=1, le=5, description="Kind, gentle and encouraging")
    learning_value: int = Field(ge=1, le=5, description="The learning goal is taught and recapped")
    drawability: int = Field(ge=1, le=5, description="Every visual works as one still picture")
    originality: int = Field(ge=1, le=5, description="Fresh, not a copy of something that exists")

    def average(self) -> float:
        values = list(self.model_dump().values())
        return sum(values) / len(values)


# The review models give no defaults: Groq's strict mode needs every field required (LangChain
# adds the no-extra-keys rule itself), and then the reviewer's answer is locked to this shape.
class Issue(BaseModel):
    scene_id: int | None = Field(
        description="The scene with the problem; null if it is the whole script"
    )
    problem: str
    fix: str = Field(description="A concrete change that solves the problem")


class FactCheck(BaseModel):
    claim: str
    verdict: Literal["true", "wrong", "misleading"] = Field(
        description='"misleading" when a child would learn something false, e.g. a wrong cause'
    )
    correction: str = Field(description="A true kid-level version; empty if the claim is true")


class Review(BaseModel):
    """The safety reviewer's verdict. `passed` is computed here, never taken from the model."""

    # Listed first, so the model checks every fact before it scores anything.
    fact_checks: list[FactCheck] = Field(
        description="The learning goal and every fact claim, each checked on its own"
    )
    hard_fails: list[str] = Field(
        description="Each hard-fail rule the script breaks; empty if none"
    )
    scores: Scores
    issues: list[Issue] = Field(description="Every problem, each with a concrete fix")

    @property
    def wrong_facts(self) -> list[FactCheck]:
        return [check for check in self.fact_checks if check.verdict != "true"]

    @computed_field
    @property
    def passed(self) -> bool:
        return not self.hard_fails and not self.wrong_facts and self.scores.average() >= 4


class ScenePrompt(BaseModel):
    scene_id: int
    prompt: str
    references: list[str] = []  # character reference sheets, in the order the prompt names them


class ArtPlan(BaseModel):
    style: str
    prompts: list[ScenePrompt]


class VisionCheck(BaseModel):
    """A vision model's look at one picture. `passed` is computed, never taken from the model."""

    matches_scene: bool = Field(description="The picture shows what the scene describes")
    characters_on_model: bool = Field(
        description="Every character matches its description: species, colors, clothing"
    )
    has_text: bool = Field(description="Letters, words, numbers, signs or logos appear anywhere")
    unsettling: bool = Field(
        description="Anything scary or broken: distorted faces, extra or missing limbs, melting"
    )
    problems: list[str] = Field(description="One short fix per problem; empty if it's fine")

    @computed_field
    @property
    def passed(self) -> bool:
        return (self.matches_scene and self.characters_on_model
                and not self.has_text and not self.unsettling)


class SceneImage(BaseModel):
    scene_id: int
    path: str
    flagged: str | None = None  # why the vision check is still unhappy after every redraw


class Timing(BaseModel):
    text: str
    start: float
    end: float


class SceneAudio(BaseModel):
    scene_id: int
    path: str
    duration_s: float
    sentences: list[Timing]  # seconds from the start of the scene


class Chapter(BaseModel):
    start_s: float
    title: str


class YouTubeMetadata(BaseModel):
    title: str
    description: str
    tags: list[str]
    chapters: list[Chapter]
    category_id: str = "27"  # Education
    default_language: str = "en"


class Check(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class QAReport(BaseModel):
    checks: list[Check]

    @computed_field
    @property
    def passed(self) -> bool:
        return all(check.ok for check in self.checks)


class EpisodeState(TypedDict, total=False):
    episode_id: str
    topic: str  # optional request from the command line
    status: str
    brief: Brief
    script: Script
    review: Review
    script_attempts: int
    art_plan: ArtPlan
    images: Annotated[list[SceneImage], operator.add]  # last entry per scene wins
    audio: Annotated[list[SceneAudio], operator.add]  # last entry per scene wins
    video_path: str
    captions_path: str
    thumbnail_path: str
    metadata: YouTubeMetadata
    qa: QAReport
    feedback: Annotated[list[str], operator.add]  # reviewer and human notes
    tokens_used: Annotated[int, operator.add]
    youtube_video_id: str


class SceneJob(TypedDict):
    """One illustrator or narrator task, handed over with Send."""

    episode_id: str
    scene: Scene
    prompt: str  # the image prompt; empty for the narrator
    references: list[str]  # character reference sheets for the illustrator


def latest_by_scene[T: SceneImage | SceneAudio](items: list[T]) -> dict[int, T]:
    """Fan-in lists only grow, so a redone scene shows up twice: keep the newest."""
    return {item.scene_id: item for item in items}


# The only classes a checkpoint may rebuild when a run resumes (plus LangGraph's own).
CHECKPOINT_TYPES = (
    Brief, Line, Scene, Script, Scores, Issue, FactCheck, Review, ScenePrompt, ArtPlan,
    SceneImage, Timing, SceneAudio, Chapter, YouTubeMetadata, Check, QAReport,
)
