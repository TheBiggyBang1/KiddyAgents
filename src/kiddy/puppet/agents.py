"""The puppet show's agents: writer, reviewer, card painter, voices, composer, renderer and more."""

import json
from pathlib import Path

from langgraph.runtime import Runtime
from langgraph.types import Send

from kiddy.media import audio, ffmpeg
from kiddy.nodes.illustrator import flag, paint_checked
from kiddy.nodes.safety_reviewer import length_problems
from kiddy.nodes.scriptwriter import revision_notes
from kiddy.prompts import as_yaml, system_prompt
from kiddy.providers.llm import BadModelOutput
from kiddy.puppet.compose import compose
from kiddy.puppet.models import (
    Beat,
    CardJob,
    CardPicture,
    PuppetScene,
    PuppetScript,
    PuppetState,
    SpokenLine,
)
from kiddy.settings import Settings
from kiddy.state import Check, QAReport, Review, YouTubeMetadata
from kiddy.store import save_json, write_once
from kiddy.studio import RunContext, get_studio
from kiddy.tracing import render

MAX_SCRIPT_ATTEMPTS = 2  # a third draft rarely helps; a blocked show is discarded instead
MAX_CARDS = 5
CARD_SIZE = (768, 576)
NO_TEXT = "no text, no letters, no logos"
BACKGROUNDS = {"meadow": "sunny meadow", "forest": "friendly forest", "pond": "pond with lily pads",
               "night": "starry night", "garden": "garden with a fence", "home": "cozy living room"}


WORDS_PER_MINUTE = 90  # dialogue shares the time with actions, cards and walks


def budget(settings: Settings) -> int:
    return round(sum(settings.puppet_minutes) / 2 * WORDS_PER_MINUTE)


