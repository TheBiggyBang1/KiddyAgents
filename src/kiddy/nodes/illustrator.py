"""Illustrator: paints one scene per Send task, has a vision model check it, redraws if needed.

A finished picture is never painted twice: a resumed run keeps it, with its check result.
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
    scene = job["scene"]
    out = studio.episode_dir(job["episode_id"]) / "images" / f"scene_{scene.id:02d}.png"
    report = out.with_suffix(".check.json")
    tokens = 0 if out.exists() else paint(studio, job, out, report)
    check = VisionCheck.model_validate_json(report.read_text("utf-8")) if report.exists() else None
    flagged = None if check is None or check.passed else "; ".join(check.problems) or "unclear"
    image = SceneImage(scene_id=scene.id, path=str(out), flagged=flagged)
    return {"images": [image], "tokens_used": tokens}


def paint(studio: Studio, job: SceneJob, out: Path, report: Path) -> int:
    """Paint until the vision check passes or the redraws run out. Returns tokens spent."""
    scene, video = job["scene"], studio.settings.video
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(f"{out.stem}.part{out.suffix}")
    prompt, tokens, check = job["prompt"], 0, None
    for attempt in range(MAX_REDRAWS + 1):
        seed = zlib.crc32(f"{job['episode_id']}/{scene.id}/{attempt}".encode()) % 2**31
        refs = [Path(path) for path in job["references"]]
        studio.images.generate(prompt, refs, (video.width, video.height), part, seed=seed)
        if not studio.settings.vision_check:
            break
        check, spent = look_at(studio, scene, part)
        tokens += spent
        if check.passed:
            break
        prompt = f"{job['prompt']}. Fix from the last try: {'; '.join(check.problems)}"
    if check:
        save_json(report, check)
    part.replace(out)  # last, so a crash never leaves a half-checked picture behind
    return tokens


def look_at(studio: Studio, scene: Scene, picture: Path) -> tuple[VisionCheck, int]:
    cast = [found for ref in scene.characters if (found := studio.settings.character(ref))]
    looks = [{"name": c.name, "look": c.look} for c in cast]
    request = {"scene": scene.visual, "characters": looks}
    return studio.llm.structured(
        "vision_check", VisionCheck, system_prompt("vision_check"), as_yaml(request),
        images=[picture],
    )
