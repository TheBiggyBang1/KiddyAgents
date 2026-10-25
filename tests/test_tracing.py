import json
import re
import string
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from kiddy.checkpoints import SERDE
from kiddy.media.ffmpeg import media_duration
from kiddy.providers.fixtures import letter_plan
from kiddy.providers.llm import BadModelOutput
from kiddy.studio import studio_for
from kiddy.tracing.agents import check_plan
from kiddy.tracing.compose import MIN_DRAW, compose, script_lines
from kiddy.tracing.graph import build_tracing_graph
from kiddy.tracing.models import LetterPlan, VoiceLine, WordIdea, WordPicture, library

PATH = re.compile(r"^M[\d.\- ]+( [LC][\d.\- ]+)+$")


def test_every_letter_has_drawable_strokes_and_words_to_say():
    letters = library()
    assert sorted(letters) == sorted(string.ascii_uppercase + string.ascii_lowercase)
    for char, strokes in letters.items():
        assert strokes, char
        for stroke in strokes:
            assert PATH.match(stroke.d), f"{char}: {stroke.d}"
            assert stroke.say.endswith("."), f"{char}: {stroke.say}"


def test_plan_keeps_real_words_for_the_letter():
    ideas = [WordIdea(word=w, sentence="Hi.", picture=w) for w in
             ["apple", "Banana", "ant", "Apple", "alligator", "Avocado"]]
    words = [idea.word for idea in check_plan(LetterPlan(words=ideas), "A").words]
    assert words == ["Apple", "Ant", "Alligator"]  # capitalized, no B word, no repeat
    assert [i.word for i in check_plan(letter_plan("X"), "X").words] == ["Xylophone", "Box", "Fox"]
    with pytest.raises(BadModelOutput):
        check_plan(LetterPlan(words=ideas[:2]), "A")


def test_lines_follow_the_stroke_library():
    lines = script_lines("A", letter_plan("A"))
    assert lines["upper_2"] == library()["A"][1].say
    assert lines["word_1"] == "A is for apple! Can you say apple?"
    assert script_lines("X", letter_plan("X"))["word_2"].startswith("You can find X in box!")


def test_strokes_are_drawn_while_their_instructions_are_spoken(tmp_path):
    plan = letter_plan("A")
    lines = {key: VoiceLine(key=key, text=text, path=str(tmp_path / f"{key}.wav"),
                            duration_s=0.5 if key == "upper_1" else 2.0)
             for key, text in script_lines("A", plan).items()}
    pictures = {i: WordPicture(index=i, path=str(tmp_path / f"word_{i}.png")) for i in (1, 2, 3)}

    props = compose("A", plan, pictures, lines, tmp_path, practice_seconds=4.0)

    segments = props["segments"]
    assert [s["kind"] for s in segments] == ["title", "trace", "practice", "trace", "practice",
                                             "word", "word", "word", "outro"]
    for before, after in zip(segments, segments[1:], strict=False):  # back to back, no gaps
        assert after["start"] == pytest.approx(before["start"] + before["duration"], abs=0.002)
    strokes = segments[1]["strokes"]
    assert strokes[0]["duration"] == pytest.approx(MIN_DRAW - 0.1)  # short line, still drawn slowly
    assert strokes[1]["start"] > strokes[0]["start"] + strokes[0]["duration"]
    clips = {clip["src"]: clip["start"] for clip in props["audio"]}
    assert clips["upper_2.wav"] == pytest.approx(strokes[1]["start"] - 0.1)
    assert segments[5]["image"] == "word_1.png"


def test_fake_tracing_video_renders_with_remotion(fake_ctx):
    graph = build_tracing_graph(InMemorySaver(serde=SERDE))
    studio_for(fake_ctx).store.start("ep-trace-B")
    config = {"configurable": {"thread_id": "ep-trace-B"}}

    final = graph.invoke({"episode_id": "ep-trace-B", "letter": "B"}, config, context=fake_ctx)

    folder = Path(fake_ctx.output_dir) / "episodes" / "ep-trace-B"
    props = json.loads((folder / "props.json").read_text("utf-8"))
    assert [idea.word for idea in final["plan"].words] == ["Ball", "Bear", "Banana"]
    assert final["status"] == "ready" and final["qa"].passed
    end = props["segments"][-1]["start"] + props["segments"][-1]["duration"]
    assert media_duration(folder / "video.mp4") == pytest.approx(end, abs=0.5)
    assert (folder / "thumbnail.jpg").exists()
