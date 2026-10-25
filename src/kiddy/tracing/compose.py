"""What the narrator says, and the timeline Remotion renders (video/src/types.ts is the contract).

Everything is timed from the real voice lengths: a stroke is drawn while its instruction is
spoken, and each scene lasts as long as its lines plus a little breathing room.
"""

from pathlib import Path

from kiddy.tracing.models import LetterPlan, VoiceLine, WordPicture, library

UPPER_COLOR, LOWER_COLOR = "#FF6B6B", "#4D96FF"  # match video/src/theme.ts
GAP = 0.35  # quiet between two lines
MIN_DRAW = 1.2  # a stroke never draws faster than this, however short its instruction
HOLD = 0.9  # the finished letter stays on screen before the next scene


def script_lines(letter: str, plan: LetterPlan) -> dict[str, str]:
    """Every line of the video, keyed by where it's used. Templates, so no model tokens."""
    upper = letter.upper()
    lines = {"title": f"Let's learn to write the letter {upper}!"}
    for case, size in (("upper", "big"), ("lower", "small")):
        glyph = upper if case == "upper" else letter.lower()
        lines[f"{case}_intro"] = f"This is a {size} letter {upper}. Start at the green dot."
        for number, stroke in enumerate(library()[glyph], 1):
            lines[f"{case}_{number}"] = stroke.say
        lines[f"{case}_try"] = f"Your turn! Trace the {size} {upper} with your finger."
    for number, idea in enumerate(plan.words, 1):
        opening = (f"{upper} is for {idea.word.lower()}!" if idea.word.upper().startswith(upper)
                   else f"You can find {upper} in {idea.word.lower()}!")
        lines[f"word_{number}"] = f"{opening} {idea.sentence}"
    lines["outro"] = f"Great job! Now you can write the letter {upper}!"
    return lines


def compose(
    letter: str, plan: LetterPlan, pictures: dict[int, WordPicture], lines: dict[str, VoiceLine],
    folder: Path, practice_seconds: float,
) -> dict:
    """The props.json Remotion renders: scenes, voice clips and captions, all in seconds."""
    upper, lower = letter.upper(), letter.lower()
    segments: list[dict] = []
    audio: list[dict] = []
    captions: list[dict] = []

    def say(key: str, at: float) -> float:
        line = lines[key]
        audio.append({"src": relative(line.path, folder), "start": round(at, 3)})
        captions.append({"text": line.text, "start": round(at, 3),
                         "end": round(at + line.duration_s, 3)})
        return at + line.duration_s

    def scene(kind: str, start: float, end: float, **fields) -> float:
        segments.append({"kind": kind, "start": round(start, 3),
                         "duration": round(end - start, 3), **fields})
        return end

    clock = scene("title", 0.0, say("title", 0.4) + 0.8, upper=upper, lower=lower)
    for case, glyph, color in (("upper", upper, UPPER_COLOR), ("lower", lower, LOWER_COLOR)):
        start, t = clock, say(f"{case}_intro", clock + 0.3) + GAP
        strokes = []
        for number, stroke in enumerate(library()[glyph], 1):
            draw = max(lines[f"{case}_{number}"].duration_s, MIN_DRAW)
            say(f"{case}_{number}", t)
            strokes.append({"d": stroke.d, "start": round(t + 0.1, 3),
                            "duration": round(draw - 0.1, 3)})
            t += draw + GAP
        clock = scene("trace", start, t + HOLD, glyph=glyph, color=color, strokes=strokes)
        clock = scene("practice", clock, say(f"{case}_try", clock + 0.3) + practice_seconds,
                      glyph=glyph, color=color,
                      strokes=[{"d": s.d} for s in library()[glyph]])
    for number, idea in enumerate(plan.words, 1):
        picture = pictures.get(number)
        clock = scene("word", clock, say(f"word_{number}", clock + 0.5) + 1.0, word=idea.word,
                      image=relative(picture.path, folder) if picture else "", letter=upper)
    scene("outro", clock, say("outro", clock + 0.5) + 2.5, upper=upper, lower=lower)
    return {"letter": upper, "title": f"Trace the Letter {upper}", "segments": segments,
            "audio": audio, "captions": captions}


def relative(path: str, folder: Path) -> str:
    """Remotion reads files through --public-dir, so props hold paths relative to the episode."""
    return Path(path).relative_to(folder).as_posix()
