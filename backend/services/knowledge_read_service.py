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

            # Insights enrichment is optional (older documents lack it);
            # fall back to the task record fields.
            insights_enr = self._knowledge.load_enrichments(
                "document", task.document_id, type="insights"
            )
            insights_payload = (insights_enr[0].payload or {}) if insights_enr else {}

            # Chunk-scoped translation enrichments → legacy translation_results
            # shape ("{profile}:{lang}" cache key), so translations survive a
            # library reopen. Optional too: no translations → empty dict.
            translation_results = self._assemble_translations(chunks)

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
                "document_id": task.document_id,
                "source_url": task.source_url,
                "title": document.title or task.title,
                # Content: from the knowledge layer.
                "transcript": "\n".join(chunk.text for chunk in chunks),
                "transcript_segments": [
                    {
                        "start": chunk.start,
                        "end": chunk.end,
                        "text": chunk.text,
                        "chunk_id": chunk.id,
                    }
                    for chunk in chunks
                ],
                "summary": summary_payload.get("text"),
                "chapters": chapters_payload.get("chapters") or [],
                "language": summary_payload.get("language") or document.primary_language,
                "transcript_language": document.primary_language,
                "keywords": insights_payload.get("keywords") or task.keywords or [],
                "suggested_questions": insights_payload.get("suggested_questions")
                or task.suggested_questions
                or [],
                "translation_results": translation_results,
            }
        except Exception as exc:
            self._warn(task.id, f"assembly error: {exc!r}")
            return None

    def _assemble_translations(self, chunks) -> dict[str, Any]:
        """Rebuild translation_results from chunk-scoped translation enrichments.

        Mirrors the legacy cache shape written by the translate endpoint:
        "{ai_profile}:{target_language.lower()}" -> {target_language,
        ai_profile_id, transcript_segments (с enrichment), full_translation}.
        """
        # chunk_id -> payload for each (profile, language) pair.
        grouped: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            enrichments = self._knowledge.load_enrichments(
                "chunk", chunk.id, type="translation"
            )
            for enrichment in enrichments:
                params = enrichment.params or {}
                profile = params.get("ai_profile")
                language = params.get("target_language")
                if not profile or not language:
                    continue
                cache_key = f"{profile}:{str(language).lower()}"
                entry = grouped.setdefault(
                    cache_key,
                    {
                        "target_language": language,
                        "ai_profile_id": profile,
                        "by_chunk": {},
                    },
                )
                entry["by_chunk"][chunk.id] = enrichment.payload or {}

        results: dict[str, Any] = {}
        for cache_key, entry in grouped.items():
            segments: list[dict[str, Any]] = []
            for chunk in chunks:
                payload = entry["by_chunk"].get(chunk.id) or {}
                segments.append(
                    {
                        "start": chunk.start,
                        "end": chunk.end,
                        "text": chunk.text,
                        "chunk_id": chunk.id,
                        "enrichment": {
                            "translation": payload.get("text"),
                            "translation_status": payload.get("status")
                            or "not_generated",
                            "translation_error": payload.get("error"),
                        },
                    }
                )
            full_translation = "\n\n".join(
                str(seg["enrichment"]["translation"]).strip()
                for seg in segments
                if seg["enrichment"].get("translation")
            )
            results[cache_key] = {
                "target_language": entry["target_language"],
                "ai_profile_id": entry["ai_profile_id"],
                "transcript_segments": segments,
                "full_translation": full_translation,
            }
        return results

    def get_document_context(
        self,
        document_id: str,
        max_chunks: int | None = None,
    ) -> dict[str, Any] | None:
        """Return normalized document context from the knowledge layer."""
        try:
            document = self._documents.load(document_id)
            if document is None:
                return None

            chunks = self._knowledge.load_chunks(document_id)
            if not chunks:
                return None

            if max_chunks is not None:
                chunks = chunks[:max_chunks]

            summary_payload = {}
            summaries = self._knowledge.load_enrichments(
                "document", document_id, type="summary"
            )
            if summaries:
                summary_payload = summaries[0].payload or {}

            chunk_payload = [
                {
                    "chunk_id": chunk.id,
                    "ordinal": chunk.ordinal,
                    "text": chunk.text,
                    "translation": self._load_chunk_translation(chunk.id),
                    "start": chunk.start,
                    "end": chunk.end,
                }
                for chunk in chunks
            ]

            return {
                "document_id": document.id,
                "title": document.title,
                "primary_language": document.primary_language,
                "summary": summary_payload.get("text"),
                "chunks": chunk_payload,
            }
        except Exception as exc:
            print(f"⚠️ Failed to build document context {document_id}: {exc!r}")
            return None

    def get_library_chunks(self) -> list[dict[str, Any]]:
        """All chunks across all documents, annotated with document titles.

        Used by the global assistant ("library" mode). Never raises — a bad
        document must not break the assistant; it is just skipped.
        """
        collected: list[dict[str, Any]] = []
        try:
            document_ids = self._documents.list_ids()
        except Exception as exc:
            print(f"⚠️ Failed to list documents for library context: {exc!r}")
            return []
        for document_id in document_ids:
            try:
                document = self._documents.load(document_id)
                chunks = self._knowledge.load_chunks(document_id)
            except Exception as exc:
                print(f"⚠️ Skipping document {document_id} in library context: {exc!r}")
                continue
            for chunk in chunks:
                collected.append(
                    {
                        "chunk_id": chunk.id,
                        "document_id": document_id,
                        "doc_title": (document.title if document else None) or "Untitled",
                        "ordinal": chunk.ordinal,
                        "text": chunk.text,
                        "translation": self._load_chunk_translation(chunk.id),
                        "start": chunk.start,
                        "end": chunk.end,
                    }
                )
        return collected

    def _load_chunk_translation(self, chunk_id: str) -> str | None:
        """Joined translation texts stored for a chunk (any profile/language).

        Used by chat retrieval so a question in one language can match a
        chunk written in another. Never raises — translations are optional.
        """
        try:
            enrichments = self._knowledge.load_enrichments(
                "chunk", chunk_id, type="translation"
            )
        except Exception:
            return None
        texts = []
        for enrichment in enrichments:
            text = (enrichment.payload or {}).get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
        return "\n".join(texts) if texts else None

    @staticmethod
    def _warn(task_id: str, reason: str) -> None:
        print(f"⚠️ Knowledge read fallback for task {task_id}: {reason}")
