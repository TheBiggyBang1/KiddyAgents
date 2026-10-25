"""The tracing video's agents: planner, painter, narrator, composer, renderer and the finishers."""

import json
import re
from pathlib import Path

from langgraph.runtime import Runtime
from langgraph.types import Send

from kiddy.media import audio, ffmpeg
from kiddy.nodes.illustrator import flag, paint_checked
from kiddy.prompts import as_yaml, system_prompt
from kiddy.providers.llm import BadModelOutput
from kiddy.state import Check, QAReport, YouTubeMetadata
from kiddy.store import save_json, write_once
from kiddy.studio import RunContext, get_studio
from kiddy.tracing import render
from kiddy.tracing.compose import compose, script_lines
from kiddy.tracing.models import LetterPlan, PictureJob, TracingState, VoiceLine, WordPicture

WORDS = 3
PICTURE_SIZE = (768, 768)
NO_TEXT = "no text, no letters, no logos"


def planner(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    """Picks three words for the letter. The only model call in the whole video."""
    studio = get_studio(runtime)
    letter = state["letter"]
    request = {"letter": letter, "audience_age": studio.settings.audience_age, "words": WORDS}
    plan, tokens = studio.llm.structured(
        "letter_planner", LetterPlan, system_prompt("letter_planner"), as_yaml(request)
    )
    plan = check_plan(plan, letter)
    save_json(studio.episode_dir(state["episode_id"]) / "plan.json", plan)
    studio.store.update(state["episode_id"], topic=f"letter {letter}", format="tracing",
                        title=f"Trace the Letter {letter}", status="making")
    return {"plan": plan, "status": "making", "tokens_used": tokens}


def check_plan(plan: LetterPlan, letter: str) -> LetterPlan:
    """Keep real words for this letter; X may use words that just contain it (box, fox)."""
    keep, seen = [], set()
    for idea in plan.words:
        word = idea.word.strip().capitalize()
        fits = word.upper().startswith(letter) or (letter == "X" and "X" in word.upper())
        if re.fullmatch(r"[A-Za-z-]{2,12}", word) and fits and word not in seen:
            seen.add(word)
            keep.append(idea.model_copy(update={"word": word}))
    if len(keep) < WORDS:
        raise BadModelOutput(f"only {len(keep)} usable words for {letter}: {plan.words}")
    return plan.model_copy(update={"words": keep[:WORDS]})


def paint_each_word(state: TracingState) -> list[Send]:
    return [Send("painter", {"episode_id": state["episode_id"], "index": number, "idea": idea})
            for number, idea in enumerate(state["plan"].words, 1)]


def painter(job: PictureJob, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    idea = job["idea"]
    out = studio.episode_dir(job["episode_id"]) / "images" / f"word_{job['index']}.png"
    prompt = (f"{studio.settings.tracing.picture_style}. {idea.picture}. One object, centered, "
              f"on a plain white background. {NO_TEXT}")
    tokens = 0 if out.exists() else paint_checked(
        studio, prompt, [], PICTURE_SIZE, out, f"{job['episode_id']}/word/{job['index']}",
        {"scene": idea.picture, "characters": []},
    )
    flagged = flag(out.with_suffix(".check.json"))
    picture = WordPicture(index=job["index"], path=str(out), flagged=flagged)
    return {"pictures": [picture], "tokens_used": tokens}


def pictures_done(state: TracingState) -> dict:
    """Join point: runs once, after every painter task has finished."""
    return {}


def narrator(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"]) / "audio"
    voice = studio.settings.narrator_voice
    lines = []
    for key, text in script_lines(state["letter"], state["plan"]).items():
        out = write_once(folder / f"{key}.wav",
                         lambda part, text=text: studio.tts.speak(text, voice, "warm", part))
        lines.append(VoiceLine(key=key, text=text, path=str(out), duration_s=audio.duration(out)))
    return {"lines": lines}


def composer(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"])
    props = compose(
        state["letter"], state["plan"], {p.index: p for p in state["pictures"]},
        {line.key: line for line in state["lines"]}, folder,
        studio.settings.tracing.practice_seconds,
    )
    path = folder / "props.json"
    path.write_text(json.dumps(props, indent=2), encoding="utf-8")
    return {"props_path": str(path)}


def renderer(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"]).resolve()
    raw = folder / "render.mp4"
    render.run(render.video_args(Path(state["props_path"]).resolve(), folder, raw,
                                 studio.settings.video.width))
    out = folder / "video.mp4"  # two-pass loudness to YouTube's -14 LUFS
    ffmpeg.run(ffmpeg.normalize_args(raw, ffmpeg.measure_loudness(raw), out))
    raw.unlink()
    return {"video_path": str(out)}


def thumbnail(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    folder = studio.episode_dir(state["episode_id"]).resolve()
    letter = state["letter"]
    first = min(state["pictures"], key=lambda p: (p.flagged is not None, p.index))
    props = {"upper": letter, "lower": letter.lower(), "headline": f"Trace the Letter {letter}!",
             "image": Path(first.path).resolve().relative_to(folder).as_posix()}
    path = folder / "thumbnail_props.json"
    path.write_text(json.dumps(props), encoding="utf-8")
    out = folder / "thumbnail.jpg"
    render.run(render.thumbnail_args(path, folder, out))
    return {"thumbnail_path": str(out)}


def metadata_writer(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    upper, lower = state["letter"], state["letter"].lower()
    words = [idea.word for idea in state["plan"].words]
    metadata = YouTubeMetadata(
        title=f"Trace the Letter {upper} | Learn to Write {upper} and {lower} for Kids",
        description=(
            f"Let's learn to write the letter {upper}! Trace the big {upper} and the small "
            f"{lower} step by step, then meet {', '.join(words[:-1])} and {words[-1]}.\n\n"
            "Handwriting practice for preschool and kindergarten."
        ),
        tags=[f"letter {upper}", "alphabet tracing", "learn to write", "abc for kids",
              "preschool", "handwriting", *[w.lower() for w in words]],
        chapters=[],
        default_language=studio.settings.language,
    )
    save_json(studio.episode_dir(state["episode_id"]) / "metadata.json", metadata)
    return {"metadata": metadata}


def qa_gate(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    video = Path(state["video_path"])
    seconds = ffmpeg.media_duration(video) if video.exists() else 0.0
    flagged = [f"word {p.index}: {p.flagged}" for p in state["pictures"] if p.flagged]
    report = QAReport(checks=[
        Check(name="video rendered", ok=seconds > 0, detail=f"{seconds:.1f} s"),
        Check(name="every line voiced",
              ok=all(Path(line.path).exists() for line in state["lines"])),
        Check(name="one picture per word",
              ok=len({p.index for p in state["pictures"]}) == len(state["plan"].words)),
        Check(name="every picture passed the vision check", ok=not flagged,
              detail="; ".join(flagged)),
        Check(name="thumbnail", ok=Path(state["thumbnail_path"]).exists()),
        Check(name="title length", ok=0 < len(state["metadata"].title) <= 100),
    ])
    save_json(studio.episode_dir(state["episode_id"]) / "qa_report.json", report)
    return {"qa": report}


def publisher(state: TracingState, runtime: Runtime[RunContext]) -> dict:
    """No upload yet (Milestone 5): marks the episode ready."""
    get_studio(runtime).store.update(
        state["episode_id"], status="ready", tokens_used=state.get("tokens_used", 0)
    )
    return {"status": "ready"}
