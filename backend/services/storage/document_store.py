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

    @abstractmethod
    def list_ids(self) -> list[str]:
        """Return ids of all persisted documents (order unspecified)."""
        raise NotImplementedError()

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Delete a document record. Returns True when a row was removed."""
        raise NotImplementedError()

    @abstractmethod
    def update(
        self,
        document_id: str,
        *,
        pinned: bool | None = None,
        title: str | None = None,
    ) -> bool:
        """Patch mutable fields (pinned/title). Returns False when missing."""
        raise NotImplementedError()

    def find_by_content_hash(self, content_hash: str | None) -> Document | None:
        """First document with this content hash, else None.

        Concrete lookup built on list_ids/load so every implementation gets
        it for free; the payload stays opaque (no schema migration needed).
        """
        if not content_hash:
            return None
        for document_id in self.list_ids():
            document = self.load(document_id)
            if document is not None and document.content_hash == content_hash:
                return document
        return None

    def find_by_origin_uri(self, origin_uri: str | None) -> Document | None:
        """First document with this origin uri, else None."""
        if not origin_uri:
            return None
        for document_id in self.list_ids():
            document = self.load(document_id)
            if document is not None and document.origin_uri == origin_uri:
                return document
        return None


class SqliteDocumentStore(DocumentStore):
    """SQLite DocumentStore. Opaque payloads; the only SQL-visible content
    is the ``pinned`` flag column, kept in sync with the payload by save()."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = ensure_db_path(db_path)
        self._lock = Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(_SCHEMA)
                self._migrate_documents_pinned(conn)

    @staticmethod
    def _migrate_documents_pinned(conn: sqlite3.Connection) -> None:
        """Lazy migration: add the ``pinned`` column to older databases.

        Same pattern as ``_migrate_notes_nullable_document``: inspect the
        table via PRAGMA and ALTER only when the column is missing.
        """
        cols = conn.execute("PRAGMA table_info(documents)").fetchall()
        if any(c[1] == "pinned" for c in cols):
            return
        conn.execute(
            "ALTER TABLE documents ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
        )

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
                            "INSERT OR REPLACE INTO documents (id, schema_version, payload, pinned) "
                            "VALUES (?, ?, ?, ?)",
                            (document.id, record["schema_version"], payload, int(document.pinned)),
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

    def list_ids(self) -> list[str]:
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute("SELECT id FROM documents").fetchall()
        except Exception as exc:
            print(f"⚠️ Failed to list documents: {exc}")
            return []
        return [row[0] for row in rows]

    def delete(self, document_id: str) -> bool:
        if not _is_safe_id(document_id):
            print(f"⚠️ Refusing to delete document: unsafe id {document_id!r}")
            return False
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    result = conn.execute(
                        "DELETE FROM documents WHERE id = ?", (document_id,)
                    )
                    return result.rowcount > 0

    def update(
        self,
        document_id: str,
        *,
        pinned: bool | None = None,
        title: str | None = None,
    ) -> bool:
        document = self.load(document_id)
        if document is None:
            return False
        if pinned is not None:
            document.pinned = pinned
        if title is not None:
            document.title = title
        self.save(document)
        return True

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
