"""SRT captions, uploaded to YouTube as a caption track rather than burned into the video."""

from pathlib import Path

from kiddy.state import Timing


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def write_srt(timings: list[Timing], out: Path) -> Path:
    blocks = [
        f"{number}\n{srt_time(t.start)} --> {srt_time(t.end)}\n{t.text}\n"
        for number, t in enumerate(timings, 1)
    ]
    out.write_text("\n".join(blocks), encoding="utf-8")
    return out
