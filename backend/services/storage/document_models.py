from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Version of the persisted document schema. Bump on schema change so
# migrations can branch on an explicit marker (same convention as tasks).
DOCUMENT_SCHEMA_VERSION = 1


@dataclass
class Document:
    """Provenance and identity of one ingested content item.

    Owns no content (KnowledgeChunk) and no job state (Task).
    Field set is frozen by docs/domain-model.md (ADR-0004).
    """

    id: str
    source_type: str
    origin_uri: Optional[str] = None
    title: Optional[str] = None
    media_path: Optional[str] = None
    primary_language: Optional[str] = None
    language_source: Optional[str] = None  # asr | declared | manual
    duration_seconds: Optional[float] = None
    content_hash: Optional[str] = None
    created_at: Optional[str] = None  # ISO 8601 UTC


def document_to_dict(doc: Document) -> dict[str, Any]:
    """Serialize a Document to its persisted dict form (schema owner)."""
    return {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "id": doc.id,
        "source_type": doc.source_type,
        "origin_uri": doc.origin_uri,
        "title": doc.title,
        "media_path": doc.media_path,
        "primary_language": doc.primary_language,
        "language_source": doc.language_source,
        "duration_seconds": doc.duration_seconds,
        "content_hash": doc.content_hash,
        "created_at": doc.created_at,
    }


def document_from_dict(data: dict[str, Any]) -> Document:
    """Deserialize a persisted dict into a Document (tolerates older data)."""
    return Document(
        id=data["id"],
        source_type=data.get("source_type", "file_media"),
        origin_uri=data.get("origin_uri"),
        title=data.get("title"),
        media_path=data.get("media_path"),
        primary_language=data.get("primary_language"),
        language_source=data.get("language_source"),
        duration_seconds=data.get("duration_seconds"),
        content_hash=data.get("content_hash"),
        created_at=data.get("created_at"),
    )
