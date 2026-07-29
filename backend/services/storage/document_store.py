from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from pathlib import Path
from threading import Lock

from .document_models import Document, document_from_dict, document_to_dict
from .models import is_valid_task_id as _is_safe_id  # generic safe-id check
from .sqlite_store import ensure_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL
)
"""


class DocumentStore(ABC):
    """Persistence contract for documents (sibling of TaskStore).

    Same conventions: save() is an atomic upsert; load() returns None for
    missing or unreadable records; unsafe ids are rejected.
    """

    @abstractmethod
    def save(self, document: Document) -> None:
        raise NotImplementedError()

    @abstractmethod
    def load(self, document_id: str) -> Document | None:
        raise NotImplementedError()


class SqliteDocumentStore(DocumentStore):
    """SQLite DocumentStore. Opaque payloads; SQL never interprets content."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = ensure_db_path(db_path)
        self._lock = Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(_SCHEMA)

    def save(self, document: Document) -> None:
        if not _is_safe_id(document.id):
            raise ValueError(f"Unsafe document id rejected: {document.id!r}")

        record = document_to_dict(document)
        payload = json.dumps(record, ensure_ascii=False)

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    with conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO documents (id, schema_version, payload) "
                            "VALUES (?, ?, ?)",
                            (document.id, record["schema_version"], payload),
                        )
            except Exception as exc:
                print(f"⚠️ Failed to persist document {document.id}: {exc}")

    def load(self, document_id: str) -> Document | None:
        if not _is_safe_id(document_id):
            print(f"⚠️ Refusing to load document: unsafe id {document_id!r}")
            return None

        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT payload FROM documents WHERE id = ?", (document_id,)
                ).fetchone()
        except Exception as exc:
            print(f"⚠️ Failed to load document {document_id}: {exc}")
            return None

        if row is None:
            return None

        try:
            return document_from_dict(json.loads(row[0]))
        except Exception as exc:
            print(f"⚠️ Failed to deserialize document {document_id}: {exc}")
            return None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
