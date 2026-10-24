"""FFmpeg command builders (pure functions, unit-tested) and a small runner."""

import json
import re
import shutil
import subprocess
from functools import cache
from pathlib import Path

import imageio_ffmpeg

LOUDNESS = "I=-14:TP=-1:LRA=11"  # YouTube plays everything at about -14 LUFS
MUSIC_VOLUME = 0.22  # the bed under the voices, before ducking
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]

# Gentle Ken Burns moves: zoom (z) and the top-left corner (x, y) over the clip's frames.
CENTER = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
MOVES = {
    "in": f"z='1+0.10*on/{{n}}':{CENTER}",
    "out": f"z='1.10-0.10*on/{{n}}':{CENTER}",
    "right": "z='1.10':x='(iw-iw/zoom)*on/{n}':y='ih/2-(ih/zoom/2)'",
    "left": "z='1.10':x='(iw-iw/zoom)*(1-on/{n})':y='ih/2-(ih/zoom/2)'",
}


@cache
def ffmpeg_exe() -> str:
    """FFmpeg from PATH if it's installed, else the copy bundled with imageio-ffmpeg."""
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def motion_clip_args(
    image: Path, seconds: float, out: Path, width: int, height: int, fps: int, move: str
) -> list[str]:
    """One scene's picture with a slow camera move, `seconds` long, no sound."""
    frames = round(seconds * fps)
    # Upscaling first keeps zoompan's whole-pixel steps from making the picture jitter.
    motion = (
        f"scale={width * 2}:{height * 2},"
        f"zoompan={MOVES[move].format(n=frames)}:d={frames}:s={width}x{height}:fps={fps}"
    )
    return ["-y", "-i", str(image), "-vf", motion, "-frames:v", str(frames), *X264, "-an", str(out)]


def crossfade_args(clips: list[Path], starts: list[float], fade: float, out: Path) -> list[str]:
    """Join clips with a crossfade; clip k fades in at `starts[k]` seconds."""
    if len(clips) == 1:
        return ["-y", "-i", str(clips[0]), "-c", "copy", str(out)]
    inputs = [arg for clip in clips for arg in ("-i", str(clip))]
    chain, last = [], "0:v"
    for k in range(1, len(clips)):
        chain.append(
            f"[{last}][{k}:v]xfade=transition=fade:duration={fade}:offset={starts[k]:.3f}[v{k}]"
        )
        last = f"v{k}"
    return ["-y", *inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", *X264, str(out)]


def voice_wav_args(src: Path, out: Path) -> list[str]:
    """Any audio in, the voice format every provider promises out: 24 kHz mono 16-bit WAV."""
    return ["-y", "-i", str(src), "-ar", "24000", "-ac", "1", "-sample_fmt", "s16", str(out)]


def mix_args(narration: Path, music: Path | None, seconds: float, out: Path) -> list[str]:
    """Voices plus an optional looped music bed that ducks whenever someone speaks."""
    if music is None:
        return ["-y", "-i", str(narration), "-ar", "48000", "-ac", "2", str(out)]
    stereo = "aresample=48000,aformat=channel_layouts=stereo"
    graph = ";".join([
        f"[0:a]{stereo},asplit=2[voice][key]",
        f"[1:a]{stereo},volume={MUSIC_VOLUME},afade=t=in:d=2,"
        f"afade=t=out:st={max(seconds - 3, 0):.3f}:d=3[bed]",
        "[bed][key]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[ducked]",
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0[mix]",
    ])
    return [
        "-y", "-i", str(narration), "-stream_loop", "-1", "-i", str(music),
        "-filter_complex", graph, "-map", "[mix]", "-t", f"{seconds:.3f}", str(out),
    ]


def loudnorm_filter(measured: dict | None) -> str:
    """Second loudnorm pass, using the first pass's measurements for an exact, linear result."""
    if measured is None:
        return "anull"  # silence (fake voices): nothing to normalize
    return (
        f"loudnorm={LOUDNESS}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true"
    )


def final_args(picture: Path, sound: Path, measured: dict | None, out: Path) -> list[str]:
    return [
        "-y", "-i", str(picture), "-i", str(sound), "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-af", loudnorm_filter(measured),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-shortest", "-movflags", "+faststart", str(out),
    ]


def run(args: list[str]) -> None:
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", *args],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()[-1500:]}")


def measure_loudness(path: Path) -> dict | None:
    """First loudnorm pass. None when the track is silent."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path),
         "-af", f"loudnorm={LOUDNESS}:print_format=json", "-f", "null", "-"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    report = result.stderr
    measured = json.loads(report[report.rindex("{"): report.rindex("}") + 1])
    return None if float(measured["input_i"]) < -70 else measured


def media_duration(path: Path) -> float:
    """Length in seconds, read from `ffmpeg -i` because the bundled FFmpeg has no ffprobe."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(f"could not read the duration of {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
