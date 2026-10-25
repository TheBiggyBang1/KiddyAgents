"""Language models behind one small interface, so agents never care which provider answers."""

import base64
import io
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.rate_limiters import InMemoryRateLimiter
from PIL import Image
from pydantic import BaseModel

from kiddy.providers import fixtures
from kiddy.settings import Settings


class BadModelOutput(Exception):
    """The model kept answering in the wrong shape. LangGraph's RetryPolicy retries these."""


class LLM(Protocol):
    def structured[T: BaseModel](
        self, agent: str, schema: type[T], system: str, user: str, images: Sequence[Path] = ()
    ) -> tuple[T, int]:
        """Ask `agent`'s model for a `schema` object; return it with the tokens spent."""
        ...


class ChatLLM:
    """Real models through init_chat_model, one per agent as set in config/channel.yaml."""

    def __init__(self, settings: Settings, attempts: int = 2):
        self.settings = settings
        self.attempts = attempts
        self._limiters: dict[str, InMemoryRateLimiter] = {}
        self._lock = threading.Lock()

    def _limiter(self, agent: str, per_minute: float) -> InMemoryRateLimiter:
        """One limiter per agent, shared by every parallel task, so they queue instead of 429."""
        with self._lock:
            if agent not in self._limiters:
                self._limiters[agent] = InMemoryRateLimiter(
                    requests_per_second=per_minute / 60, check_every_n_seconds=0.5
                )
            return self._limiters[agent]

    def structured[T: BaseModel](
        self, agent: str, schema: type[T], system: str, user: str, images: Sequence[Path] = ()
    ) -> tuple[T, int]:
        choice = self.settings.model_for(agent)
        options = choice.options()
        output = {"method": options.pop("structured_output", "function_calling")}
        if "strict" in options:  # lock the answer to the schema (Groq: gpt-oss models only)
            output["strict"] = options.pop("strict")
        if "requests_per_minute" in options:
            options["rate_limiter"] = self._limiter(agent, options.pop("requests_per_minute"))
        # The Groq client retries 429s itself and honors retry-after; free tiers hit them often.
        options.setdefault("max_retries", 6)
        model = init_chat_model(choice.model, **options)
        runnable = model.with_structured_output(schema, include_raw=True, **output)
        tokens, prompt = 0, user
        for _ in range(self.attempts):
            try:
                out = runnable.invoke([SystemMessage(system), human_message(prompt, images)])
            except Exception as error:
                # Groq answers 400 (tool_use_failed) when the model garbles its own answer.
                if getattr(error, "status_code", None) != 400:
                    raise
                out = {"raw": None, "parsed": None, "parsing_error": "the answer was garbled"}
            tokens += (getattr(out["raw"], "usage_metadata", None) or {}).get("total_tokens", 0)
            if out["parsed"] is not None:
                return out["parsed"], tokens
            problem = out["parsing_error"] or "no structured answer"
            prompt = (
                f"{user}\n\nYour last answer did not fit the required format ({problem}). "
                "Answer again and fill in every field."
            )
        raise BadModelOutput(f"{agent}: no valid {schema.__name__} after {self.attempts} tries")


def human_message(text: str, images: Sequence[Path]) -> HumanMessage:
    if not images:
        return HumanMessage(text)
    return HumanMessage([
        {"type": "text", "text": text},
        *({"type": "image_url", "image_url": {"url": jpeg_data_uri(path)}} for path in images),
    ])


def jpeg_data_uri(path: Path, longest_side: int = 1024) -> str:
    """Shrink a picture before sending it: the model sees no more detail, the upload is smaller."""
    with Image.open(path) as picture:
        small = picture.convert("RGB")
        small.thumbnail((longest_side, longest_side))
        buffer = io.BytesIO()
        small.save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


class FakeLLM:
    """Canned answers, so `kiddy run --fake` and the tests work offline."""

    def structured[T: BaseModel](
        self, agent: str, schema: type[T], system: str, user: str, images: Sequence[Path] = ()
    ) -> tuple[T, int]:
        return fixtures.answer(schema, user), 0


def make_llm(settings: Settings, fake: bool) -> LLM:
    return FakeLLM() if fake else ChatLLM(settings)
