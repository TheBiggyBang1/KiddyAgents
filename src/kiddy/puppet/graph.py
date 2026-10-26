"""The puppet show's production line, from an idea to a video waiting for your approval."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from kiddy.approval import after_approval, approval, publisher
from kiddy.puppet import agents
from kiddy.puppet.models import PuppetState
from kiddy.studio import RunContext

MODEL_RETRY = RetryPolicy(max_attempts=2)
MEDIA_RETRY = RetryPolicy(max_attempts=3)


def build_puppet_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(PuppetState, context_schema=RunContext)
    g.add_node("writer", agents.writer, retry_policy=MODEL_RETRY)
    g.add_node("reviewer", agents.reviewer, retry_policy=MODEL_RETRY)
    g.add_node("discard", agents.discard)
    g.add_node("paint_cards", agents.paint_cards)
    g.add_node("card_painter", agents.card_painter, retry_policy=MEDIA_RETRY)
    g.add_node("voices", agents.voices, retry_policy=MEDIA_RETRY)
    g.add_node("composer", agents.composer)
    g.add_node("renderer", agents.renderer)
    g.add_node("thumbnail", agents.thumbnail)
    g.add_node("metadata_writer", agents.metadata_writer)
    g.add_node("qa_gate", agents.qa_gate)
    g.add_node("approval", approval)
    g.add_node("publisher", publisher)

    g.add_edge(START, "writer")
    g.add_edge("writer", "reviewer")
    g.add_conditional_edges("reviewer", agents.after_review, ["writer", "paint_cards", "discard"])
    g.add_edge("discard", END)
    g.add_conditional_edges("paint_cards", agents.paint_each_card, ["card_painter", "voices"])
    g.add_edge("card_painter", "voices")
    for before, after in [("voices", "composer"), ("composer", "renderer"),
                          ("renderer", "thumbnail"), ("thumbnail", "metadata_writer"),
                          ("metadata_writer", "qa_gate"), ("qa_gate", "approval")]:
        g.add_edge(before, after)
    g.add_conditional_edges("approval", after_approval, ["publisher", END])
    g.add_edge("publisher", END)
    return g.compile(checkpointer=checkpointer)


graph = build_puppet_graph()  # what `langgraph dev` and LangGraph Studio load
