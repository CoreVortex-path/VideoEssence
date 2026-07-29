from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import re

# Version of the persisted task schema. Absence of the key in existing
# files means v0 (pre-versioning). Bump when the schema changes so future
# migrations can branch on an explicit marker instead of heuristics.
# v2: added document_id (link to the knowledge layer, ADR-0005).
TASK_SCHEMA_VERSION = 2

# Storage backends never trust callers: only a conservative charset may be
# used as a record id, so no id can become a path traversal (JSON backend)
# or an unexpected key shape (any backend).
_SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def is_valid_task_id(task_id: str | None) -> bool:
    """Return True if *task_id* is safe to use as a storage key."""
    return bool(task_id) and bool(_SAFE_TASK_ID.match(task_id))


@dataclass
class Task:
    """Processing job record.

    Owns both the job state (status/progress/error/timings) and, for now,
    the produced artifacts (transcript/segments/chapters/summary). Phase 2
    will move artifacts out into persistent knowledge objects; the schema
    below is frozen for backward compatibility with existing JSON files.
    """

    id: str
    source: str
    status: str = "created"
    progress: str = "Task created"
    error: Optional[str] = None
    transcript_path: Optional[Path] = None
    summary_path: Optional[Path] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    language: Optional[str] = None
    transcript_language: Optional[str] = None
    transcript_segments: list[dict[str, Any]] | None = None
    chapters: list[dict[str, Any]] | None = None
    translation_results: dict[str, dict[str, Any]] | None = None
    ai_profile_id: Optional[str] = None
    ai_profile_name: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    timings: dict[str, float] | None = None
    started_at: float | None = None
    document_id: Optional[str] = None


def task_to_dict(task: Task) -> dict[str, Any]:
    """Serialize a Task to its persisted dict form.

    This is the single owner of the on-disk task schema. Keys and value
    shapes must stay backward compatible with existing data/tasks/*.json.
    """
    return {
        "schema_version": TASK_SCHEMA_VERSION,
        "id": task.id,
        "source": task.source,
        "status": task.status,
        "progress": task.progress,
        "error": task.error,
        "transcript_path": str(task.transcript_path) if task.transcript_path else None,
        "summary_path": str(task.summary_path) if task.summary_path else None,
        "transcript": task.transcript,
        "summary": task.summary,
        "language": task.language,
        "transcript_language": task.transcript_language,
        "transcript_segments": task.transcript_segments or [],
        "chapters": task.chapters or [],
        "ai_profile_id": task.ai_profile_id,
        "ai_profile_name": task.ai_profile_name,
        "ai_provider": task.ai_provider,
        "ai_model": task.ai_model,
        "translation_results": task.translation_results or {},
        "timings": task.timings or {},
        "started_at": task.started_at,
        "document_id": task.document_id,
    }


def task_from_dict(data: dict[str, Any]) -> Task:
    """Deserialize a persisted dict back into a Task.

    Tolerates missing optional keys (older files) via .get() defaults.
    """
    return Task(
        id=data["id"],
        source=data.get("source", "file"),
        status=data.get("status", "created"),
        progress=data.get("progress", "Task created"),
        error=data.get("error"),
        transcript_path=Path(data["transcript_path"]) if data.get("transcript_path") else None,
        summary_path=Path(data["summary_path"]) if data.get("summary_path") else None,
        transcript=data.get("transcript"),
        summary=data.get("summary"),
        language=data.get("language"),
        transcript_language=data.get("transcript_language"),
        transcript_segments=data.get("transcript_segments") or [],
        chapters=data.get("chapters") or [],
        translation_results=data.get("translation_results") or {},
        ai_profile_id=data.get("ai_profile_id"),
        ai_profile_name=data.get("ai_profile_name"),
        ai_provider=data.get("ai_provider"),
        ai_model=data.get("ai_model"),
        timings=data.get("timings") or {},
        started_at=data.get("started_at"),
        document_id=data.get("document_id"),
    )
