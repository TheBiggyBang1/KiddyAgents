"""The one step a human does: watch the finished video, then approve or reject it.

The graph pauses here with interrupt(); `kiddy approve` / `kiddy reject` resume it. Rejection
notes are saved, and the showrunner and writer read them before making the next episodes.
Approved videos go to YouTube as private and go public by themselves at the next free slot.
"""

import json
from datetime import datetime

from langgraph.graph import END
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from kiddy.state import YouTubeMetadata
from kiddy.store import save_json
from kiddy.studio import RunContext, Studio, get_studio
from kiddy.youtube import FakeYouTube, Progress, YouTubeError, next_slot, srt, video_body


def approval(state: dict, runtime: Runtime[RunContext]) -> dict:
    store = get_studio(runtime).store
    store.update(state["episode_id"], status="awaiting_approval")
    answer = interrupt({
        "episode_id": state["episode_id"],
        "title": state["metadata"].title,
        "video": state["video_path"],
        "checks_failed": [c.name for c in state["qa"].checks if not c.ok],
    })
    if answer.get("approved"):
        return {"status": "approved"}
    store.update(state["episode_id"], status="rejected", notes=answer.get("notes") or "")
    return {"status": "rejected"}


def after_approval(state: dict) -> str:
    return "publisher" if state["status"] == "approved" else END


def publisher(state: dict, runtime: Runtime[RunContext]) -> dict:
    """Upload the approved video, unless youtube.upload is off. Safe to run again after a stop."""
    studio = get_studio(runtime)
    studio.store.update(state["episode_id"], status="approved",
                        tokens_used=state.get("tokens_used", 0))
    if not studio.settings.youtube.upload:
        return {"status": "approved"}
    done = publish(studio, state["episode_id"])
    return {"status": "scheduled" if done.publish_at else "uploaded", "youtube": done.model_dump()}


def publish(studio: Studio, episode_id: str) -> Progress:
    """Put an approved episode on YouTube, or finish an upload that stopped. Never uploads twice.

    Every step is saved in youtube.json as soon as it's done. The video itself must succeed; a
    thumbnail, captions or playlist that fails becomes a warning, and the next run retries it.
    """
    cfg = studio.settings.youtube
    row = studio.store.get(episode_id)
    if row["fake"] and not isinstance(studio.youtube, FakeYouTube):
        raise RuntimeError(f"{episode_id} was made with --fake (placeholder pictures and silent "
                           "voices), so it never goes to YouTube.")
    folder = studio.output_dir / "episodes" / episode_id
    record = folder / "youtube.json"
    done = (Progress.model_validate_json(record.read_text("utf-8")) if record.exists()
            else Progress())
    metadata = YouTubeMetadata.model_validate_json((folder / "metadata.json").read_text("utf-8"))

    if not done.video_id:
        taken = {datetime.fromisoformat(r["publish_at"]) for r in studio.store.recent(500)
                 if r["publish_at"]}
        slot = next_slot(cfg.publish_times, taken, datetime.now().astimezone())
        done.publish_at = slot.isoformat(timespec="seconds") if slot else ""
        done.video_id = studio.youtube.upload(folder / "video.mp4",
                                              video_body(metadata, done.publish_at))
        save_json(record, done)
        studio.store.update(episode_id, youtube_video_id=done.video_id,
                            publish_at=done.publish_at)

    captions = json.loads((folder / "props.json").read_text("utf-8")).get("captions") or []
    subtitles = folder / "captions.srt"
    subtitles.write_text(srt(captions), encoding="utf-8")
    playlist = cfg.playlists.get(row["format"] or "")
    steps = {"thumbnail": lambda: studio.youtube.set_thumbnail(done.video_id,
                                                               folder / "thumbnail.jpg")}
    if cfg.captions and captions:
        steps["captions"] = lambda: studio.youtube.add_captions(done.video_id, subtitles,
                                                                metadata.default_language)
    if playlist:
        steps["playlist"] = lambda: studio.youtube.add_to_playlist(done.video_id, playlist)
    done.warnings = []
    for name, step in steps.items():
        if getattr(done, name):
            continue
        try:
            step()
            setattr(done, name, True)
        except YouTubeError as error:
            done.warnings.append(f"{name}: {error}")
        save_json(record, done)
    studio.store.update(episode_id, status="scheduled" if done.publish_at else "uploaded")
    return done
