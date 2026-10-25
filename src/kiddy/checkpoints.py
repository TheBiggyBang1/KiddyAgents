"""Where runs are saved between steps, so a stopped run resumes instead of starting over."""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from kiddy.state import CHECKPOINT_TYPES
from kiddy.tracing.models import TRACING_TYPES

# Strict loading: checkpoints may only rebuild LangGraph's own types and Kiddy's state models.
SERDE = JsonPlusSerializer(allowed_msgpack_modules=None).with_msgpack_allowlist(
    CHECKPOINT_TYPES + TRACING_TYPES
)


def sqlite_checkpointer(path: Path) -> SqliteSaver:
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False), serde=SERDE)
