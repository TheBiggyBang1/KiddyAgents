"""Everything a run needs besides the state: settings, providers and folders."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from langgraph.runtime import Runtime

from kiddy.providers.images import ImageProvider, make_image_provider
from kiddy.providers.llm import LLM, make_llm
from kiddy.providers.tts import TTSProvider, make_tts_provider
from kiddy.settings import Settings
from kiddy.store import EpisodeStore


@dataclass(frozen=True)
class RunContext:
    """Passed as graph.invoke(..., context=...). Plain values, so LangGraph Studio can show it."""

    fake: bool = False  # fake every model and provider: offline and free
    config_path: str = "config/channel.yaml"
    output_dir: str = "output"
    data_dir: str = "data"
    assets_dir: str = "assets"


@dataclass(frozen=True)
class Studio:
    settings: Settings
    llm: LLM
    images: ImageProvider
    tts: TTSProvider
    store: EpisodeStore
    output_dir: Path
    assets_dir: Path  # character reference sheets live here, shared by every episode

    def episode_dir(self, episode_id: str) -> Path:
        folder = self.output_dir / "episodes" / episode_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder


@cache
def studio_for(ctx: RunContext) -> Studio:
    settings = Settings.load(Path(ctx.config_path))
    return Studio(
        settings=settings,
        llm=make_llm(settings, fake=ctx.fake),
        images=make_image_provider("fake" if ctx.fake else settings.providers.images, settings),
        tts=make_tts_provider("fake" if ctx.fake else settings.providers.tts, settings),
        store=EpisodeStore(Path(ctx.data_dir) / "kiddy.sqlite"),
        output_dir=Path(ctx.output_dir),
        # Fake reference cards must never land among the real reference sheets.
        assets_dir=Path(ctx.output_dir) / "fake-assets" if ctx.fake else Path(ctx.assets_dir),
    )


def get_studio(runtime: Runtime[RunContext]) -> Studio:
    return studio_for(runtime.context or RunContext())
