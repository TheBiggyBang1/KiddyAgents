"""WAV helpers on the standard library: the bundled FFmpeg has no ffprobe, and WAV needs none."""

import re
import wave
from pathlib import Path

from kiddy.state import Timing

SAMPLE_RATE = 24_000
SAMPLE_WIDTH = 2  # bytes: 16-bit
CHANNELS = 1


def write_silence(out: Path, seconds: float) -> Path:
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(int(seconds * SAMPLE_RATE) * SAMPLE_WIDTH * CHANNELS))
    return out


def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def join(parts: list[Path], out: Path, gap: float) -> Path:
    """Concatenate same-format WAVs with `gap` seconds of silence between them."""
    with wave.open(str(parts[0]), "rb") as first:
        params = first.getparams()
    pause = bytes(int(gap * params.framerate) * params.sampwidth * params.nchannels)
    with wave.open(str(out), "wb") as joined:
        joined.setparams(params)
        for index, part in enumerate(parts):
            if index:
                joined.writeframes(pause)
            with wave.open(str(part), "rb") as wav:
                joined.writeframes(wav.readframes(wav.getnframes()))
    return out


def place(parts: list[tuple[Path, float]], seconds: float, out: Path) -> Path:
    """A `seconds`-long track of silence with each same-format WAV dropped in at its offset."""
    with wave.open(str(parts[0][0]), "rb") as first:
        params = first.getparams()
    frame = params.sampwidth * params.nchannels
    track = bytearray(int(seconds * params.framerate) * frame)
    for path, offset in parts:
        with wave.open(str(path), "rb") as wav:
            sound = wav.readframes(wav.getnframes())
        start = int(offset * params.framerate) * frame
        sound = sound[: max(len(track) - start, 0)]
        track[start: start + len(sound)] = sound
    with wave.open(str(out), "wb") as placed:
        placed.setparams(params)
        placed.writeframes(bytes(track))
    return out


def sentence_timings(text: str, start: float, seconds: float) -> list[Timing]:
    """Spread a line's duration over its sentences by length: close enough for captions."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s] or [text]
    total = sum(len(s) for s in sentences) or 1
    timings, clock = [], start
    for sentence in sentences:
        length = seconds * len(sentence) / total
        timings.append(Timing(text=sentence, start=round(clock, 3), end=round(clock + length, 3)))
        clock += length
    return timings
