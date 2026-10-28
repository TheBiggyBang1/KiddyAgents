import json
import math
import wave
from array import array
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from kiddy.checkpoints import SERDE
from kiddy.media.audio import mouth_envelope, write_silence
from kiddy.media.ffmpeg import media_duration
from kiddy.providers import fixtures
from kiddy.providers.fixtures import beat, say
from kiddy.providers.llm import BadModelOutput, FakeLLM
from kiddy.puppet.agents import tidy
from kiddy.puppet.compose import INTRO, compose
from kiddy.puppet.graph import build_puppet_graph
from kiddy.puppet.models import CardPicture, EpisodeIdea, PuppetScene, PuppetScript, SpokenLine
from kiddy.showrunner import next_idea
from kiddy.studio import studio_for


def script_of(*scenes: PuppetScene) -> PuppetScript:
    return PuppetScript(title="T", learning_goal="G", fact_claims=[], scenes=list(scenes))


def test_tidy_keeps_only_beats_the_stage_can_perform(settings):
    scene = PuppetScene(background="meadow", cast=["Fennel", "a dragon"], beats=[
        say("fennel", "Hello!"),
        say("glim", "I fly in to talk!"),          # not in the cast yet: steps onto the stage
        beat("act", "olo", action=None),           # an act without an action
        say("nobody", "Who am I?"),                # unknown speaker
        beat("word", text="Supercalifragilistic"),  # too long to show big
        *[beat("card", card=f"picture {n}") for n in range(7)],  # only 5 cards are painted
    ])
    tidied = tidy(script_of(scene), settings).scenes[0]
    assert tidied.cast == ["fennel", "glim"]
    assert [b.kind for b in tidied.beats] == ["say", "say", *["card"] * 5]
    with pytest.raises(BadModelOutput):
        tidy(script_of(PuppetScene(background="home", cast=["olo"], beats=[])), settings)


def test_timeline_plays_lines_in_order_and_shows_cards_until_the_next_word(tmp_path):
    scene = PuppetScene(background="home", cast=["fennel", "olo"], beats=[
        say("fennel", "Look!"), beat("card", card="a red ball"), say("olo", "A ball."),
        beat("act", "olo", action="nod"), beat("word", text="Ball"),
    ])
    lines = {key: SpokenLine(key=key, character=who, text="x", path=str(tmp_path / f"{key}.wav"),
                             duration_s=2.0, mouth=[0.5] * 60)
             for key, who in (("s1_b1", "fennel"), ("s1_b3", "olo"))}
    cards = {"a red ball": CardPicture(index=1, description="a red ball",
                                       path=str(tmp_path / "card_1.png"))}

    props = compose(script_of(scene), lines, cards, tmp_path)

    stage = props["stages"][0]
    assert stage["start"] == INTRO
    fennel, olo = stage["actors"]
    assert (fennel["x"], olo["x"]) == (500, 1420)
    assert olo["talks"][0]["start"] > fennel["talks"][0]["start"] + 2.0  # one after the other
    assert olo["acts"][0]["action"] == "nod"
    card, word = stage["cards"][0], stage["words"][0]
    assert card["image"] == "card_1.png" and card["end"] == word["start"]  # the word replaces it
    assert stage["start"] + stage["duration"] >= word["end"]


def test_mouth_follows_the_voice(tmp_path):
    loud = tmp_path / "tone.wav"
    with wave.open(str(loud), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)
        tone = [int(8000 * math.sin(i / 8) * (i // 12_000 % 2)) for i in range(48_000)]
        wav.writeframes(array("h", tone).tobytes())  # half a second quiet, half loud, ...
    mouth = mouth_envelope(loud, fps=30)
    assert len(mouth) == 60 and max(mouth) > 0.8
    assert mouth[5] == 0.0 and mouth[25] > 0.5  # shut in the quiet part, open in the loud one
    assert set(mouth_envelope(write_silence(tmp_path / "s.wav", 1.0), fps=30)) == {0.0}


def test_showrunner_never_repeats_and_retires_tracing_when_the_alphabet_is_done(fake_ctx,
                                                                                 monkeypatch):
    studio = studio_for(fake_ctx)
    first, _ = next_idea(studio)
    studio.store.start("ep-1-show", format="puppet", topic=first.topic, subject=first.subject)
    second, _ = next_idea(studio)
    assert second.topic != first.topic

    for n, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        studio.store.start(f"ep-t{n}-{letter}", format="tracing", topic=f"letter {letter}",
                           status="approved")
    tracing = EpisodeIdea(format="tracing", subject="letters and sounds", topic="letter A",
                          learning_goal="g", letter="A", why="w")
    penguins = tracing.model_copy(update={"format": "puppet", "letter": None,
                                          "topic": "how penguins keep warm", "subject": "animals"})
    asked = []

    def wants_tracing(self, agent, schema, system, user, images=()):
        asked.append(user)
        return (tracing if len(asked) == 1 else penguins), 0

    monkeypatch.setattr(FakeLLM, "structured", wants_tracing)
    idea, _ = next_idea(studio)
    assert idea.format == "puppet"  # all 26 letters done: a story instead of failing
    assert "tracing" not in asked[1].split("formats:")[1].split("tracing_rule")[0]


def test_showrunner_can_be_limited_to_puppet_shows(fake_ctx, monkeypatch):
    tracing = EpisodeIdea(format="tracing", subject="letters and sounds", topic="letter D",
                          learning_goal="g", letter="D", why="w")
    bees = tracing.model_copy(update={"format": "puppet", "letter": None,
                                      "topic": "how bees make honey", "subject": "animals"})
    asked = []

    def ignores_the_offer(self, agent, schema, system, user, images=()):
        asked.append(user)
        return (tracing if len(asked) == 1 else bees), 0

    monkeypatch.setattr(FakeLLM, "structured", ignores_the_offer)
    idea, _ = next_idea(studio_for(fake_ctx), only="puppet")
    assert idea.format == "puppet" and len(asked) == 2  # the tracing answer was sent back
    assert "tracing" not in asked[0].split("formats:")[1].split("tracing_rule")[0]


def test_fake_puppet_show_renders_then_waits_for_approval(fake_ctx):
    graph = build_puppet_graph(InMemorySaver(serde=SERDE))
    studio = studio_for(fake_ctx)
    idea = fixtures.episode_idea("")
    studio.store.start("ep-show", format="puppet", topic=idea.topic, subject=idea.subject)
    config = {"configurable": {"thread_id": "ep-show"}}

    graph.invoke({"episode_id": "ep-show", "idea": idea}, config, context=fake_ctx)

    assert graph.get_state(config).next == ("approval",)
    assert studio.store.get("ep-show")["status"] == "awaiting_approval"
    folder = Path(fake_ctx.output_dir) / "episodes" / "ep-show"
    props = json.loads((folder / "props.json").read_text("utf-8"))
    end = props["stages"][-1]["start"] + props["stages"][-1]["duration"]
    assert media_duration(folder / "video.mp4") == pytest.approx(end, abs=0.5)
    assert (folder / "cards" / "card_1.png").exists() and (folder / "thumbnail.jpg").exists()

    final = graph.invoke(Command(resume={"approved": False, "notes": "Too much talking."}),
                         config, context=fake_ctx)
    assert final["status"] == "rejected"
    assert studio.store.get("ep-show")["notes"] == "Too much talking."  # the next ideas see it
