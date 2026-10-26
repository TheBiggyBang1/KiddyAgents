"""Channel settings and the series bible, loaded from config/channel.yaml."""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Character(BaseModel):
    id: str
    name: str
    species: str
    look: str  # copied word for word into every image prompt, so the character stays on-model
    personality: str
    voice: str


class ModelChoice(BaseModel):
    """The chat model one agent uses. Extra keys (temperature, max_tokens...) go to the model."""

    model_config = ConfigDict(extra="allow")

    model: str  # an init_chat_model string, e.g. "groq:llama-3.3-70b-versatile"

    def options(self) -> dict:
        return dict(self.model_extra or {})


class VideoFormat(BaseModel):
    width: int = 1920
    height: int = 1080
    fps: int = 30


class Providers(BaseModel):
    images: str = "fake"
    tts: str = "fake"


class EdgeVoiceSettings(BaseModel):
    rate: str = "-8%"  # a touch slower than normal, for young listeners
    pitch: str = "+0Hz"


class TracingSettings(BaseModel):
    picture_style: str = (
        "cute flat children's book illustration, bold clean outlines, bright friendly colors"
    )
    practice_seconds: float = 4.0  # quiet time for kids to trace along with a finger


class GroqVoiceSettings(BaseModel):
    model: str = "canopylabs/orpheus-v1-english"
    requests_per_minute: float = 9  # the free tier allows 10


class CloudflareSettings(BaseModel):
    model: str = "@cf/black-forest-labs/flux-2-klein-4b"  # takes up to 4 reference images
    render_size: tuple[int, int] = (1024, 576)  # upscaled to the video size; bigger costs more


class YouTubeSettings(BaseModel):
    upload: bool = False  # True: approving a video uploads it
    publish_times: list[str] = Field(default_factory=lambda: ["16:00"])  # this PC's clock
    captions: bool = True  # 400 of the 10,000 daily quota units
    playlists: dict[str, str] = Field(default_factory=dict)  # format -> playlist title


class Settings(BaseModel):
    channel_name: str
    concept: str = ""  # the stem idea every episode grows from
    curriculum: list[str] = Field(default_factory=list)  # subject areas the showrunner rotates
    puppet_minutes: tuple[float, float] = (2, 3)
    tracing_every: int = 4  # about one tracing video per this many episodes
    audience_age: str
    language: str = "en"
    format: str
    video_minutes: tuple[int, int] = (3, 5)
    video: VideoFormat = Field(default_factory=VideoFormat)
    art_style: str
    publish_mode: Literal["human_approval", "auto_private", "auto_scheduled"] = "human_approval"
    llm: dict[str, ModelChoice]
    providers: Providers = Field(default_factory=Providers)
    cloudflare: CloudflareSettings = Field(default_factory=CloudflareSettings)
    groq_voices: GroqVoiceSettings = Field(default_factory=GroqVoiceSettings)
    edge_voices: EdgeVoiceSettings = Field(default_factory=EdgeVoiceSettings)
    tracing: TracingSettings = Field(default_factory=TracingSettings)
    vision_check: bool = True  # a vision model looks at every picture before it's used
    youtube: YouTubeSettings = Field(default_factory=YouTubeSettings)
    narrator_voice: str
    characters: list[Character]

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def model_for(self, agent: str) -> ModelChoice:
        return self.llm.get(agent) or self.llm["default"]

    def character(self, ref: str) -> Character | None:
        """Find a character by id or by name, ignoring case: models mix the two up."""
        key = ref.strip().lower()
        return next((c for c in self.characters if key in (c.id, c.name.lower())), None)

    def voice_for(self, speaker: str) -> str:
        found = self.character(speaker)
        return found.voice if found else self.narrator_voice
