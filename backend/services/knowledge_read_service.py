from __future__ import annotations

from typing import Any

from .storage import DocumentStore, KnowledgeStore
from .storage.models import Task


class KnowledgeReadService:
    """Assembles the legacy status payload from the knowledge layer (ADR-0008).

    Compatibility adapter: reproduces the exact shape of
    TaskManager.to_dict() so the API contract never changes. All-or-nothing:
    returns None unless every flipped field is available, letting the caller
    fall back to the task record. Never raises — a bad shadow must never
    break the status endpoint.
    """

    def __init__(self, document_store: DocumentStore, knowledge_store: KnowledgeStore) -> None:
        self._documents = document_store
        self._knowledge = knowledge_store

    def assemble_status(self, task: Task) -> dict[str, Any] | None:
        """Build the status payload from knowledge data, or None to fall back."""
        try:
            if not task.document_id:
                return None

            document = self._documents.load(task.document_id)
            if document is None:
                self._warn(task.id, "document missing")
                return None

            chunks = self._knowledge.load_chunks(task.document_id)
            if not chunks:
                self._warn(task.id, "chunks missing")
                return None

            summaries = self._knowledge.load_enrichments(
                "document", task.document_id, type="summary"
            )
            chapters_enr = self._knowledge.load_enrichments(
                "document", task.document_id, type="chapters"
            )
            if not summaries or not chapters_enr:
                self._warn(task.id, "summary/chapters enrichments missing")
                return None

            summary_payload = summaries[0].payload or {}
            chapters_payload = chapters_enr[0].payload or {}

            return {
                # Job state: always from the task record (frozen domain split).
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "error": task.error,
                "source_type": task.source,
                "ai_profile_id": task.ai_profile_id,
                "ai_profile_name": task.ai_profile_name,
                "ai_provider": task.ai_provider,
                "ai_model": task.ai_model,
                "timings": task.timings or {},
                # Content: from the knowledge layer.
                "transcript": "\n".join(chunk.text for chunk in chunks),
                "transcript_segments": [
                    {"start": chunk.start, "end": chunk.end, "text": chunk.text}
                    for chunk in chunks
                ],
                "summary": summary_payload.get("text"),
                "chapters": chapters_payload.get("chapters") or [],
                "language": summary_payload.get("language") or document.primary_language,
                "transcript_language": document.primary_language,
            }
        except Exception as exc:
            self._warn(task.id, f"assembly error: {exc!r}")
            return None

    @staticmethod
    def _warn(task_id: str, reason: str) -> None:
        print(f"⚠️ Knowledge read fallback for task {task_id}: {reason}")
