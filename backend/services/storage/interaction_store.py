from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from pathlib import Path
from threading import Lock

from .interaction_models import (
    ChatConversation,
    ChatMessage,
    Highlight,
    Note,
    conversation_from_dict,
    conversation_to_dict,
    highlight_from_dict,
    highlight_to_dict,
    message_from_dict,
    message_to_dict,
    note_from_dict,
    note_to_dict,
)
from .models import is_valid_task_id as _is_safe_id
from .sqlite_store import ensure_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_conversations (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_document
    ON chat_conversations(document_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_created
    ON chat_messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_id TEXT,
    note_text TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_notes_document ON notes(document_id);

CREATE TABLE IF NOT EXISTS highlights (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    color TEXT NOT NULL,
    text TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_highlights_document ON highlights(document_id);
CREATE INDEX IF NOT EXISTS idx_highlights_chunk ON highlights(chunk_id);
"""


class ChatStore(ABC):
    """Persistence contract for chat conversations and messages."""

    @abstractmethod
    def save_conversation(self, conversation: ChatConversation) -> None:
        raise NotImplementedError()

    @abstractmethod
    def load_conversation(self, conversation_id: str) -> ChatConversation | None:
        raise NotImplementedError()

    @abstractmethod
    def list_conversations(self, document_id: str) -> list[ChatConversation]:
        raise NotImplementedError()

    @abstractmethod
    def save_message(self, message: ChatMessage) -> None:
        raise NotImplementedError()

    @abstractmethod
    def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        raise NotImplementedError()


class NoteStore(ABC):
    """Persistence contract for user notes."""

    @abstractmethod
    def save_note(self, note: Note) -> None:
        raise NotImplementedError()

    @abstractmethod
    def load_note(self, note_id: str) -> Note | None:
        raise NotImplementedError()

    @abstractmethod
    def list_notes(self, document_id: str) -> list[Note]:
        raise NotImplementedError()

    @abstractmethod
    def delete_note(self, note_id: str) -> bool:
        raise NotImplementedError()


class HighlightStore(ABC):
    """Persistence contract for text highlights."""

    @abstractmethod
    def save_highlight(self, highlight: Highlight) -> None:
        raise NotImplementedError()

    @abstractmethod
    def load_highlight(self, highlight_id: str) -> Highlight | None:
        raise NotImplementedError()

    @abstractmethod
    def list_highlights(self, document_id: str) -> list[Highlight]:
        raise NotImplementedError()

    @abstractmethod
    def delete_highlight(self, highlight_id: str) -> bool:
        raise NotImplementedError()


class InteractionStore(ChatStore, NoteStore, HighlightStore):
    """Combined interface for backward compatibility.

    Prefer the focused sub-interfaces (ChatStore / NoteStore / HighlightStore)
    as service dependencies so ISP is respected.  The single SQLite backend
    implements all three, so passing SqliteInteractionStore anywhere an
    individual sub-interface is expected is always valid.
    """


class SqliteInteractionStore(InteractionStore):
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

    def save_conversation(self, conversation: ChatConversation) -> None:
        if not _is_safe_id(conversation.id) or not _is_safe_id(conversation.document_id):
            raise ValueError(f"Unsafe conversation/document id rejected: {conversation.id!r}")
        record = conversation_to_dict(conversation)
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO chat_conversations "
                        "(id, document_id, schema_version, payload, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            conversation.id,
                            conversation.document_id,
                            record["schema_version"],
                            json.dumps(record, ensure_ascii=False),
                            conversation.created_at,
                            conversation.updated_at,
                        ),
                    )

    def load_conversation(self, conversation_id: str) -> ChatConversation | None:
        if not _is_safe_id(conversation_id):
            return None
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload FROM chat_conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return conversation_from_dict(json.loads(row[0]))

    def list_conversations(self, document_id: str) -> list[ChatConversation]:
        if not _is_safe_id(document_id):
            return []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload FROM chat_conversations WHERE document_id = ? "
                "ORDER BY updated_at DESC, created_at DESC",
                (document_id,),
            ).fetchall()
        return [conversation_from_dict(json.loads(row[0])) for row in rows]

    def save_message(self, message: ChatMessage) -> None:
        if not _is_safe_id(message.id) or not _is_safe_id(message.conversation_id):
            raise ValueError(f"Unsafe message/conversation id rejected: {message.id!r}")
        record = message_to_dict(message)
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO chat_messages "
                        "(id, conversation_id, schema_version, payload, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            message.id,
                            message.conversation_id,
                            record["schema_version"],
                            json.dumps(record, ensure_ascii=False),
                            message.created_at,
                        ),
                    )

    def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        if not _is_safe_id(conversation_id):
            return []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload FROM chat_messages WHERE conversation_id = ? "
                "ORDER BY created_at ASC, rowid ASC",
                (conversation_id,),
            ).fetchall()
        return [message_from_dict(json.loads(row[0])) for row in rows]

    def save_note(self, note: Note) -> None:
        if not _is_safe_id(note.id) or not _is_safe_id(note.document_id):
            raise ValueError(f"Unsafe note/document id rejected: {note.id!r}")
        if note.chunk_id and not _is_safe_id(note.chunk_id):
            raise ValueError(f"Unsafe chunk id rejected: {note.chunk_id!r}")
        record = note_to_dict(note)
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO notes "
                        "(id, document_id, chunk_id, note_text, schema_version, payload, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            note.id,
                            note.document_id,
                            note.chunk_id,
                            note.text,
                            record["schema_version"],
                            json.dumps(record, ensure_ascii=False),
                            note.created_at,
                            note.updated_at,
                        ),
                    )

    def load_note(self, note_id: str) -> Note | None:
        if not _is_safe_id(note_id):
            return None
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT payload FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            return None
        return note_from_dict(json.loads(row[0]))

    def list_notes(self, document_id: str) -> list[Note]:
        if not _is_safe_id(document_id):
            return []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload FROM notes WHERE document_id = ? ORDER BY updated_at DESC, created_at DESC",
                (document_id,),
            ).fetchall()
        return [note_from_dict(json.loads(row[0])) for row in rows]

    def delete_note(self, note_id: str) -> bool:
        if not _is_safe_id(note_id):
            return False
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    result = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                    return result.rowcount > 0

    def save_highlight(self, highlight: Highlight) -> None:
        if (
            not _is_safe_id(highlight.id)
            or not _is_safe_id(highlight.document_id)
            or not _is_safe_id(highlight.chunk_id)
        ):
            raise ValueError(f"Unsafe highlight/document/chunk id rejected: {highlight.id!r}")
        record = highlight_to_dict(highlight)
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO highlights "
                        "(id, document_id, chunk_id, start_offset, end_offset, color, text, schema_version, payload, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            highlight.id,
                            highlight.document_id,
                            highlight.chunk_id,
                            highlight.start_offset,
                            highlight.end_offset,
                            highlight.color,
                            highlight.text,
                            record["schema_version"],
                            json.dumps(record, ensure_ascii=False),
                            highlight.created_at,
                            highlight.updated_at,
                        ),
                    )

    def load_highlight(self, highlight_id: str) -> Highlight | None:
        if not _is_safe_id(highlight_id):
            return None
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload FROM highlights WHERE id = ?",
                (highlight_id,),
            ).fetchone()
        if row is None:
            return None
        return highlight_from_dict(json.loads(row[0]))

    def list_highlights(self, document_id: str) -> list[Highlight]:
        if not _is_safe_id(document_id):
            return []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload FROM highlights WHERE document_id = ? "
                "ORDER BY created_at ASC, rowid ASC",
                (document_id,),
            ).fetchall()
        return [highlight_from_dict(json.loads(row[0])) for row in rows]

    def delete_highlight(self, highlight_id: str) -> bool:
        if not _is_safe_id(highlight_id):
            return False
        with self._lock:
            with closing(self._connect()) as conn:
                with conn:
                    result = conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
                    return result.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)
