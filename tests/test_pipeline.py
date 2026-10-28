from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from kiddy.checkpoints import SERDE, sqlite_checkpointer
from kiddy.graph import build_graph
from kiddy.media.ffmpeg import media_duration
from kiddy.nodes.editor import timeline
from kiddy.nodes.illustrator import MAX_REDRAWS
from kiddy.providers.images import FakeImages
from kiddy.providers.llm import BadModelOutput, FakeLLM
from kiddy.state import Script, VisionCheck, latest_by_scene
from kiddy.studio import RunContext, studio_for

EPISODE_FILES = [
    "brief.json", "script.json", "review.json", "art_plan.json", "video.mp4",
    "captions.srt", "thumbnail.jpg", "metadata.json", "qa_report.json",
]


def start(ctx: RunContext, episode_id: str) -> tuple[dict, dict]:
    studio_for(ctx).store.start(episode_id)
    return {"episode_id": episode_id, "topic": ""}, {"configurable": {"thread_id": episode_id}}


def test_fake_episode_makes_a_playable_video(fake_ctx):
    graph = build_graph(InMemorySaver(serde=SERDE))
    inputs, config = start(fake_ctx, "ep-test")

    final = graph.invoke(inputs, config, context=fake_ctx)

    folder = Path(fake_ctx.output_dir) / "episodes" / "ep-test"
    assert final["status"] == "ready"
    assert final["qa"].passed
    assert [name for name in EPISODE_FILES if not (folder / name).exists()] == []
    shots = timeline(final["script"], latest_by_scene(final["audio"]), fps=10)
    expected = shots[-1].start + shots[-1].length  # scenes overlap by the crossfade
    assert media_duration(folder / "video.mp4") == pytest.approx(expected, abs=0.3)
    assert studio_for(fake_ctx).store.recent(1)[0]["status"] == "ready"


def count_paintings(monkeypatch) -> list[str]:
    """Record the name of every picture FakeImages paints."""
    painted, real_generate = [], FakeImages.generate

    def counting_generate(self, prompt, refs, size, out, seed=0):
        painted.append(out.name.split(".")[0])
        return real_generate(self, prompt, refs, size, out, seed)

    monkeypatch.setattr(FakeImages, "generate", counting_generate)
    return painted


def test_failed_vision_check_redraws_then_flags(fake_ctx, monkeypatch):
    painted = count_paintings(monkeypatch)
    real_structured = FakeLLM.structured

    def picky(self, agent, schema, system, user, images=()):
        if schema is VisionCheck and images and Path(images[0]).name.startswith("scene_02"):
            return VisionCheck(matches_scene=True, characters_on_model=False, has_text=False,
                               unsettling=False, problems=["Give Olo his yellow scarf"]), 0
        return real_structured(self, agent, schema, system, user, images)

    monkeypatch.setattr(FakeLLM, "structured", picky)
    graph = build_graph(InMemorySaver(serde=SERDE))
    inputs, config = start(fake_ctx, "ep-picky")

    final = graph.invoke(inputs, config, context=fake_ctx)

    assert painted.count("scene_02") == 1 + MAX_REDRAWS
    assert painted.count("scene_01") == 1
    flagged = {image.scene_id: image.flagged for image in final["images"]}
    assert flagged[2] == "Give Olo his yellow scarf" and flagged[1] is None
    assert not final["qa"].passed  # flagged pictures show up at the approval gate
    assert final["status"] == "ready"  # but they don't stop the video


def test_a_checker_that_cant_answer_flags_the_picture_instead_of_stopping(fake_ctx,
                                                                         monkeypatch):
    painted = count_paintings(monkeypatch)
    real_structured = FakeLLM.structured

    def mute(self, agent, schema, system, user, images=()):
        if schema is VisionCheck and images and Path(images[0]).name.startswith("scene_02"):
            raise BadModelOutput("vision_check: no valid VisionCheck after 2 tries")
        return real_structured(self, agent, schema, system, user, images)

    monkeypatch.setattr(FakeLLM, "structured", mute)
    graph = build_graph(InMemorySaver(serde=SERDE))
    inputs, config = start(fake_ctx, "ep-mute")

    final = graph.invoke(inputs, config, context=fake_ctx)

    assert painted.count("scene_02") == 1  # kept, not redrawn
    flagged = {image.scene_id: image.flagged for image in final["images"]}
    assert "look at this picture yourself" in flagged[2]
    assert final["status"] == "ready"


def test_reference_sheets_are_painted_once_for_every_episode(fake_ctx, monkeypatch):
    painted = count_paintings(monkeypatch)
    graph = build_graph(InMemorySaver(serde=SERDE))
    for episode_id in ("ep-one", "ep-two"):
        inputs, config = start(fake_ctx, episode_id)
        graph.invoke(inputs, config, context=fake_ctx)

    sheets = [name for name in painted if name.startswith("reference")]
    assert len(sheets) == 3  # Fennel, Olo and Glim, once each
    # Fake runs keep their placeholder sheets away from the real assets folder.
    assert len(list((Path(fake_ctx.output_dir) / "fake-assets").rglob("reference-*.png"))) == 3


def test_resume_never_paints_a_scene_twice(fake_ctx, monkeypatch):
    painted, failures = [], []
    real_generate = FakeImages.generate

    def flaky_generate(self, prompt, refs, size, out, seed=0):
        if out.name.startswith("scene_02") and not failures:
            failures.append(out.name)
            raise RuntimeError("image service is down")
        painted.append(out.name.split(".")[0])
        return real_generate(self, prompt, refs, size, out, seed)

    monkeypatch.setattr(FakeImages, "generate", flaky_generate)
    checkpointer = sqlite_checkpointer(Path(fake_ctx.data_dir) / "checkpoints.sqlite")
    graph = build_graph(checkpointer)
    inputs, config = start(fake_ctx, "ep-resume")

    with pytest.raises(RuntimeError, match="image service is down"):
        graph.invoke(inputs, config, context=fake_ctx)
    final = graph.invoke(None, config, context=fake_ctx)  # what `kiddy resume` does

    assert final["status"] == "ready"
    scenes = [name for name in painted if name.startswith("scene")]
    assert sorted(scenes) == [f"scene_{n:02d}" for n in range(1, len(final["script"].scenes) + 1)]
    # Rebuilt from SQLite as real models, not plain dicts: the checkpoint allowlist works.
    assert isinstance(graph.get_state(config).values["script"], Script)
    checkpointer.conn.close()
