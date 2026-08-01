from __future__ import annotations

from typing import Any

from .ai_provider import BaseAIProvider, is_quota_error
from ..config.ai_token_limits import DEFAULT as _DEFAULT_LIMITS
from .translation.batch_builder import BatchBuilder
from .translation.prompt_builder import TranslationPromptBuilder
from .translation.parser import TranslationParser
from .translation.translator import Translator
from .translation.retry import AdaptivePacer


class TranscriptEnrichmentService:
    """Оркестратор перевода транскрипта.

    Вся работа вынесена в пакет services/translation:
    BatchBuilder (батчи по max_chars) -> TranslationPromptBuilder ->
    Translator (prompt -> raw text) -> TranslationParser. Сегменты,
    потерянные при парсинге, досылаются отдельным repair-проходом
    в конце, а не перепереводом всего батча.
    """

    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_NOT_GENERATED = "not_generated"

    MAX_REPAIR_ROUNDS = 2

    def __init__(
        self,
        ai_provider: BaseAIProvider,
        token_limits=None,
        max_chars: int = 4500,
    ) -> None:
        self.ai_provider = ai_provider
        self.limits = token_limits or _DEFAULT_LIMITS
        self.batch_builder = BatchBuilder(max_chars=max_chars)
        self.prompt_builder = TranslationPromptBuilder()
        self.parser = TranslationParser()
        self.translator = Translator(
            ai_provider,
            max_tokens=self.limits.ENRICHMENT_MAX if self.limits else 8192,
        )
        self.pacer = AdaptivePacer()

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

        batches = self.batch_builder.build(enriched)
        missing: list[dict[str, Any]] = []

        for batch_index, batch in enumerate(batches, start=1):
            if batch_index > 1:
                self.pacer.wait()
            raw = self._translate_batch(
                batch, source_language, target_language, batch_index, len(batches)
            )
            if raw is None:
                continue  # батч уже помечен failed целиком
            missing.extend(self._apply_translations(raw, batch))

        self._repair_missing(missing, source_language, target_language)
        return enriched

    def build_full_translation(self, enriched: list[dict[str, Any]]) -> str:
        """Склеить все переводы в единое полотно для правой панели."""
        parts = []
        for seg in enriched:
            t = seg.get("enrichment", {}).get("translation")
            if t:
                parts.append(str(t).strip())
        return "\n\n".join(parts)

    def _translate_batch(
        self,
        batch: list[dict[str, Any]],
        source_language: str | None,
        target_language: str,
        batch_index: int,
        batch_total: int,
    ) -> str | None:
        """Перевести один батч. None — батч упал и помечен failed."""
        prompt = self.prompt_builder.build(
            batch=batch,
            source_language=source_language,
            target_language=target_language,
            batch_index=batch_index,
            batch_total=batch_total,
        )
        try:
            raw = self.translator.translate(prompt)
        except Exception as exc:
            print(f"[enrichment] batch {batch_index}/{batch_total} failed: {exc}")
            if is_quota_error(exc):
                self.pacer.on_rate_limit()
            self._mark_batch_translation_failed(batch, str(exc))
            return None
        self.pacer.on_success()
        return raw

    def _apply_translations(
        self, raw: str, batch: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Применить распарсенные переводы; вернуть сегменты без перевода."""
        translations = self.parser.parse(raw)
        missing: list[dict[str, Any]] = []
        for i, seg in enumerate(batch):
            translation = translations.get(i)
            if translation:
                seg["enrichment"] = {
                    "translation": translation,
                    "translation_status": self.STATUS_READY,
                    "translation_error": None,
                    "key_concepts": [],
                    "entities": [],
                    "tags": [],
                    "extra": {},
                }
            else:
                missing.append(seg)
        return missing

    def _repair_missing(
        self,
        missing: list[dict[str, Any]],
        source_language: str | None,
        target_language: str,
    ) -> None:
        """Дослать потерянные сегменты отдельными мелкими запросами."""
        rounds = 0
        while missing and rounds < self.MAX_REPAIR_ROUNDS:
            rounds += 1
            repair_batches = self.batch_builder.build(missing)
            still_missing: list[dict[str, Any]] = []
            for batch_index, batch in enumerate(repair_batches, start=1):
                self.pacer.wait()
                raw = self._translate_batch(
                    batch, source_language, target_language,
                    batch_index, len(repair_batches),
                )
                if raw is None:
                    # Батч уже помечен failed; из repair выбывает.
                    continue
                still_missing.extend(self._apply_translations(raw, batch))
            missing = still_missing

        for seg in missing:
            self._mark_segment_translation_failed(
                seg, "Segment missing in response after repair"
            )

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

    def _mark_batch_translation_failed(
        self, batch: list[dict[str, Any]], error: str
    ) -> None:
        for seg in batch:
            self._mark_segment_translation_failed(seg, error)

    def _mark_segment_translation_failed(
        self, seg: dict[str, Any], error: str
    ) -> None:
        seg["enrichment"] = {
            "translation": None,
            "translation_status": self.STATUS_FAILED,
            "translation_error": error,
            "key_concepts": [],
            "entities": [],
            "tags": [],
            "extra": {},
        }
