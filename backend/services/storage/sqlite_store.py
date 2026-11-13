from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Lock

from .base import TaskStore
from .models import Task, is_valid_task_id, task_from_dict, task_to_dict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL
)
"""

# Legacy database filename from ADR-0003 (tasks-only era).
_LEGACY_DB_NAME = "tasks.db"


def ensure_db_path(db_path: Path) -> Path:
    """Resolve the database path, migrating the legacy tasks.db once.

    The database was renamed tasks.db → videobrain.db when it grew beyond
    tasks (ADR-0005). If the legacy file exists and the new one does not,
    it is moved (os.replace, same directory). If both exist, the new path
    wins and the legacy file is left untouched.
    """
    db_path = Path(db_path)
    legacy = db_path.parent / _LEGACY_DB_NAME
    if db_path.name != _LEGACY_DB_NAME and legacy.exists() and not db_path.exists():
        try:
            os.replace(legacy, db_path)
            print(f"📦 Migrated database: {legacy} -> {db_path}")
        except OSError as exc:
            print(f"⚠️ Could not migrate legacy database {legacy}: {exc}")
    return db_path


class SqliteTaskStore(TaskStore):
    """SQLite TaskStore backend.

    The table stores opaque serialized records: SQL never interprets the
    payload — serialization/deserialization stays in storage.models
    (task_to_dict / task_from_dict), so no business logic lives in SQL.

    Writes are atomic: each save is a single INSERT OR REPLACE statement
    committed as one transaction. Connections are opened per operation
    (WAL journal), guarded by a lock — safe for concurrent callers.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = ensure_db_path(db_path)
        self._lock = Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(_SCHEMA)

    def save(self, task: Task) -> None:
        if not is_valid_task_id(task.id):
            raise ValueError(f"Unsafe task id rejected: {task.id!r}")

        record = task_to_dict(task)
        payload = json.dumps(record, ensure_ascii=False)

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    with conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO tasks (id, schema_version, payload) "
                            "VALUES (?, ?, ?)",
                            (task.id, record["schema_version"], payload),
                        )
            except Exception as exc:
                # Persistence failures must not crash the worker; same
                # tolerance policy as JsonTaskStore.
                print(f"⚠️ Failed to persist task {task.id}: {exc}")

    def load(self, task_id: str) -> Task | None:
        if not is_valid_task_id(task_id):
            print(f"⚠️ Refusing to load task: unsafe id {task_id!r}")
            return None

        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT payload FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
        except Exception as exc:
            print(f"⚠️ Failed to load task {task_id}: {exc}")
            return None

        if row is None:
            return None

        try:
            return task_from_dict(json.loads(row[0]))
        except Exception as exc:
            print(f"⚠️ Failed to deserialize task {task_id}: {exc}")
            return None

    def list_ids(self) -> list[str]:
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute("SELECT id FROM tasks ORDER BY id").fetchall()
            return [row[0] for row in rows]
        except Exception as exc:
            print(f"⚠️ Failed to list task ids: {exc}")
            return []

    def delete(self, task_id: str) -> bool:
        if not is_valid_task_id(task_id):
            print(f"⚠️ Refusing to delete task: unsafe id {task_id!r}")
            return False
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    result = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                    return result.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
