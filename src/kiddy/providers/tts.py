"""Voices: a fake for offline runs, Microsoft Edge's free voices, and Orpheus on Groq.

Every provider writes 24 kHz mono 16-bit WAV, so lines can be joined without re-encoding.
"""

import os
import re
import time
from pathlib import Path
from typing import Protocol

import edge_tts
import httpx
from langchain_core.rate_limiters import InMemoryRateLimiter

from kiddy.media import audio, ffmpeg
from kiddy.settings import Settings

WORDS_PER_SECOND = 2.0  # about 120 words a minute: an unhurried pace for young kids


class TTSProvider(Protocol):
    def speak(self, text: str, voice: str, emotion: str, out: Path) -> Path:
        """Say `text` in `voice`, colored by `emotion`, into the WAV file `out`."""
        ...


class VoiceServiceError(RuntimeError):
    """The voice service refused (terms not accepted, daily free limit used up...).
    A RuntimeError, so LangGraph doesn't retry it: trying again wouldn't help."""


class FakeTTS:
    """Silence as long as the line would take to say, so timing and captions still work."""

    def speak(self, text: str, voice: str, emotion: str, out: Path) -> Path:
        return audio.write_silence(out, max(1.0, len(text.split()) / WORDS_PER_SECOND))


class EdgeVoices:
    """Microsoft Edge's online neural voices: free and no key, but an unofficial endpoint."""

    def __init__(self, rate: str, pitch: str):
        self.rate, self.pitch = rate, pitch

    def speak(self, text: str, voice: str, emotion: str, out: Path) -> Path:
        mp3 = out.with_suffix(".mp3")
        edge_tts.Communicate(text, voice, rate=self.rate, pitch=self.pitch).save_sync(str(mp3))
        ffmpeg.run(ffmpeg.voice_wav_args(mp3, out))  # the shared 24 kHz mono WAV format
        mp3.unlink()
        return out


class GroqVoices:
    """Orpheus on Groq. Free tier: 10 requests a minute, 100 a day, 200 characters a request."""

    URL = "https://api.groq.com/openai/v1/audio/speech"
    MAX_CHARS = 200
    LONGEST_WAIT = 90  # seconds: a longer retry-after means today's free limit is used up
    CHUNK_GAP = 0.15  # pause between the pieces of a line that was too long for one request

    def __init__(self, model: str, requests_per_minute: float, client: httpx.Client | None = None):
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise ValueError("Set GROQ_API_KEY in .env")
        self.model = model
        self.client = client or httpx.Client(
            headers={"Authorization": f"Bearer {key}"}, timeout=120
        )
        # One limiter for the whole run: parallel narrator tasks queue instead of hitting 429s.
        self.limiter = InMemoryRateLimiter(
            requests_per_second=requests_per_minute / 60, check_every_n_seconds=0.25
        )
        self.sleep = time.sleep  # how a 429's retry-after is waited out (tests swap it)

    def speak(self, text: str, voice: str, emotion: str, out: Path) -> Path:
        direction = f"[{emotion}] " if emotion else ""  # Orpheus reads [warm], [excited]...
        pieces = []
        for number, chunk in enumerate(chunks(text, self.MAX_CHARS - len(direction))):
            raw = out.with_name(f"{out.stem}.{number}.raw.wav")
            raw.write_bytes(self._request(direction + chunk, voice))
            piece = out.with_name(f"{out.stem}.{number}.wav")
            ffmpeg.run(ffmpeg.voice_wav_args(raw, piece))  # whatever Groq sends, 24 kHz mono
            raw.unlink()
            pieces.append(piece)
        audio.join(pieces, out, gap=self.CHUNK_GAP)
        for piece in pieces:
            piece.unlink()
        return out

    def _request(self, text: str, voice: str) -> bytes:
        for _ in range(6):
            self.limiter.acquire()
            response = self.client.post(self.URL, json={
                "model": self.model, "input": text, "voice": voice, "response_format": "wav",
            })
            if response.status_code == 200:
                return response.content
            if response.status_code == 429:
                wait = float(response.headers.get("retry-after", 10))
                if wait > self.LONGEST_WAIT:
                    raise VoiceServiceError(
                        f"Groq's free voice limit is used up for now (resets in about "
                        f"{wait / 3600:.1f} h). Continue later with `kiddy resume`."
                    )
                self.sleep(wait)
                continue
            if response.status_code >= 500:
                response.raise_for_status()  # LangGraph's RetryPolicy retries 5xx errors
            raise VoiceServiceError(f"Groq refused the voice: {error_message(response)}")
        raise VoiceServiceError("Groq kept rate-limiting the voices; try again in a minute")


def chunks(text: str, limit: int) -> list[str]:
    """Split text into pieces of at most `limit` characters, at sentence breaks when possible."""
    pieces: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        for part in split_long(sentence, limit):
            if pieces and len(pieces[-1]) + 1 + len(part) <= limit:
                pieces[-1] += " " + part
            else:
                pieces.append(part)
    return [piece for piece in pieces if piece]


def split_long(sentence: str, limit: int) -> list[str]:
    parts, current = [], ""
    for word in sentence.split():
        if current and len(current) + 1 + len(word) > limit:
            parts.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return [*parts, current]


def error_message(response: httpx.Response) -> str:
    try:
        return response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return f"HTTP {response.status_code}: {response.text[:300]}"


def make_tts_provider(name: str, settings: Settings) -> TTSProvider:
    if name == "fake":
        return FakeTTS()
    if name == "edge":
        return EdgeVoices(settings.edge_voices.rate, settings.edge_voices.pitch)
    if name == "groq":
        return GroqVoices(settings.groq_voices.model, settings.groq_voices.requests_per_minute)
    raise ValueError(f"Unknown voice provider {name!r}: use 'fake', 'edge' or 'groq'")