def writer(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    cfg = studio.settings
    request = {
        "idea": state["idea"].model_dump(exclude={"why", "letter"}),
        "audience_age": cfg.audience_age,
        "characters": [c.model_dump(include={"id", "name", "species", "personality"})
                       for c in cfg.characters],
        "stages": BACKGROUNDS,
        "length_plan": {"total_words": budget(cfg), "scenes": "3 to 6"},
        "lessons": [row["notes"] for row in studio.store.recent(80) if row["notes"]] or "none",
    }
    notes = revision_notes(state)
    if notes and "script" in state:
        request["previous_draft"] = state["script"].model_dump()
        request["revision_notes"] = notes
    script, tokens = studio.llm.structured(
        "puppet_writer", PuppetScript, system_prompt("puppet_writer"), as_yaml(request)
    )
    script = tidy(script, cfg)
    save_json(studio.episode_dir(state["episode_id"]) / "script.json", script)
    studio.store.update(state["episode_id"], title=script.title, status="making")
    return {"script": script, "script_attempts": state.get("script_attempts", 0) + 1,
            "tokens_used": tokens, "status": "making"}


def tidy(script: PuppetScript, cfg: Settings) -> PuppetScript:
    """Keep only beats the stage can perform: known cast, complete fields, a few cards."""
    scenes, cards = [], []
    for scene in script.scenes:
        cast = list(dict.fromkeys(found.id for ref in scene.cast if (found := cfg.character(ref))))
        beats = []
        for beat in scene.beats:
            who = cfg.character(beat.character or "")
            if (who and who.id not in cast and len(cast) < 3 and beat.kind in ("say", "act", "move")
                    and keep(beat, who.id, [])):
                cast.append(who.id)  # a character with something to do steps onto the stage
            kept = keep(beat, who.id if who and who.id in cast else None, cards)
            if kept:
                beats.append(kept)
        if any(b.kind == "say" for b in beats):
            scenes.append(PuppetScene(background=scene.background, cast=cast, beats=beats))
    if not scenes:
        raise BadModelOutput("the script has no scene with a spoken line")
    return script.model_copy(update={"scenes": scenes})


def keep(beat: Beat, who: str | None, cards: list[str]) -> Beat | None:
    blank = {"character": None, "text": None, "emotion": None, "action": None, "to": None,
             "card": None}
    match beat.kind:
        case "say" if who and (beat.text or "").strip():
            return Beat(**{**blank, "kind": "say", "character": who, "text": beat.text.strip(),
                           "emotion": beat.emotion or "happy"})
        case "act" if who and beat.action:
            return Beat(**{**blank, "kind": "act", "character": who, "action": beat.action})
        case "move" if who and beat.to:
            return Beat(**{**blank, "kind": "move", "character": who, "to": beat.to})
        case "card" if (beat.card or "").strip() and (beat.card in cards or len(cards) < MAX_CARDS):
            if beat.card not in cards:
                cards.append(beat.card)
            return Beat(**{**blank, "kind": "card", "card": beat.card})
        case "word" if (beat.text or "").strip() and len(beat.text.strip()) <= 14:
            return Beat(**{**blank, "kind": "word", "text": beat.text.strip()})
    return None


def reviewer(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    script = state["script"]
    request = {"audience_age": studio.settings.audience_age, "script": script.model_dump()}
    review, tokens = studio.llm.structured(
        "safety_reviewer", Review, system_prompt("safety_reviewer"), as_yaml(request)
    )
    problems = length_problems(script, budget(studio.settings))
    review = review.model_copy(update={"hard_fails": review.hard_fails + problems})
    save_json(studio.episode_dir(state["episode_id"]) / "review.json", review)
    return {"review": review, "tokens_used": tokens}


def after_review(state: PuppetState) -> str:
    review = state["review"]
    if review.passed and not review.issues:
        return "paint_cards"
    if state.get("script_attempts", 0) < MAX_SCRIPT_ATTEMPTS:
        return "writer"
    return "paint_cards" if review.passed else "discard"


def discard(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    """The script never passed review. Autopilot moves on to a fresh idea instead of asking you."""
    get_studio(runtime).store.update(state["episode_id"], status="discarded",
                                     tokens_used=state.get("tokens_used", 0))
    return {"status": "discarded"}


def card_list(script: PuppetScript) -> list[str]:
    return list(dict.fromkeys(b.card for s in script.scenes for b in s.beats if b.kind == "card"))


def paint_cards(state: PuppetState) -> dict:
    """Join point before the card painters; nothing to do when the show has no cards."""
    return {}


def paint_each_card(state: PuppetState) -> list[Send] | str:
    jobs = [Send("card_painter", {"episode_id": state["episode_id"], "index": i, "description": d})
            for i, d in enumerate(card_list(state["script"]), 1)]
    return jobs or "voices"


def card_painter(job: CardJob, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    out = studio.episode_dir(job["episode_id"]) / "cards" / f"card_{job['index']}.png"
    prompt = (f"{studio.settings.tracing.picture_style}. {job['description']}. One clear "
              f"picture on a plain soft background. {NO_TEXT}")
    tokens = 0 if out.exists() else paint_checked(
        studio, prompt, [], CARD_SIZE, out, f"{job['episode_id']}/card/{job['index']}",
        {"scene": job["description"], "characters": []},
    )
    card = CardPicture(index=job["index"], description=job["description"], path=str(out),
                       flagged=flag(out.with_suffix(".check.json")))
    return {"cards": [card], "tokens_used": tokens}


def voices(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"]) / "audio"
    fps = studio.settings.video.fps
    lines = []
    for s, scene in enumerate(state["script"].scenes, 1):
        for b, beat in enumerate(scene.beats, 1):
            if beat.kind != "say":
                continue
            voice = studio.settings.voice_for(beat.character)
            out = write_once(folder / f"s{s}_b{b}.wav", lambda part, beat=beat, voice=voice:
                             studio.tts.speak(beat.text, voice, beat.emotion, part))
            lines.append(SpokenLine(key=f"s{s}_b{b}", character=beat.character, text=beat.text,
                                    path=str(out), duration_s=audio.duration(out),
                                    mouth=audio.mouth_envelope(out, fps)))
    return {"lines": lines}


def composer(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"])
    cards = {c.description: c for c in state.get("cards", [])}
    props = compose(state["script"], {line.key: line for line in state["lines"]}, cards, folder)
    path = folder / "props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    return {"props_path": str(path)}


def renderer(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"]).resolve()
    raw = folder / "render.mp4"
    render.run(render.video_args(Path(state["props_path"]).resolve(), folder, raw,
                                 studio.settings.video.width, composition="PuppetShow"))
    out = folder / "video.mp4"  # two-pass loudness to YouTube's -14 LUFS
    ffmpeg.run(ffmpeg.normalize_args(raw, ffmpeg.measure_loudness(raw), out))
    raw.unlink()
    return {"video_path": str(out)}


def thumbnail(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"]).resolve()
    first = state["script"].scenes[0]
    cards = sorted((c for c in state.get("cards", []) if not c.flagged), key=lambda c: c.index)
    props = {"headline": state["script"].title, "background": first.background,
             "cast": first.cast,
             "image": Path(cards[0].path).resolve().relative_to(folder).as_posix() if cards else ""}
    path = folder / "thumbnail_props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    out = folder / "thumbnail.jpg"
    render.run(render.thumbnail_args(path, folder, out, composition="PuppetThumbnail"))
    return {"thumbnail_path": str(out)}


def metadata_writer(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    script, idea = state["script"], state["idea"]
    names = [c.name for c in studio.settings.characters]
    metadata = YouTubeMetadata(
        title=f"{script.title} | {studio.settings.channel_name}"[:100],
        description=(f"{script.learning_goal}\n\nA puppet show with {', '.join(names[:-1])} and "
                     f"{names[-1]}, for preschool and kindergarten."),
        tags=list(dict.fromkeys([idea.subject, idea.topic, "kids cartoon", "puppet show",
                                 "preschool learning", *[n.lower() for n in names]])),
        chapters=[],
        default_language=studio.settings.language,
    )
    save_json(studio.episode_dir(state["episode_id"]) / "metadata.json", metadata)
    return {"metadata": metadata}


def qa_gate(state: PuppetState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    video = Path(state["video_path"])
    seconds = ffmpeg.media_duration(video) if video.exists() else 0.0
    cards = state.get("cards", [])
    flagged = [f"card {c.index}: {c.flagged}" for c in cards if c.flagged]
    report = QAReport(checks=[
        Check(name="review passed", ok=state["review"].passed),
        Check(name="video rendered", ok=seconds > 0, detail=f"{seconds:.1f} s"),
        Check(name="every line voiced",
              ok=all(Path(line.path).exists() for line in state["lines"])),
        Check(name="every card painted",
              ok=len({c.index for c in cards}) == len(card_list(state["script"]))),
        Check(name="every card passed the vision check", ok=not flagged, detail="; ".join(flagged)),
        Check(name="thumbnail", ok=Path(state["thumbnail_path"]).exists()),
        Check(name="title length", ok=0 < len(state["metadata"].title) <= 100),
    ])
    save_json(studio.episode_dir(state["episode_id"]) / "qa_report.json", report)
    return {"qa": report}
