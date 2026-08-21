from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import (
    Document,
    DocumentStore,
    Enrichment,
    KnowledgeChunk,
    KnowledgeStore,
)
from .storage.models import Task
from .document_extraction import ExtractedDocument
from .extractors.formula_detector import (
    KIND_IMAGE,
    KIND_REGION,
    KIND_TEXT,
    KIND_VECTOR,
)
from .formula_region_renderer import FormulaRegionRenderer

_LOG_PATH = Path("data/logs/knowledge_shadow.log")

# Registry: current producer versions (ADR-0004). Bump on prompt change —
# a new version creates a new enrichment record, old ones are kept.
PROMPT_VERSION_SUMMARY = 1
PROMPT_VERSION_CHAPTERS = 1
PROMPT_VERSION_TRANSLATION = 1


def _deterministic_id(*parts: Any) -> str:
    """Content-addressed uuid5 for stable shadow identities (ADR-0006)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "videobrain:" + ":".join(str(p) for p in parts)))


def deterministic_chunk_id(document_id: str, ordinal: int) -> str:
    """Public helper: stable chunk id for a document's segment ordinal.

    Must stay in sync with KnowledgeIngestService.shadow_write_task, which
    assigns chunk ids as uuid5("chunk", document_id, index).
    """
    return _deterministic_id("chunk", document_id, ordinal)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(line: str) -> None:
    try:
        print(f"🌑 {line}")
    except UnicodeEncodeError:
        # Windows cp1251 consoles cannot print the emoji — never let logging
        # crash the caller.
        print(f"[knowledge] {line}")
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{_utc_now_iso()} {line}\n")
    except Exception as exc:
        print(f"⚠️ Could not write shadow log: {exc}")


class KnowledgeIngestService:
    """Best-effort shadow writer: task output → knowledge layer (ADR-0006).

    The task pipeline remains the source of truth. Every public method
    catches all exceptions, logs them, and never raises — a shadow failure
    must never affect processing or API behavior. A completed task without
    document_id marks a missing shadow (repair queue for the backfill).
    """

    def __init__(
        self,
        document_store: DocumentStore,
        knowledge_store: KnowledgeStore,
        formula_renderer: FormulaRegionRenderer | None = None,
    ) -> None:
        self._documents = document_store
        self._knowledge = knowledge_store
        self._formula_renderer = formula_renderer or FormulaRegionRenderer()

    def shadow_write_task(
        self,
        task: Task,
        content_hash: str | None,
        origin_filename: str | None,
    ) -> str | None:
        """Shadow-write a completed task. Returns document_id or None on failure."""
        stage = "document"
        document_id: str | None = None
        try:
            if not task.transcript_segments:
                raise ValueError("task has no transcript segments to shadow-write")

            document_id = _deterministic_id("doc", content_hash or f"task:{task.id}")
            document = Document(
                id=document_id,
                source_type="file_media",
                origin_uri=origin_filename,
                title=origin_filename,
                # Media retention is a deferred Phase 2 decision (ADR-0006);
                # cleanup deletes the upload, so no media_path is recorded.
                media_path=None,
                primary_language=task.transcript_language or task.language,
                language_source="asr" if task.transcript_language else None,
                duration_seconds=None,
                content_hash=content_hash,
                created_at=_utc_now_iso(),
            )
            self._documents.save(document)

            stage = "chunks"
            chunks = [
                KnowledgeChunk(
                    id=_deterministic_id("chunk", document_id, index),
                    document_id=document_id,
                    ordinal=index,
                    text=str(seg.get("text", "")),
                    start=float(seg["start"]) if seg.get("start") is not None else None,
                    end=float(seg["end"]) if seg.get("end") is not None else None,
                )
                for index, seg in enumerate(task.transcript_segments)
            ]
            self._knowledge.save_chunks(document_id, chunks)

            stage = "enrichments"
            written = 0
            producer = {"ai_profile": task.ai_profile_id, "ai_model": task.ai_model}
            if task.summary:
                self._save_document_enrichment(
                    document_id, "summary", PROMPT_VERSION_SUMMARY, producer,
                    {"text": task.summary, "language": task.language},
                )
                written += 1
            if task.chapters:
                self._save_document_enrichment(
                    document_id, "chapters", PROMPT_VERSION_CHAPTERS, producer,
                    {"chapters": task.chapters},
                )
                written += 1
            # AI insights (keywords + suggested questions) come from the same
            # summary prompt pass, hence the shared prompt version.
            if task.keywords or task.suggested_questions:
                self._save_document_enrichment(
                    document_id, "insights", PROMPT_VERSION_SUMMARY, producer,
                    {
                        "keywords": task.keywords or [],
                        "suggested_questions": task.suggested_questions or [],
                    },
                )
                written += 1

            _log(f"SUCCESS task={task.id} document={document_id} "
                 f"chunks={len(chunks)} enrichments={written}")
            return document_id
        except Exception as exc:
            _log(f"FAILURE task={task.id} document={document_id or 'none'} "
                 f"stage={stage} error={exc!r}\n{traceback.format_exc()}")
            return None

    def ingest_extracted_document(
        self,
        extracted: ExtractedDocument,
        source_type: str,
        content_hash: str | None,
        origin_filename: str | None,
        source_path: Path | None = None,
    ) -> str | None:
        """Ingest a DocumentExtractor result (PDF/FB2) into the knowledge layer.

        Returns document_id or None on failure. Same best-effort contract
        as shadow_write_task: logs and never raises.

        ``source_path`` is the document file on disk; when present, formula
        candidates (ExtractedDocument.formulas) are rendered to PNG and
        ingested as additional formula chunks after the text chunks.
        """
        stage = "document"
        document_id: str | None = None
        try:
            if not extracted.chunks:
                raise ValueError("extracted document has no chunks to ingest")

            document_id = _deterministic_id(
                "doc", content_hash or f"{source_type}:{origin_filename}"
            )
            document = Document(
                id=document_id,
                source_type=source_type,
                origin_uri=origin_filename,
                title=extracted.title or origin_filename,
                media_path=None,
                primary_language=extracted.language,
                language_source="declared" if extracted.language else None,
                duration_seconds=None,
                content_hash=content_hash,
                created_at=_utc_now_iso(),
            )
            self._documents.save(document)

            stage = "chunks"
            chunks = [
                KnowledgeChunk(
                    id=_deterministic_id("chunk", document_id, chunk.ordinal),
                    document_id=document_id,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    locator_type=chunk.locator_type,
                    locator_payload=chunk.locator_payload or None,
                )
                for chunk in extracted.chunks
            ]
            formula_chunks = self._build_formula_chunks(document_id, extracted, source_path)
            chunks.extend(formula_chunks)
            self._knowledge.save_chunks(document_id, chunks)

            _log(f"SUCCESS source_type={source_type} document={document_id} "
                 f"chunks={len(chunks)} formulas={len(formula_chunks)}")
            return document_id
        except Exception as exc:
            _log(f"FAILURE source_type={source_type} document={document_id or 'none'} "
                 f"stage={stage} error={exc!r}\n{traceback.format_exc()}")
            return None

    def _build_formula_chunks(
        self,
        document_id: str,
        extracted: ExtractedDocument,
        source_path: Path | None,
    ) -> list[KnowledgeChunk]:
        """Turn formula candidates into chunks appended after the text chunks.

        formula_vector/formula_region candidates are rendered to PNG (when
        the source file is available) and carry image_path in the locator;
        formula_text keeps only its text. A render failure is logged and
        the chunk is still written, without image_path.
        formula_image candidates (plain embedded images) are skipped
        entirely: a photo or diagram is not a formula.
        """
        base = len(extracted.chunks)
        candidates = [c for c in extracted.formulas if c.kind != KIND_IMAGE]
        formula_chunks = []
        for index, candidate in enumerate(candidates):
            payload: dict[str, Any] = {
                "page": candidate.page,
                "bbox": list(candidate.bbox),
                "kind": candidate.kind,
            }
            if candidate.kind in (KIND_VECTOR, KIND_REGION) and source_path is not None:
                try:
                    png = self._formula_renderer.render(
                        source_path, document_id, candidate, index
                    )
                    payload["image_path"] = png.as_posix()
                except Exception as exc:
                    _log(f"WARN document={document_id} stage=formula-render "
                         f"page={candidate.page} kind={candidate.kind} error={exc!r}")
            formula_chunks.append(KnowledgeChunk(
                id=_deterministic_id("chunk", document_id, base + index),
                document_id=document_id,
                ordinal=base + index,
                text=candidate.text or "" if candidate.kind == KIND_TEXT else "",
                locator_type=candidate.kind,
                locator_payload=payload,
            ))
        return formula_chunks

    def shadow_write_translations(self, task: Task) -> int:
        """Shadow-write cached translations as chunk-scoped enrichments.

        Returns the number of enrichments written (0 on skip/failure).
        """
        try:
            if not task.document_id:
                _log(f"SKIP task={task.id} stage=translation reason=no-document-id")
                return 0

            chunks = self._knowledge.load_chunks(task.document_id)
            if not chunks:
                raise ValueError(f"no chunks found for document {task.document_id}")

            written = 0
            for cache_key, result in (task.translation_results or {}).items():
                segments = result.get("transcript_segments") or []
                params = {
                    "target_language": result.get("target_language"),
                    "ai_profile": result.get("ai_profile_id"),
                }
                for index, seg in enumerate(segments):
                    if index >= len(chunks):
                        break
                    enrichment = seg.get("enrichment") if isinstance(seg, dict) else None
                    if not isinstance(enrichment, dict):
                        continue
                    chunk_id = chunks[index].id
                    self._knowledge.save_enrichment(Enrichment(
                        id=_deterministic_id(
                            "enr", chunk_id, "translation",
                            json.dumps(params, sort_keys=True),
                            PROMPT_VERSION_TRANSLATION,
                        ),
                        scope="chunk",
                        owner_id=chunk_id,
                        type="translation",
                        params=params,
                        prompt_version=PROMPT_VERSION_TRANSLATION,
                        payload={
                            "text": enrichment.get("translation"),
                            "status": enrichment.get("translation_status"),
                            "error": enrichment.get("translation_error"),
                        },
                        created_at=_utc_now_iso(),
                    ))
                    written += 1

            _log(f"SUCCESS task={task.id} document={task.document_id} "
                 f"stage=translation enrichments={written}")
            return written
        except Exception as exc:
            _log(f"FAILURE task={task.id} document={task.document_id or 'none'} "
                 f"stage=translation error={exc!r}\n{traceback.format_exc()}")
            return 0

    def _save_document_enrichment(
        self,
        document_id: str,
        type: str,
        prompt_version: int,
        params: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        self._knowledge.save_enrichment(Enrichment(
            id=_deterministic_id(
                "enr", document_id, type,
                json.dumps(params, sort_keys=True), prompt_version,
            ),
            scope="document",
            owner_id=document_id,
            type=type,
            params=params,
            prompt_version=prompt_version,
            payload=payload,
            created_at=_utc_now_iso(),
        ))
