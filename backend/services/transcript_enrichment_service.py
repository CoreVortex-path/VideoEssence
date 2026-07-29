from __future__ import annotations

import json
import math
from typing import Any

from .ai_provider import BaseAIProvider
from ..config.ai_token_limits import TokenLimits, DEFAULT as _DEFAULT_LIMITS


class TranscriptEnrichmentService:
    """Adds AI enrichment metadata to transcript segments in batched requests."""

    MAX_BATCH_SIZE = 60
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_NOT_GENERATED = "not_generated"

    def __init__(
        self,
        ai_provider: BaseAIProvider,
        batch_size: int = 80,
        token_limits: TokenLimits = _DEFAULT_LIMITS,
    ) -> None:
        self.ai_provider = ai_provider
        self.batch_size = max(1, min(batch_size, self.MAX_BATCH_SIZE))
        self.limits = token_limits

    def enrich_segments(
        self,
        transcript_segments: list[dict[str, Any]],
        source_language: str | None = None,
        target_language: str = "Russian",
    ) -> list[dict[str, Any]]:
        if not transcript_segments:
            return []

        enriched = [dict(segment) for segment in transcript_segments]
        self._ensure_default_enrichment(enriched)
        batches = [
            enriched[i:i + self.batch_size]
            for i in range(0, len(enriched), self.batch_size)
        ]

        for batch_index, batch in enumerate(batches, start=1):
            try:
                prompt = self._build_prompt(
                    batch=batch,
                    source_language=source_language,
                    target_language=target_language,
                    batch_index=batch_index,
                    batch_total=len(batches),
                )
                max_tokens = self._estimate_batch_max_tokens(batch)
                raw = self.ai_provider.generate_text(prompt, max_tokens=max_tokens)
                payload = self._load_json(raw)
                self._merge_batch_enrichment(batch, payload)
            except Exception as exc:
                print(f"⚠️ Enrichment batch {batch_index}/{len(batches)} failed: {exc}")
                self._mark_batch_translation_failed(batch, str(exc))
                continue

        return enriched

    def _estimate_batch_max_tokens(self, batch: list[dict[str, Any]]) -> int:
        """Estimate output budget for one enrichment batch and keep it bounded."""
        text_chars = sum(len(str(seg.get("text", ""))) for seg in batch)
        # Rough budget: translation chars + JSON structure overhead per segment.
        estimated_output_tokens = math.ceil((text_chars + len(batch) * 140) / 4)
        with_safety_margin = math.ceil(estimated_output_tokens * 1.35)
        return max(
            self.limits.ENRICHMENT_MIN,
            min(with_safety_margin, self.limits.ENRICHMENT_MAX),
        )

    def _build_prompt(
        self,
        batch: list[dict[str, Any]],
        source_language: str | None,
        target_language: str,
        batch_index: int,
        batch_total: int,
    ) -> str:
        rows = []
        for i, seg in enumerate(batch):
            rows.append(
                {
                    "index": i,
                    "start": float(seg.get("start", 0.0)),
                    "end": float(seg.get("end", 0.0)),
                    "text": str(seg.get("text", "")),
                }
            )

        language_note = (
            f"Source language is likely {source_language}."
            if source_language
            else "Detect source language from text."
        )

        return f"""
You enrich transcript segments for downstream UX and knowledge extraction.

Batch: {batch_index}/{batch_total}
{language_note}
Target translation language: {target_language}

Input JSON segments:
{json.dumps(rows, ensure_ascii=False)}

Return STRICT JSON only with schema:
{{
  "segments": [
    {{
      "index": 0,
      "enrichment": {{
        "translation": "string",
        "translation_status": "ready",
        "translation_error": null,
        "key_concepts": ["string"],
        "entities": [{{"label": "string", "value": "string"}}],
        "tags": ["string"],
        "extra": {{}}
      }}
    }}
  ]
}}

Rules:
- Preserve segment order by index.
- translation is required for every segment and must match target language.
- If translation cannot be produced, set translation_status="failed" and provide translation_error.
- key_concepts/entities/tags can be empty arrays.
- Do not include markdown wrappers.
"""

    def _merge_batch_enrichment(self, batch: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        items = payload.get("segments") or []
        if not isinstance(items, list):
            self._mark_batch_translation_failed(batch, "Model returned invalid JSON schema for segments")
            return
        by_index: dict[int, dict[str, Any]] = {}
        for item in items:
            try:
                idx = int(item.get("index"))
            except Exception:
                continue
            by_index[idx] = item

        for i, seg in enumerate(batch):
            item = by_index.get(i) or {}
            enrichment = item.get("enrichment") or {}

            translation_raw = enrichment.get("translation")
            translation = str(translation_raw).strip() if translation_raw is not None else ""
            has_translation = bool(translation)
            status_raw = str(enrichment.get("translation_status") or "").strip().lower()
            translation_status = status_raw if status_raw in {
                self.STATUS_READY,
                self.STATUS_FAILED,
                self.STATUS_NOT_GENERATED,
            } else (self.STATUS_READY if has_translation else self.STATUS_FAILED)
            translation_error_raw = enrichment.get("translation_error")
            translation_error = str(translation_error_raw).strip() if translation_error_raw is not None else None

            key_concepts = enrichment.get("key_concepts")
            entities = enrichment.get("entities")
            tags = enrichment.get("tags")
            extra = enrichment.get("extra")

            seg["enrichment"] = {
                "translation": translation if has_translation else None,
                "translation_status": translation_status if has_translation else self.STATUS_FAILED,
                "translation_error": None if has_translation else (translation_error or "Translation was not provided by the model"),
                "key_concepts": key_concepts if isinstance(key_concepts, list) else [],
                "entities": entities if isinstance(entities, list) else [],
                "tags": tags if isinstance(tags, list) else [],
                "extra": extra if isinstance(extra, dict) else {},
            }

    def _ensure_default_enrichment(self, segments: list[dict[str, Any]]) -> None:
        for seg in segments:
            seg["enrichment"] = {
                "translation": None,
                "translation_status": self.STATUS_NOT_GENERATED,
                "translation_error": None,
                "key_concepts": [],
                "entities": [],
                "tags": [],
                "extra": {},
            }

    def _mark_batch_translation_failed(self, batch: list[dict[str, Any]], error: str) -> None:
        message = str(error).strip() or "Translation generation failed"
        for seg in batch:
            enrichment = seg.get("enrichment")
            if not isinstance(enrichment, dict):
                enrichment = {}
            enrichment["translation"] = None
            enrichment["translation_status"] = self.STATUS_FAILED
            enrichment["translation_error"] = message
            enrichment["key_concepts"] = enrichment.get("key_concepts") if isinstance(enrichment.get("key_concepts"), list) else []
            enrichment["entities"] = enrichment.get("entities") if isinstance(enrichment.get("entities"), list) else []
            enrichment["tags"] = enrichment.get("tags") if isinstance(enrichment.get("tags"), list) else []
            enrichment["extra"] = enrichment.get("extra") if isinstance(enrichment.get("extra"), dict) else {}
            seg["enrichment"] = enrichment

    @staticmethod
    def _load_json(text: str) -> dict[str, Any]:
        from .ai_provider import BaseAIProvider
        payload = BaseAIProvider.parse_ai_json(text)
        if isinstance(payload, list):
            return {"segments": payload}
        if isinstance(payload, dict):
            return payload
        return {"segments": []}
