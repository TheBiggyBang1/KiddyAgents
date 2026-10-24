"""Thumbnail artist: the cover picture.

It picks the best scene (passed the vision check, most characters in it) and writes a short
headline on a soft band. Drop a rounded .ttf/.otf font into assets/fonts/ and it's used.
"""

from pathlib import Path

from langgraph.runtime import Runtime
from PIL import Image, ImageDraw, ImageFont, ImageOps

from kiddy.state import EpisodeState, latest_by_scene
from kiddy.studio import RunContext, get_studio

SIZE = (1280, 720)
OUTLINE = (60, 50, 80)
QUESTION_WORDS = {"why", "how", "what", "where", "when", "who", "can", "do", "does", "is", "are"}


def thumbnail_artist(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    images = latest_by_scene(state["images"])
    best = max(
        state["script"].scenes,
        key=lambda s: (images[s.id].flagged is None, len(s.characters), -s.id),
    )
    with Image.open(images[best.id].path) as picture:
        cover = ImageOps.fit(picture.convert("RGB"), SIZE)

    # A soft dark band at the bottom keeps the words readable on any picture.
    band = Image.new("L", SIZE, 0)
    ImageDraw.Draw(band).rectangle((0, SIZE[1] - 210, SIZE[0], SIZE[1]), fill=110)
    cover.paste((30, 20, 40), mask=band)

    words = headline(state["brief"].topic)
    draw = ImageDraw.Draw(cover)
    size = 120
    font = load_font(studio.assets_dir / "fonts", size)
    while draw.textlength(words, font=font) > SIZE[0] - 80 and size > 40:
        size -= 6
        font = load_font(studio.assets_dir / "fonts", size)
    draw.text(
        (SIZE[0] // 2, SIZE[1] - 60), words, anchor="ms", fill="white", font=font,
        stroke_width=max(size // 12, 2), stroke_fill=OUTLINE,
    )
    out = studio.episode_dir(state["episode_id"]) / "thumbnail.jpg"
    cover.save(out, quality=90)
    return {"thumbnail_path": str(out)}


def headline(topic: str) -> str:
    """'how do bees make honey?' -> 'How Do Bees Make Honey?' (six words at most)."""
    words = topic.strip().rstrip("?!.").split()[:6]
    text = " ".join(word.capitalize() for word in words)
    return text + "?" if words and words[0].lower() in QUESTION_WORDS else text


def load_font(folder: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    fonts = sorted([*folder.glob("*.ttf"), *folder.glob("*.otf")])
    return ImageFont.truetype(str(fonts[0]), size) if fonts else ImageFont.load_default(size=size)
