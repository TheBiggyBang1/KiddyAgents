"""QA gate: checks the finished files before anyone sees them. Code only, no model.

Milestone 4 adds duration, loudness and metadata-limit checks, and the automatic redo.
"""

from pathlib import Path

from langgraph.runtime import Runtime

from kiddy.media import ffmpeg
from kiddy.state import Check, EpisodeState, QAReport, latest_by_scene
from kiddy.store import save_json
from kiddy.studio import RunContext, get_studio


def qa_gate(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    scene_ids = [scene.id for scene in state["script"].scenes]
    images, voices = latest_by_scene(state["images"]), latest_by_scene(state["audio"])
    video = Path(state["video_path"])
    seconds = ffmpeg.media_duration(video) if video.exists() else 0.0

    report = QAReport(checks=[
        Check(name="review passed", ok=state["review"].passed),
        Check(name="one picture per scene",
              ok=all(i in images and Path(images[i].path).exists() for i in scene_ids)),
        Check(name="one voice track per scene",
              ok=all(i in voices and Path(voices[i].path).exists() for i in scene_ids)),
        Check(name="every picture passed the vision check",
              ok=not any(images[i].flagged for i in scene_ids if i in images),
              detail="; ".join(f"scene {i}: {images[i].flagged}"
                               for i in scene_ids if i in images and images[i].flagged)),
        Check(name="video rendered", ok=seconds > 0, detail=f"{seconds:.1f} s"),
        Check(name="thumbnail", ok=Path(state["thumbnail_path"]).exists()),
        Check(name="title length", ok=0 < len(state["metadata"].title) <= 100),
    ])
    save_json(studio.episode_dir(state["episode_id"]) / "qa_report.json", report)
    return {"qa": report}
