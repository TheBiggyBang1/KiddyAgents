"""Art director: one image prompt per scene, and one reference sheet per character.

The sheets are painted once and reused in every episode, so the characters stay on-model.
"""

import zlib
from pathlib import Path

from langgraph.runtime import Runtime

from kiddy.settings import Character
from kiddy.state import ArtPlan, EpisodeState, ScenePrompt
from kiddy.store import save_json, write_once
from kiddy.studio import RunContext, Studio, get_studio

NO_TEXT = "no text, no letters, no logos"
SHEET_SIZE = (512, 512)
MAX_REFERENCES = 4  # what FLUX.2 accepts per picture


def art_director(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    cfg = studio.settings
    prompts = []
    for scene in state["script"].scenes:
        cast = [found for ref in scene.characters if (found := cfg.character(ref))]
        cast = cast[:MAX_REFERENCES]
        looks = "; ".join(f"{c.name} is {c.look}" for c in cast)
        hint = ", ".join(f"image {i} is {c.name}" for i, c in enumerate(cast))
        parts = [
            cfg.art_style, scene.visual, looks,
            f"Reference images: {hint}. Keep each character exactly as in their reference" if cast
            else "",
            NO_TEXT,
        ]
        prompts.append(ScenePrompt(
            scene_id=scene.id,
            prompt=". ".join(p for p in parts if p),
            references=[str(reference_sheet(studio, c)) for c in cast],
        ))
    plan = ArtPlan(style=cfg.art_style, prompts=prompts)
    save_json(studio.episode_dir(state["episode_id"]) / "art_plan.json", plan)
    return {"art_plan": plan}


def reference_sheet(studio: Studio, character: Character) -> Path:
    """The character's reference picture. Changing their look or the art style makes a new one."""
    version = zlib.crc32(f"{studio.settings.art_style}|{character.look}".encode())
    out = studio.assets_dir / "characters" / character.id / f"reference-{version:08x}.png"
    prompt = (
        f"{studio.settings.art_style}. Character reference of {character.name}, "
        f"{character.look}. Full body, front view, friendly smile, standing on a plain white "
        f"background, centered. {NO_TEXT}"
    )
    return write_once(out, lambda part: studio.images.generate(
        prompt, [], SHEET_SIZE, part, seed=version % 2**31
    ))
