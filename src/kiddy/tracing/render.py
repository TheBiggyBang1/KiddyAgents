"""Calls the Remotion project in video/ to render videos and thumbnails (tracing and puppets)."""

import shutil
import subprocess
from pathlib import Path

VIDEO_PROJECT = Path(__file__).resolve().parents[3] / "video"
FULL_WIDTH = 1920  # the AlphabetTracing composition's width


def npx() -> str:
    found = shutil.which("npx")
    if not found:
        raise RuntimeError("Remotion needs Node.js: install it from https://nodejs.org")
    return found


def video_args(
    props: Path, public_dir: Path, out: Path, width: int, composition: str = "AlphabetTracing"
) -> list[str]:
    return [
        npx(), "remotion", "render", "src/index.ts", composition, str(out),
        f"--props={props}", f"--public-dir={public_dir}", f"--scale={width / FULL_WIDTH:g}",
        "--log=error",
    ]


def thumbnail_args(
    props: Path, public_dir: Path, out: Path, composition: str = "Thumbnail"
) -> list[str]:
    return [
        npx(), "remotion", "still", "src/index.ts", composition, str(out),
        f"--props={props}", f"--public-dir={public_dir}", "--image-format=jpeg", "--log=error",
    ]


def run(args: list[str]) -> None:
    result = subprocess.run(
        args, cwd=VIDEO_PROJECT, capture_output=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"Remotion failed: {(result.stderr or result.stdout).strip()[-1500:]}")
