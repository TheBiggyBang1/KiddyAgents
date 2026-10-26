"""The puppet show's timeline, in the shape video/src/puppet/types.ts expects.

Lines play one after another at their real lengths; actions and walks start with the next line
so the show keeps moving; cards stay up until the next card, word or scene.
"""

from pathlib import Path

from kiddy.puppet.models import CardPicture, PuppetScript, SpokenLine

SLOTS = {"left": 500, "center": 960, "right": 1420}
INTRO = 3.0  # title card
GAP = 0.3  # between two lines
OPEN, CLOSE = 0.7, 0.9  # quiet at the start and end of a scene
ACT, WALK = 1.3, 1.4  # how long an action and a walk take


def places(cast: list[str]) -> dict[str, int]:
    names = {1: ["center"], 2: ["left", "right"], 3: ["left", "center", "right"]}[len(cast)]
    return {who: SLOTS[place] for who, place in zip(cast, names, strict=True)}


def compose(
    script: PuppetScript, lines: dict[str, SpokenLine], cards: dict[str, CardPicture], folder: Path
) -> dict:
    stages: list[dict] = []
    audio: list[dict] = []
    captions: list[dict] = []
    clock = INTRO
    for s, scene in enumerate(script.scenes, 1):
        start, t = clock, clock + OPEN
        actors = {who: {"id": who, "x": x, "talks": [], "acts": [], "moves": [],
                        "moods": [{"start": round(start, 3), "emotion": "happy"}]}
                  for who, x in places(scene.cast).items()}
        shown: list[dict] = []
        words: list[dict] = []
        for b, beat in enumerate(scene.beats, 1):
            if beat.kind == "say":
                line = lines[f"s{s}_b{b}"]
                actor = actors[line.character]
                actor["talks"].append({"start": round(t, 3), "duration": round(line.duration_s, 3),
                                       "mouth": line.mouth})
                actor["moods"].append({"start": round(t, 3), "emotion": beat.emotion or "happy"})
                audio.append({"src": relative(line.path, folder), "start": round(t, 3)})
                captions.append({"text": line.text, "start": round(t, 3),
                                 "end": round(t + line.duration_s, 3)})
                t += line.duration_s + GAP
            elif beat.kind == "act":
                actors[beat.character]["acts"].append(
                    {"start": round(t, 3), "duration": ACT, "action": beat.action})
                t += 0.4
            elif beat.kind == "move":
                actors[beat.character]["moves"].append(
                    {"start": round(t, 3), "duration": WALK, "to": SLOTS[beat.to]})
                t += 1.0
            elif beat.kind == "card":
                close_card(shown, t)
                shown.append({"start": round(t, 3), "end": None,
                              "image": relative(cards[beat.card].path, folder)})
                t += 0.6
            elif beat.kind == "word":
                close_card(shown, t)
                words.append({"start": round(t, 3), "end": round(t + 2.4, 3), "text": beat.text})
                t += 0.6
        end = max(t + CLOSE, *(w["end"] for w in words)) if words else t + CLOSE
        close_card(shown, end)
        stages.append({"start": round(start, 3), "duration": round(end - start, 3),
                       "background": scene.background, "actors": list(actors.values()),
                       "cards": shown, "words": words})
        clock = end
    return {"title": script.title, "intro": INTRO, "stages": stages, "audio": audio,
            "captions": captions}


def close_card(shown: list[dict], at: float) -> None:
    """The card on the easel comes down when the next card, word or scene comes."""
    if shown and shown[-1]["end"] is None:
        shown[-1]["end"] = round(at, 3)


def relative(path: str, folder: Path) -> str:
    """Remotion reads files through --public-dir, so props hold paths relative to the episode."""
    return Path(path).resolve().relative_to(folder.resolve()).as_posix()
