from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from pathlib import Path
from threading import Lock

from .knowledge_models import (
    Enrichment,
    KnowledgeChunk,
    chunk_from_dict,
    chunk_to_dict,
    enrichment_from_dict,
    enrichment_to_dict,
)
from .models import is_valid_task_id as _is_safe_id  # generic safe-id check
from .sqlite_store import ensure_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON knowledge_chunks(document_id);
CREATE TABLE IF NOT EXISTS enrichments (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_enrichments_owner
    ON enrichments(scope, owner_id, type);
"""


class KnowledgeStore(ABC):
    """Persistence contract for knowledge chunks and enrichments.

    Same conventions as TaskStore/DocumentStore: atomic writes, None on
    missing/unreadable, unsafe ids rejected.
    """

    @abstractmethod
    def save_chunks(self, document_id: str, chunks: list[KnowledgeChunk]) -> None:
        """Replace the document's chunk set atomically.

        Deletes the document's existing chunks AND their chunk-scoped
        enrichments (frozen cascade rule, ADR-0004), then inserts the new
        set — one transaction. Document-scoped enrichments survive.
        """
        raise NotImplementedError()

    @abstractmethod
    def load_chunks(self, document_id: str) -> list[KnowledgeChunk]:
        """Return the document's chunks ordered by ordinal."""
        raise NotImplementedError()

    @abstractmethod
    def save_enrichment(self, enrichment: Enrichment) -> None:
        raise NotImplementedError()

    @abstractmethod
    def load_enrichments(
        self, scope: str, owner_id: str, type: str | None = None
    ) -> list[Enrichment]:
        """Return enrichments for an owner, newest first, optionally by type."""
        raise NotImplementedError()


class SqliteKnowledgeStore(KnowledgeStore):
    """SQLite KnowledgeStore. Opaque payloads; keys live in columns."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = ensure_db_path(db_path)
        self._lock = Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL")
                for statement in _SCHEMA.split(";"):
                    if statement.strip():
                        conn.execute(statement)

    def save_chunks(self, document_id: str, chunks: list[KnowledgeChunk]) -> None:
        if not _is_safe_id(document_id):
            raise ValueError(f"Unsafe document id rejected: {document_id!r}")
        for chunk in chunks:
            if not _is_safe_id(chunk.id):
                raise ValueError(f"Unsafe chunk id rejected: {chunk.id!r}")

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    with conn:
                        # Cascade: chunk-scoped enrichments die with their chunks.
                        conn.execute(
                            "DELETE FROM enrichments WHERE scope = 'chunk' AND owner_id IN "
                            "(SELECT id FROM knowledge_chunks WHERE document_id = ?)",
                            (document_id,),
                        )
                        conn.execute(
                            "DELETE FROM knowledge_chunks WHERE document_id = ?",
                            (document_id,),
                        )
                        for chunk in chunks:
                            record = chunk_to_dict(chunk)
                            conn.execute(
                                "INSERT OR REPLACE INTO knowledge_chunks "
                                "(id, document_id, ordinal, schema_version, payload) "
                                "VALUES (?, ?, ?, ?, ?)",
                                (
                                    chunk.id,
                                    document_id,
                                    chunk.ordinal,
                                    record["schema_version"],
                                    json.dumps(record, ensure_ascii=False),
                                ),
                            )
            except Exception as exc:
                print(f"⚠️ Failed to persist chunks for document {document_id}: {exc}")

    def load_chunks(self, document_id: str) -> list[KnowledgeChunk]:
        if not _is_safe_id(document_id):
            print(f"⚠️ Refusing to load chunks: unsafe document id {document_id!r}")
            return []

        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    "SELECT payload FROM knowledge_chunks WHERE document_id = ? "
                    "ORDER BY ordinal",
                    (document_id,),
                ).fetchall()
        except Exception as exc:
            print(f"⚠️ Failed to load chunks for document {document_id}: {exc}")
            return []

        chunks: list[KnowledgeChunk] = []
        for (payload,) in rows:
            try:
                chunks.append(chunk_from_dict(json.loads(payload)))
            except Exception as exc:
                print(f"⚠️ Skipping corrupt chunk for document {document_id}: {exc}")
        return chunks

    def save_enrichment(self, enrichment: Enrichment) -> None:
        if not _is_safe_id(enrichment.id) or not _is_safe_id(enrichment.owner_id):
            raise ValueError(f"Unsafe enrichment/owner id rejected: {enrichment.id!r}")

        record = enrichment_to_dict(enrichment)
        payload = json.dumps(record, ensure_ascii=False)

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    with conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO enrichments "
                            "(id, scope, owner_id, type, schema_version, payload) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                enrichment.id,
                                enrichment.scope,
                                enrichment.owner_id,
                                enrichment.type,
                                record["schema_version"],
                                payload,
                            ),
                        )
            except Exception as exc:
                print(f"⚠️ Failed to persist enrichment {enrichment.id}: {exc}")

    def load_enrichments(
        self, scope: str, owner_id: str, type: str | None = None
    ) -> list[Enrichment]:
        if not _is_safe_id(owner_id):
            print(f"⚠️ Refusing to load enrichments: unsafe owner id {owner_id!r}")
            return []

        query = "SELECT payload FROM enrichments WHERE scope = ? AND owner_id = ?"
        params: list = [scope, owner_id]
        if type is not None:
            query += " AND type = ?"
            params.append(type)
        query += " ORDER BY rowid DESC"  # insertion order = newest first

        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(query, params).fetchall()
        except Exception as exc:
            print(f"⚠️ Failed to load enrichments for {owner_id}: {exc}")
            return []

        enrichments: list[Enrichment] = []
        for (payload,) in rows:
            try:
                enrichments.append(enrichment_from_dict(json.loads(payload)))
            except Exception as exc:
                print(f"⚠️ Skipping corrupt enrichment for {owner_id}: {exc}")
        return enrichments

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
