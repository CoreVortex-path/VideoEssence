"""Formula vision enrichment: formula chunks -> LaTeX enrichments.

Best-effort, chunk-scoped, registry-model enrichment (ADR-0004). Depends
only on the FormulaRecognizer port — never on a concrete AI provider —
so a local recognizer (e.g. pix2tex) can replace the AI implementations
without changes here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from .ai_provider import (
    AIProfile,
    AIProviderConfigurationError,
    get_ai_provider,
)
from .extractors.formula_detector import KIND_IMAGE, KIND_REGION, KIND_VECTOR
from .formula_recognizer import (
    AIProviderFormulaRecognizer,
    FormulaRecognizer,
    UNRECOGNIZED_MARKER,
)
from .knowledge_ingest_service import _deterministic_id, _log, _utc_now_iso
from .storage import Enrichment, KnowledgeStore
from ..config.ai_token_limits import get_limits

# Registry: bump when FORMULA_LATEX_PROMPT or the payload shape changes —
# a new version produces new enrichment records, old ones are kept.
PROMPT_VERSION_FORMULA_LATEX = 1

ENRICHMENT_TYPE_FORMULA_LATEX = "formula_latex"

# Chunk kinds that go through vision. formula_text never does: its text
# is already available in the chunk itself.
VISION_KINDS = (KIND_IMAGE, KIND_VECTOR, KIND_REGION)

# profile_id -> (profile, recognizer); injectable for tests.
RecognizerFactory = Callable[[Optional[str]], tuple[AIProfile, FormulaRecognizer]]


def default_recognizer_factory(profile_id: str | None) -> tuple[AIProfile, FormulaRecognizer]:
    profile, provider = get_ai_provider(profile_id)
    if not provider.supports_image_input():
        raise AIProviderConfigurationError(
            f"AI profile '{profile.id}' does not support image input; "
            "choose a vision-capable profile for formula enrichment"
        )
    recognizer = AIProviderFormulaRecognizer(
        provider, max_tokens=get_limits(profile.id).FORMULA_VISION
    )
    return profile, recognizer


class FormulaVisionService:
    """Transcribes formula chunks' region images into LaTeX enrichments.

    Mirrors the best-effort contract of KnowledgeIngestService: errors are
    logged and recorded per chunk, never raised into the ingestion path.
    """

    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        recognizer_factory: RecognizerFactory = default_recognizer_factory,
    ) -> None:
        self._knowledge = knowledge_store
        self._recognizer_factory = recognizer_factory

    def enrich_formulas(
        self,
        document_id: str,
        ai_profile_id: str | None = None,
        chunk_ids: set[str] | None = None,
    ) -> dict[str, int]:
        """Run formula vision for a document. Returns result counters.

        ``chunk_ids`` limits the run to the selected formula chunks; None
        means every vision-eligible chunk of the document.
        """
        counters = {"ready": 0, "failed": 0, "skipped": 0}
        try:
            profile, recognizer = self._recognizer_factory(ai_profile_id)
        except Exception as exc:
            _log(f"SKIP document={document_id} stage=formula-vision "
                 f"reason=recognizer-unavailable error={exc!r}")
            return counters

        params = {"ai_profile": profile.id, "ai_model": profile.model}

        for chunk in self._knowledge.load_chunks(document_id):
            if chunk.locator_type not in VISION_KINDS:
                continue
            if chunk_ids is not None and chunk.id not in chunk_ids:
                continue
            if self._is_current(chunk.id, params):
                counters["skipped"] += 1
                continue

            payload = chunk.locator_payload or {}
            image_path = payload.get("image_path")
            if not image_path:
                counters["skipped"] += 1
                _log(f"SKIP document={document_id} chunk={chunk.id} "
                     f"stage=formula-vision reason=no-image-path")
                continue
            if not Path(image_path).exists():
                counters["skipped"] += 1
                _log(f"SKIP document={document_id} chunk={chunk.id} "
                     f"stage=formula-vision reason=image-missing path={image_path}")
                continue

            latex: str | None = None
            status = "ready"
            error: str | None = None
            try:
                raw = recognizer.recognize_latex(Path(image_path))
                latex = (raw or "").strip()
                if not latex or latex == UNRECOGNIZED_MARKER:
                    status, error = "failed", "formula not recognized"
                    latex = None
            except Exception as exc:
                status, error = "failed", str(exc)[:500]
                _log(f"WARN document={document_id} chunk={chunk.id} "
                     f"stage=formula-vision error={exc!r}")

            self._save(chunk.id, params, {"latex": latex, "status": status, "error": error})
            counters["ready" if status == "ready" else "failed"] += 1

        _log(f"SUCCESS document={document_id} stage=formula-vision "
             f"ready={counters['ready']} failed={counters['failed']} "
             f"skipped={counters['skipped']}")
        return counters

    def _is_current(self, chunk_id: str, params: dict[str, Any]) -> bool:
        """True if a ready enrichment of the current version/params exists."""
        for existing in self._knowledge.load_enrichments(
            "chunk", chunk_id, type=ENRICHMENT_TYPE_FORMULA_LATEX
        ):
            if (
                existing.prompt_version == PROMPT_VERSION_FORMULA_LATEX
                and existing.params == params
                and (existing.payload or {}).get("status") == "ready"
            ):
                return True
        return False

    def _save(self, chunk_id: str, params: dict[str, Any], payload: dict[str, Any]) -> None:
        # Deterministic id: re-runs overwrite the same record, never duplicate.
        self._knowledge.save_enrichment(Enrichment(
            id=_deterministic_id(
                "enr", chunk_id, ENRICHMENT_TYPE_FORMULA_LATEX,
                json.dumps(params, sort_keys=True), PROMPT_VERSION_FORMULA_LATEX,
            ),
            scope="chunk",
            owner_id=chunk_id,
            type=ENRICHMENT_TYPE_FORMULA_LATEX,
            params=params,
            prompt_version=PROMPT_VERSION_FORMULA_LATEX,
            payload=payload,
            created_at=_utc_now_iso(),
        ))
