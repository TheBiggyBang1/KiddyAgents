import json
from dataclasses import replace
from datetime import datetime

import pytest

from kiddy.approval import publish
from kiddy.state import YouTubeMetadata
from kiddy.store import save_json
from kiddy.studio import Studio, studio_for
from kiddy.youtube import YouTubeClient, next_slot, srt, video_body


def make_episode(studio: Studio, episode_id: str = "ep-up", **fields: str) -> None:
    """An approved episode folder with everything the publisher reads."""
    folder = studio.output_dir / "episodes" / episode_id
    folder.mkdir(parents=True)
    (folder / "video.mp4").write_bytes(b"video")
    (folder / "thumbnail.jpg").write_bytes(b"jpeg")
    captions = [{"text": "Hello, Fennel!", "start": 0.4, "end": 2.25}]
    (folder / "props.json").write_text(json.dumps({"captions": captions}), "utf-8")
    save_json(folder / "metadata.json", YouTubeMetadata(
        title="Fennel's Thirsty Day", description="Water keeps us strong.",
        tags=["water", "kids cartoon"], chapters=[]))
    studio.store.start(episode_id, format="puppet", status="approved", **fields)


def test_captions_become_an_srt_file():
    lines = [{"text": "Hi!", "start": 3.7, "end": 5.25}, {"text": "Bye!", "start": 3725.5,
                                                          "end": 3726}]
    assert srt(lines) == ("1\n00:00:03,700 --> 00:00:05,250\nHi!\n\n"
                          "2\n01:02:05,500 --> 01:02:06,000\nBye!\n")


def test_next_slot_is_free_and_leaves_time_to_process():
    now = datetime(2026, 10, 27, 15, 30).astimezone()

    def at(day: int, hour: int) -> datetime:
        return datetime(2026, 10, day, hour).astimezone()

    times = ["16:00", "09:00"]
    assert next_slot(times, set(), now) == at(28, 9)  # 16:00 today is too soon
    assert next_slot(times, {at(28, 9)}, now) == at(28, 16)
    assert next_slot([], set(), now) is None  # no times: it stays private


def test_upload_is_made_for_kids_private_and_within_youtube_limits():
    metadata = YouTubeMetadata(title="<Fennel> " + "x" * 120, description="é" * 3000,
                               tags=[f"tag number {n}" for n in range(60)], chapters=[])
    body = video_body(metadata, "2026-10-28T16:00:00+01:00")
    status, snippet = body["status"], body["snippet"]
    assert status["selfDeclaredMadeForKids"] is True and status["privacyStatus"] == "private"
    assert status["publishAt"] == "2026-10-28T16:00:00+01:00"
    assert snippet["title"].startswith("Fennel x") and len(snippet["title"]) == 100
    assert len(snippet["description"].encode("utf-8")) <= 5000
    assert sum(len(tag) + 3 for tag in snippet["tags"]) - 1 <= 500  # quotes and commas count
    assert "publishAt" not in video_body(metadata, "")["status"]


def test_publish_uploads_once_and_retries_only_what_failed(fake_ctx):
    studio = studio_for(fake_ctx)
    make_episode(studio)
    studio.youtube.fail = {"thumbnail"}  # e.g. a channel that isn't verified yet

    first = publish(studio, "ep-up")
    assert first.video_id and first.publish_at and first.captions and not first.thumbnail
    assert first.warnings == ["thumbnail: fake thumbnail failure"]
    studio.youtube.fail = set()
    second = publish(studio, "ep-up")

    assert [name for name, _ in studio.youtube.calls] == ["upload", "captions", "playlist",
                                                          "thumbnail"]
    assert second.video_id == first.video_id and second.thumbnail and not second.warnings
    assert ("playlist", "Puppet shows") in studio.youtube.calls
    subtitles = "1\n00:00:00,400 --> 00:00:02,250\nHello, Fennel!\n"
    assert ("captions", subtitles) in studio.youtube.calls
    row = studio.store.get("ep-up")
    assert row["status"] == "scheduled" and row["youtube_video_id"] == first.video_id


def test_each_video_gets_its_own_publishing_time(fake_ctx):
    studio = studio_for(fake_ctx)
    make_episode(studio, "ep-1")
    make_episode(studio, "ep-2")
    assert publish(studio, "ep-1").publish_at != publish(studio, "ep-2").publish_at


def test_fake_episodes_never_reach_real_youtube(fake_ctx, tmp_path):
    studio = replace(studio_for(fake_ctx), youtube=YouTubeClient(tmp_path))
    make_episode(studio, fake="yes")
    with pytest.raises(RuntimeError, match="--fake"):
        publish(studio, "ep-up")
