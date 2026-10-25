"""The tracing video's production line."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from kiddy.studio import RunContext
from kiddy.tracing import agents
from kiddy.tracing.models import TracingState

MODEL_RETRY = RetryPolicy(max_attempts=2)
MEDIA_RETRY = RetryPolicy(max_attempts=3)


def build_tracing_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(TracingState, context_schema=RunContext)
    g.add_node("planner", agents.planner, retry_policy=MODEL_RETRY)
    g.add_node("painter", agents.painter, retry_policy=MEDIA_RETRY)
    g.add_node("pictures_done", agents.pictures_done)
    g.add_node("narrator", agents.narrator, retry_policy=MEDIA_RETRY)
    g.add_node("composer", agents.composer)
    g.add_node("renderer", agents.renderer)
    g.add_node("thumbnail", agents.thumbnail)
    g.add_node("metadata_writer", agents.metadata_writer)
    g.add_node("qa_gate", agents.qa_gate)
    g.add_node("publisher", agents.publisher)

    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", agents.paint_each_word, ["painter"])
    g.add_edge("painter", "pictures_done")
    for before, after in [
        ("pictures_done", "narrator"), ("narrator", "composer"), ("composer", "renderer"),
        ("renderer", "thumbnail"), ("thumbnail", "metadata_writer"),
        ("metadata_writer", "qa_gate"), ("qa_gate", "publisher"), ("publisher", END),
    ]:
        g.add_edge(before, after)
    return g.compile(checkpointer=checkpointer)


graph = build_tracing_graph()  # what `langgraph dev` and LangGraph Studio load
