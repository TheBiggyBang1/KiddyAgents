"""The production line: which agent hands its work to which."""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send

from kiddy.nodes.art_director import art_director
from kiddy.nodes.editor import editor
from kiddy.nodes.escalate import escalate
from kiddy.nodes.human_approval import human_approval
from kiddy.nodes.illustrator import illustrator
from kiddy.nodes.metadata_writer import metadata_writer
from kiddy.nodes.narrator import narrator
from kiddy.nodes.publisher import publisher
from kiddy.nodes.qa_gate import qa_gate
from kiddy.nodes.safety_reviewer import safety_reviewer
from kiddy.nodes.scriptwriter import scriptwriter
from kiddy.nodes.showrunner import showrunner
from kiddy.nodes.thumbnail_artist import thumbnail_artist
from kiddy.state import CHECKPOINT_TYPES, EpisodeState
from kiddy.studio import RunContext

MAX_SCRIPT_ATTEMPTS = 3
MODEL_RETRY = RetryPolicy(max_attempts=2)  # each attempt may already ask the model twice
MEDIA_RETRY = RetryPolicy(max_attempts=3)

# Strict loading: checkpoints may only rebuild LangGraph's own types and Kiddy's state models.
SERDE = JsonPlusSerializer(allowed_msgpack_modules=None).with_msgpack_allowlist(CHECKPOINT_TYPES)


def after_review(state: EpisodeState) -> str:
    review = state["review"]
    if review.passed and not review.issues:
        return "art_director"
    if state.get("script_attempts", 0) < MAX_SCRIPT_ATTEMPTS:
        return "scriptwriter"  # fix blockers, and polish smaller issues while tries remain
    # Out of tries: small leftover issues may ship; blockers go to a human.
    return "art_director" if review.passed else "escalate"


def paint_each_scene(state: EpisodeState) -> list[Send]:
    prompts = {p.scene_id: p for p in state["art_plan"].prompts}
    return [
        Send("illustrator", {"episode_id": state["episode_id"], "scene": scene,
                             "prompt": prompts[scene.id].prompt,
                             "references": prompts[scene.id].references})
        for scene in state["script"].scenes
    ]


def images_done(state: EpisodeState) -> dict:
    """Join point: runs once, after every illustrator task has finished."""
    return {}


def voice_each_scene(state: EpisodeState) -> list[Send]:
    return [
        Send("narrator", {"episode_id": state["episode_id"], "scene": scene, "prompt": "",
                          "references": []})
        for scene in state["script"].scenes
    ]


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(EpisodeState, context_schema=RunContext)
    g.add_node("showrunner", showrunner, retry_policy=MODEL_RETRY)
    g.add_node("scriptwriter", scriptwriter, retry_policy=MODEL_RETRY)
    g.add_node("safety_reviewer", safety_reviewer, retry_policy=MODEL_RETRY)
    g.add_node("escalate", escalate)
    g.add_node("art_director", art_director)
    g.add_node("illustrator", illustrator, retry_policy=MEDIA_RETRY)
    g.add_node("images_done", images_done)
    g.add_node("narrator", narrator, retry_policy=MEDIA_RETRY)
    g.add_node("editor", editor)
    g.add_node("thumbnail_artist", thumbnail_artist)
    g.add_node("metadata_writer", metadata_writer)
    g.add_node("qa_gate", qa_gate)
    g.add_node("human_approval", human_approval)
    g.add_node("publisher", publisher)

    g.add_edge(START, "showrunner")
    g.add_edge("showrunner", "scriptwriter")
    g.add_edge("scriptwriter", "safety_reviewer")
    g.add_conditional_edges(
        "safety_reviewer", after_review, ["scriptwriter", "art_director", "escalate"]
    )
    g.add_edge("escalate", END)
    g.add_conditional_edges("art_director", paint_each_scene, ["illustrator"])
    g.add_edge("illustrator", "images_done")
    g.add_conditional_edges("images_done", voice_each_scene, ["narrator"])
    g.add_edge("narrator", "editor")
    g.add_edge("editor", "thumbnail_artist")
    g.add_edge("thumbnail_artist", "metadata_writer")
    g.add_edge("metadata_writer", "qa_gate")
    g.add_edge("qa_gate", "human_approval")
    g.add_edge("human_approval", "publisher")
    g.add_edge("publisher", END)
    return g.compile(checkpointer=checkpointer)


def sqlite_checkpointer(path: Path) -> SqliteSaver:
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False), serde=SERDE)


graph = build_graph()  # what `langgraph dev` and LangGraph Studio load
