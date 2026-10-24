"""Narrator: voices one scene per Send task, line by line, each in its speaker's voice."""

from pathlib import Path

from langgraph.runtime import Runtime

from kiddy.media import audio
from kiddy.state import Line, SceneAudio, SceneJob, Timing
from kiddy.store import write_once
from kiddy.studio import RunContext, Studio, get_studio

LINE_GAP = 0.35  # seconds of quiet between two lines


def narrator(job: SceneJob, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    scene = job["scene"]
    folder = studio.episode_dir(job["episode_id"]) / "audio"
    # One file per line: voices differ per speaker, and a crash only costs the unfinished lines.
    parts = [
        voice_line(studio, folder / "lines" / f"scene_{scene.id:02d}_{number:02d}.wav", line)
        for number, line in enumerate(scene.lines, 1)
    ]
    out = write_once(
        folder / f"scene_{scene.id:02d}.wav", lambda part: audio.join(parts, part, gap=LINE_GAP)
    )
    return {"audio": [SceneAudio(
        scene_id=scene.id, path=str(out), duration_s=audio.duration(out),
        sentences=timings(scene.lines, parts),
    )]}


def voice_line(studio: Studio, out: Path, line: Line) -> Path:
    voice = studio.settings.voice_for(line.speaker)
    return write_once(out, lambda part: studio.tts.speak(line.text, voice, line.emotion, part))


def timings(lines: list[Line], parts: list[Path]) -> list[Timing]:
    """Caption timings for the whole scene, in seconds from its start."""
    result, clock = [], 0.0
    for line, part in zip(lines, parts, strict=True):
        seconds = audio.duration(part)
        result += audio.sentence_timings(line.text, clock, seconds)
        clock += seconds + LINE_GAP
    return result
