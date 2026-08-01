from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

CHAT_CONVERSATION_SCHEMA_VERSION = 1
CHAT_MESSAGE_SCHEMA_VERSION = 1
NOTE_SCHEMA_VERSION = 1
HIGHLIGHT_SCHEMA_VERSION = 1


@dataclass
class ChatConversation:
    id: str
    document_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ChatMessage:
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Note:
    id: str
    document_id: str
    text: str
    chunk_id: Optional[str] = None
    selected_text: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Highlight:
    id: str
    document_id: str
    chunk_id: str
    start_offset: int
    end_offset: int
    text: str
    color: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def conversation_to_dict(item: ChatConversation) -> dict[str, Any]:
    return {
        "schema_version": CHAT_CONVERSATION_SCHEMA_VERSION,
        "id": item.id,
        "document_id": item.document_id,
        "title": item.title,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def conversation_from_dict(data: dict[str, Any]) -> ChatConversation:
    return ChatConversation(
        id=data["id"],
        document_id=data["document_id"],
        title=data.get("title"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )


def message_to_dict(item: ChatMessage) -> dict[str, Any]:
    return {
        "schema_version": CHAT_MESSAGE_SCHEMA_VERSION,
        "id": item.id,
        "conversation_id": item.conversation_id,
        "role": item.role,
        "content": item.content,
        "created_at": item.created_at,
        "metadata": item.metadata or {},
    }


def message_from_dict(data: dict[str, Any]) -> ChatMessage:
    return ChatMessage(
        id=data["id"],
        conversation_id=data["conversation_id"],
        role=data.get("role", "user"),
        content=data.get("content", ""),
        created_at=data.get("created_at"),
        metadata=data.get("metadata") or {},
    )


def note_to_dict(item: Note) -> dict[str, Any]:
    return {
        "schema_version": NOTE_SCHEMA_VERSION,
        "id": item.id,
        "document_id": item.document_id,
        "chunk_id": item.chunk_id,
        "selected_text": item.selected_text,
        "text": item.text,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def note_from_dict(data: dict[str, Any]) -> Note:
    return Note(
        id=data["id"],
        document_id=data["document_id"],
        chunk_id=data.get("chunk_id"),
        selected_text=data.get("selected_text"),
        text=data.get("text", ""),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )


def highlight_to_dict(item: Highlight) -> dict[str, Any]:
    return {
        "schema_version": HIGHLIGHT_SCHEMA_VERSION,
        "id": item.id,
        "document_id": item.document_id,
        "chunk_id": item.chunk_id,
        "start_offset": item.start_offset,
        "end_offset": item.end_offset,
        "text": item.text,
        "color": item.color,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def highlight_from_dict(data: dict[str, Any]) -> Highlight:
    return Highlight(
        id=data["id"],
        document_id=data["document_id"],
        chunk_id=data["chunk_id"],
        start_offset=int(data.get("start_offset", 0)),
        end_offset=int(data.get("end_offset", 0)),
        text=data.get("text", ""),
        color=data.get("color", "yellow"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )
