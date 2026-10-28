"""Picture makers: a fake for offline runs, and FLUX on Cloudflare Workers AI's free tier."""

import base64
import io
import os
import textwrap
from pathlib import Path
from typing import Protocol

import httpx
from PIL import Image, ImageDraw, ImageFont

from kiddy.settings import Settings

PASTELS = [(255, 223, 186), (255, 250, 200), (210, 245, 210), (200, 235, 250), (225, 215, 250)]
INK = (70, 60, 90)
REFERENCE_MAX = 496  # FLUX.2 wants reference images smaller than 512x512
TIMEOUT = 90  # seconds: a picture takes 15-30 s; on busy days some requests hang, so give up
TRIES = 5  # ...and send it again, which usually answers at once


class ImageProvider(Protocol):
    def generate(
        self, prompt: str, refs: list[Path], size: tuple[int, int], out: Path, seed: int = 0
    ) -> Path:
        """Paint `prompt` into `out` at `size` pixels, keeping the `refs` characters on-model."""
        ...


class ImageServiceError(RuntimeError):
    """The image service refused the request (bad input, or the daily free tier is used up).
    A RuntimeError, so LangGraph doesn't retry it: trying again wouldn't help."""


class FakeImages:
    """A pastel card with the scene name and prompt, so a fake video shows which scene is which."""

    def generate(
        self, prompt: str, refs: list[Path], size: tuple[int, int], out: Path, seed: int = 0
    ) -> Path:
        width, height = size
        name = out.name.split(".")[0]  # "scene_03" from "scene_03.part.png"
        card = Image.new("RGB", size, PASTELS[sum(map(ord, name)) % len(PASTELS)])
        draw = ImageDraw.Draw(card)
        margin = width // 16
        title_font = ImageFont.load_default(size=height // 9)
        draw.text((margin, height // 10), name.replace("_", " ").title(), fill=INK, font=title_font)
        body = "\n".join(textwrap.wrap(prompt, width=60)[:10])
        body_font = ImageFont.load_default(size=height // 24)
        draw.multiline_text(
            (margin, height // 3), body, fill=INK, font=body_font, spacing=height // 80
        )
        card.save(out, format="PNG")
        return out


class CloudflareImages:
    """FLUX on Workers AI. Free tier: 10,000 neurons a day, about 170 pictures at 1024x576."""

    def __init__(
        self, model: str, render_size: tuple[int, int], client: httpx.Client | None = None
    ):
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        token = os.environ.get("CLOUDFLARE_API_TOKEN")
        if not (account and token):
            raise ValueError("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env")
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
        self.render_size = render_size
        self.client = client or httpx.Client(
            headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT
        )

    def generate(
        self, prompt: str, refs: list[Path], size: tuple[int, int], out: Path, seed: int = 0
    ) -> Path:
        # Small pictures (reference sheets) render as asked; video frames render small and are
        # upscaled, which the soft watercolor style hides well.
        width, height = size if size[0] <= self.render_size[0] else self.render_size
        fields: dict = {
            "prompt": (None, prompt[:2048]),
            "width": (None, str(width)),
            "height": (None, str(height)),
            "seed": (None, str(seed)),
        }
        for index, ref in enumerate(refs[:4]):
            fields[f"input_image_{index}"] = (ref.name, reference_png(ref), "image/png")
        response = self._post(fields)
        if response.status_code >= 500:
            response.raise_for_status()  # LangGraph's RetryPolicy retries 5xx errors
        body = response.json()
        if not body.get("success"):
            raise ImageServiceError(f"Cloudflare refused the picture: {body.get('errors')}")
        with Image.open(io.BytesIO(base64.b64decode(body["result"]["image"]))) as picture:
            picture.convert("RGB").resize(size, Image.Resampling.LANCZOS).save(out, format="PNG")
        return out

    def _post(self, fields: dict) -> httpx.Response:
        for _ in range(TRIES):
            try:
                return self.client.post(self.url, files=fields)
            except httpx.TimeoutException:
                continue
        raise ImageServiceError(f"Cloudflare didn't answer {TRIES} times in a row: it's busy. "
                                "Try again later; finished pictures are kept.")


def reference_png(path: Path) -> bytes:
    with Image.open(path) as picture:
        small = picture.convert("RGB")
        small.thumbnail((REFERENCE_MAX, REFERENCE_MAX))
        buffer = io.BytesIO()
        small.save(buffer, format="PNG")
        return buffer.getvalue()


def make_image_provider(name: str, settings: Settings) -> ImageProvider:
    if name == "fake":
        return FakeImages()
    if name == "cloudflare":
        return CloudflareImages(settings.cloudflare.model, settings.cloudflare.render_size)
    raise ValueError(f"Unknown image provider {name!r}: use 'fake' or 'cloudflare'")
