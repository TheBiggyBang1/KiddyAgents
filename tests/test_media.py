from pathlib import Path

import pytest

from kiddy.media.audio import duration, join, place, sentence_timings, write_silence
from kiddy.media.captions import srt_time
from kiddy.media.ffmpeg import (
    crossfade_args,
    final_args,
    loudnorm_filter,
    mix_args,
    motion_clip_args,
)
from kiddy.nodes.editor import FADE, LEAD, TAIL, timeline
from kiddy.nodes.thumbnail_artist import headline
from kiddy.providers import fixtures
from kiddy.state import SceneAudio, Script


def arg(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


def test_motion_clip_upscales_then_moves_for_every_frame():
    args = motion_clip_args(Path("a.png"), 4.0, Path("a.mp4"), 1920, 1080, 30, "in")
    motion = arg(args, "-vf")
    assert motion.startswith("scale=3840:2160,zoompan=")  # upscaled first: no jitter
    assert "d=120:s=1920x1080:fps=30" in motion and arg(args, "-frames:v") == "120"
    assert "-an" in args


def test_crossfade_starts_each_clip_where_the_timeline_says():
    clips = [Path("1.mp4"), Path("2.mp4"), Path("3.mp4")]
    graph = arg(crossfade_args(clips, [0.0, 9.5, 20.0], 0.5, Path("v.mp4")), "-filter_complex")
    assert "[0:v][1:v]xfade=transition=fade:duration=0.5:offset=9.500[v1]" in graph
    assert "[v1][2:v]xfade=transition=fade:duration=0.5:offset=20.000[v2]" in graph


def test_music_ducks_under_the_voice_and_fades_out():
    graph = arg(mix_args(Path("n.wav"), Path("m.mp3"), 60.0, Path("mix.wav")), "-filter_complex")
    assert "[bed][key]sidechaincompress" in graph
    assert "afade=t=out:st=57.000:d=3" in graph
    assert arg(mix_args(Path("n.wav"), None, 60.0, Path("mix.wav")), "-ar") == "48000"


def test_second_loudness_pass_uses_the_measurements():
    measured = {"input_i": "-20.1", "input_tp": "-4.0", "input_lra": "5.0",
                "input_thresh": "-30.4", "target_offset": "0.3"}
    second_pass = loudnorm_filter(measured)
    assert "measured_I=-20.1" in second_pass and "linear=true" in second_pass
    assert arg(final_args(Path("v.mp4"), Path("a.wav"), None, Path("o.mp4")), "-af") == "anull"


def test_timeline_overlaps_scenes_by_the_crossfade():
    script = fixtures.answer(Script)
    voices = {s.id: SceneAudio(scene_id=s.id, path="", duration_s=10.0, sentences=[])
              for s in script.scenes}
    shots = timeline(script, voices, fps=10)
    assert shots[0].length == pytest.approx(LEAD + 10.0 + TAIL)
    assert shots[1].start == pytest.approx(shots[0].length - FADE)


def test_place_drops_voices_in_at_their_offsets(tmp_path):
    voice = write_silence(tmp_path / "v.wav", 1.0)
    track = place([(voice, 0.5), (voice, 3.0)], 5.0, tmp_path / "t.wav")
    assert duration(track) == pytest.approx(5.0)


def test_srt_time():
    assert srt_time(0) == "00:00:00,000"
    assert srt_time(3661.5) == "01:01:01,500"


def test_sentence_timings_fill_the_line():
    timings = sentence_timings("Hi there. How are you today?", start=2.0, seconds=4.0)
    assert [t.text for t in timings] == ["Hi there.", "How are you today?"]
    assert timings[0].start == 2.0
    assert timings[-1].end == pytest.approx(6.0)


def test_join_puts_a_pause_between_lines(tmp_path):
    first = write_silence(tmp_path / "a.wav", 1.0)
    second = write_silence(tmp_path / "b.wav", 2.0)
    assert duration(join([first, second], tmp_path / "ab.wav", gap=0.5)) == pytest.approx(3.5)


def test_headline_turns_a_topic_into_cover_words():
    assert headline("how do bees make honey") == "How Do Bees Make Honey?"
    assert headline("the water cycle!") == "The Water Cycle"
