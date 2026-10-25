"""Illustrator: paints one scene per Send task, has a vision model check it, redraws if needed.

A finished picture is never painted twice: a resumed run keeps it, with its check result.
`paint_checked` is shared with the tracing videos' painter.
"""

import zlib
from pathlib import Path

from langgraph.runtime import Runtime

from kiddy.prompts import as_yaml, system_prompt
from kiddy.state import Scene, SceneImage, SceneJob, VisionCheck
from kiddy.store import save_json
from kiddy.studio import RunContext, Studio, get_studio

MAX_REDRAWS = 2


def illustrator(job: SceneJob, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    scene, video = job["scene"], studio.settings.video
    out = studio.episode_dir(job["episode_id"]) / "images" / f"scene_{scene.id:02d}.png"
    report = out.with_suffix(".check.json")
    tokens = 0 if out.exists() else paint_checked(
        studio, job["prompt"], [Path(path) for path in job["references"]],
        (video.width, video.height), out, f"{job['episode_id']}/{scene.id}",
        vision_request(studio, scene),
    )
    image = SceneImage(scene_id=scene.id, path=str(out), flagged=flag(report))
    return {"images": [image], "tokens_used": tokens}


def paint_checked(
    studio: Studio, prompt: str, refs: list[Path], size: tuple[int, int], out: Path,
    seed_key: str, request: dict,
) -> int:
    """Paint until the vision check passes or the redraws run out. Returns tokens spent."""
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(f"{out.stem}.part{out.suffix}")
    tries, tokens, check = prompt, 0, None
    for attempt in range(MAX_REDRAWS + 1):
        seed = zlib.crc32(f"{seed_key}/{attempt}".encode()) % 2**31
        studio.images.generate(tries, refs, size, part, seed=seed)
        if not studio.settings.vision_check:
            break
        check, spent = studio.llm.structured(
            "vision_check", VisionCheck, system_prompt("vision_check"), as_yaml(request),
            images=[part],
        )
        tokens += spent
        if check.passed:
            break
        tries = f"{prompt}. Fix from the last try: {'; '.join(check.problems)}"
    if check:
        save_json(out.with_suffix(".check.json"), check)
    part.replace(out)  # last, so a crash never leaves a half-checked picture behind
    return tokens


def flag(report: Path) -> str | None:
    """Why a finished picture failed its vision check, or None if it passed (or wasn't checked)."""
    if not report.exists():
        return None
    check = VisionCheck.model_validate_json(report.read_text("utf-8"))
    return None if check.passed else "; ".join(check.problems) or "unclear"


def vision_request(studio: Studio, scene: Scene) -> dict:
    cast = [found for ref in scene.characters if (found := studio.settings.character(ref))]
    looks = [{"name": c.name, "look": c.look} for c in cast]
    return {"scene": scene.visual, "characters": looks}
