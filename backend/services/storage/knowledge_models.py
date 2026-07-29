from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Versions of the persisted knowledge schemas (same convention as tasks).
CHUNK_SCHEMA_VERSION = 1
ENRICHMENT_SCHEMA_VERSION = 1


@dataclass
class KnowledgeChunk:
    """Immutable, source-faithful content unit with a locator into its origin.

    Field set is frozen by docs/domain-model.md (ADR-0004). Media sources
    use start/end (seconds); non-media sources use locator_type/payload.
    """

    id: str
    document_id: str
    ordinal: int
    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    locator_type: Optional[str] = None
    locator_payload: Optional[dict[str, Any]] = None


def chunk_to_dict(chunk: KnowledgeChunk) -> dict[str, Any]:
    """Serialize a KnowledgeChunk to its persisted dict form (schema owner)."""
    return {
        "schema_version": CHUNK_SCHEMA_VERSION,
        "id": chunk.id,
        "document_id": chunk.document_id,
        "ordinal": chunk.ordinal,
        "text": chunk.text,
        "start": chunk.start,
        "end": chunk.end,
        "locator_type": chunk.locator_type,
        "locator_payload": chunk.locator_payload,
    }


def chunk_from_dict(data: dict[str, Any]) -> KnowledgeChunk:
    """Deserialize a persisted dict into a KnowledgeChunk."""
    return KnowledgeChunk(
        id=data["id"],
        document_id=data["document_id"],
        ordinal=int(data.get("ordinal", 0)),
        text=data.get("text", ""),
        start=data.get("start"),
        end=data.get("end"),
        locator_type=data.get("locator_type"),
        locator_payload=data.get("locator_payload"),
    )


@dataclass
class Enrichment:
    """Derived, versioned knowledge attached to a Document or a chunk.

    Registry model (ADR-0004): type/params/prompt_version identify the
    producer; payload is the result. "Current" = newest per
    (owner, type, params).
    """

    id: str
    scope: str  # document | chunk
    owner_id: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    prompt_version: int = 1
    payload: Any = None
    created_at: Optional[str] = None  # ISO 8601 UTC


def enrichment_to_dict(enr: Enrichment) -> dict[str, Any]:
    """Serialize an Enrichment to its persisted dict form (schema owner)."""
    return {
        "schema_version": ENRICHMENT_SCHEMA_VERSION,
        "id": enr.id,
        "scope": enr.scope,
        "owner_id": enr.owner_id,
        "type": enr.type,
        "params": enr.params,
        "prompt_version": enr.prompt_version,
        "payload": enr.payload,
        "created_at": enr.created_at,
    }


def enrichment_from_dict(data: dict[str, Any]) -> Enrichment:
    """Deserialize a persisted dict into an Enrichment."""
    return Enrichment(
        id=data["id"],
        scope=data.get("scope", "document"),
        owner_id=data["owner_id"],
        type=data.get("type", ""),
        params=data.get("params") or {},
        prompt_version=int(data.get("prompt_version", 1)),
        payload=data.get("payload"),
        created_at=data.get("created_at"),
    )
