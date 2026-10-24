"""Editor: turns the pictures and voices into the finished video, plus captions. Code only.

Each picture gets a slow camera move, scenes crossfade, the voices are laid on one track, music
ducks under them, and the mix is normalized to YouTube's loudness in two passes.
"""

import zlib
from pathlib import Path
from typing import NamedTuple

from langgraph.runtime import Runtime

from kiddy.media import audio, ffmpeg
from kiddy.media.captions import write_srt
from kiddy.state import EpisodeState, SceneAudio, Script, latest_by_scene
from kiddy.studio import RunContext, Studio, get_studio

FADE = 0.5  # seconds of crossfade between two scenes
LEAD = 0.5  # quiet at the start of a scene, so its voice begins once the crossfade is done
TAIL = 0.7  # breathing room after the voice
MOVES = ("in", "right", "out", "left")
MUSIC_TYPES = ("*.mp3", "*.wav", "*.m4a", "*.ogg")


class Shot(NamedTuple):
    scene_id: int
    start: float  # when the scene starts fading in, in seconds from the start of the video
    length: float


def timeline(script: Script, voices: dict[int, SceneAudio], fps: int) -> list[Shot]:
    """Each scene lasts LEAD + its voice + TAIL (whole frames), overlapping the next by FADE."""
    shots, clock = [], 0.0
    for scene in script.scenes:
        length = round((LEAD + voices[scene.id].duration_s + TAIL) * fps) / fps
        shots.append(Shot(scene.id, clock, length))
        clock += length - FADE
    return shots


def editor(state: EpisodeState, runtime: Runtime[RunContext]) -> dict:
    studio = get_studio(runtime)
    video = studio.settings.video
    folder = studio.episode_dir(state["episode_id"])
    work = folder / "clips"
    work.mkdir(exist_ok=True)
    images, voices = latest_by_scene(state["images"]), latest_by_scene(state["audio"])
    shots = timeline(state["script"], voices, video.fps)
    total = shots[-1].start + shots[-1].length

    clips = []
    for index, shot in enumerate(shots):
        clip = work / f"scene_{shot.scene_id:02d}.mp4"
        ffmpeg.run(ffmpeg.motion_clip_args(
            Path(images[shot.scene_id].path), shot.length, clip,
            video.width, video.height, video.fps, MOVES[index % len(MOVES)],
        ))
        clips.append(clip)
    picture = work / "picture.mp4"
    ffmpeg.run(ffmpeg.crossfade_args(clips, [shot.start for shot in shots], FADE, picture))

    narration = audio.place(
        [(Path(voices[shot.scene_id].path), shot.start + LEAD) for shot in shots],
        total, work / "narration.wav",
    )
    mix = work / "mix.wav"
    ffmpeg.run(ffmpeg.mix_args(narration, pick_music(studio, state), total, mix))
    out = folder / "video.mp4"
    ffmpeg.run(ffmpeg.final_args(picture, mix, ffmpeg.measure_loudness(mix), out))

    captions = [
        t.model_copy(update={"start": t.start + offset, "end": t.end + offset})
        for shot in shots
        for offset in [shot.start + LEAD]
        for t in voices[shot.scene_id].sentences
    ]
    srt = write_srt(captions, folder / "captions.srt")
    return {"video_path": str(out), "captions_path": str(srt)}


def pick_music(studio: Studio, state: EpisodeState) -> Path | None:
    """A track from assets/music/<mood>/ if there is one, else from assets/music/; None if empty."""
    library = studio.assets_dir / "music"
    for folder in (library / state["brief"].mood.lower(), library):
        tracks = sorted(path for kind in MUSIC_TYPES for path in folder.glob(kind))
        if tracks:  # the same episode always gets the same track
            return tracks[zlib.crc32(state["episode_id"].encode()) % len(tracks)]
    return None
