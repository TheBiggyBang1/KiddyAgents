"""Episode folders on disk and the episodes table that remembers every episode."""

import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

COLUMNS = ("topic", "title", "learning_goal", "format", "status", "youtube_video_id", "tokens_used")


def new_episode_id() -> str:
    return datetime.now().strftime("ep-%Y%m%d-%H%M%S")


def save_json(path: Path, data: BaseModel) -> Path:
    path.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    return path


def write_once(out: Path, make: Callable[[Path], object]) -> Path:
    """Create `out` with make(temp_path) unless it exists: pay once, never keep half a file."""
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        part = out.with_name(f"{out.stem}.part{out.suffix}")
        make(part)
        part.replace(out)
    return out


class EpisodeStore:
    """The episodes table: what was made, so the showrunner never repeats itself."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            "create table if not exists episodes (id text primary key, topic text, title text,"
            " learning_goal text, format text, status text not null, youtube_video_id text,"
            " tokens_used integer default 0, created_at text not null)"
        )

    def start(self, episode_id: str) -> None:
        self._run(
            "insert or ignore into episodes (id, status, created_at) values (?, 'started', ?)",
            (episode_id, datetime.now().isoformat(timespec="seconds")),
        )

    def update(self, episode_id: str, **fields: str | int) -> None:
        unknown = set(fields) - set(COLUMNS)
        if unknown:
            raise ValueError(f"not episode columns: {sorted(unknown)}")
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self._run(f"update episodes set {assignments} where id = ?", (*fields.values(), episode_id))

    def recent(self, limit: int = 50) -> list[dict]:
        rows = self._run("select * from episodes order by created_at desc limit ?", (limit,))
        return [dict(row) for row in rows]

    def _run(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        # A short-lived connection per call, because nodes run on worker threads.
        db = sqlite3.connect(self.path)
        try:
            db.row_factory = sqlite3.Row
            rows = db.execute(sql, params).fetchall()
            db.commit()
            return rows
        finally:
            db.close()
