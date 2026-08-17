#!/usr/bin/env python3
"""
Tests for FormulaVisionService (Этап 6F) — no real AI involved.

Covers:
- formula_image/formula_vector/formula_region chunks -> formula_latex enrichment
- enrichment identity: scope/owner/type/params/prompt_version/payload
- dedup: a second run makes no new recognizer calls, no duplicate records
- formula_text chunks never reach the recognizer
- missing image_path / missing PNG file -> skipped, no recognizer call
- recognizer error / UNRECOGNIZED -> failed enrichment, rerun overwrites
- recognizer factory failure (no vision support) -> zero counters, no raise
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pymupdf

from backend.services.ai_provider import AIProfile
from backend.services.formula_recognizer import UNRECOGNIZED_MARKER
from backend.services.formula_vision_service import (
    ENRICHMENT_TYPE_FORMULA_LATEX,
    PROMPT_VERSION_FORMULA_LATEX,
    FormulaVisionService,
)

MOCK_PROFILE = AIProfile(id="mock_vision", display_name="Mock", provider="mock", model="mock-1")
MOCK_PARAMS = {"ai_profile": "mock_vision", "ai_model": "mock-1"}


class MockRecognizer:
    def __init__(self, latex="\\frac{a}{b}", error: Exception | None = None):
        self.latex = latex
        self.error = error
        self.calls: list[Path] = []

    def recognize_latex(self, image_path: Path) -> str:
        self.calls.append(image_path)
        if self.error is not None:
            raise self.error
        return self.latex


def _mock_factory(recognizer):
    return lambda profile_id: (MOCK_PROFILE, recognizer)


def _failing_factory(profile_id):
    raise RuntimeError("profile does not support image input")


def _make_formula_pdf(path: Path) -> Path:
    """One page: plain text + math-symbol line + image + vector fraction."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Plain paragraph.", fontsize=12)
    page.insert_text((72, 100), "∫ f(x) dx = F(b) - F(a)", fontname="china-s", fontsize=12)
    pm = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40))
    pm.clear_with(30)
    page.insert_image(pymupdf.Rect(100, 150, 190, 210), pixmap=pm)
    page.insert_text((120, 292), "a", fontsize=12)
    page.insert_text((120, 320), "b", fontsize=12)
    page.draw_line((100, 300), (160, 300))
    page.draw_line((100, 306), (160, 306))
    doc.save(path)
    doc.close()
    return path


def _ingest_with_formulas(tmp: str):
    """Extract + ingest the formula PDF; return (knowledge, document_id)."""
    from backend.services.extractors.pdf_extractor import PdfExtractor
    from backend.services.formula_region_renderer import FormulaRegionRenderer
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore

    pdf = _make_formula_pdf(Path(tmp) / "doc.pdf")
    extracted = PdfExtractor().extract(pdf)
    db = Path(tmp) / "videobrain.db"
    docs = SqliteDocumentStore(db)
    knowledge = SqliteKnowledgeStore(db)
    renderer = FormulaRegionRenderer(output_root=Path(tmp) / "formula_images")
    ingest = KnowledgeIngestService(docs, knowledge, formula_renderer=renderer)
    document_id = ingest.ingest_extracted_document(
        extracted, source_type="pdf", content_hash="vision-hash",
        origin_filename="doc.pdf", source_path=pdf,
    )
    assert document_id is not None
    return knowledge, document_id


def _formula_enrichments(knowledge, document_id):
    result = []
    for chunk in knowledge.load_chunks(document_id):
        result.extend(knowledge.load_enrichments(
            "chunk", chunk.id, type=ENRICHMENT_TYPE_FORMULA_LATEX
        ))
    return result


def test_ready_enrichment_written():
    print("Testing formula_latex enrichment is written...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        recognizer = MockRecognizer()
        service = FormulaVisionService(knowledge, _mock_factory(recognizer))
        counters = service.enrich_formulas(document_id)

        chunks = knowledge.load_chunks(document_id)
        vision_chunks = [
            c for c in chunks
            if c.locator_type in ("formula_image", "formula_vector", "formula_region")
        ]
        assert counters == {"ready": len(vision_chunks), "failed": 0, "skipped": 0}, counters
        assert len(recognizer.calls) == len(vision_chunks)

        for chunk in vision_chunks:
            enrichments = knowledge.load_enrichments(
                "chunk", chunk.id, type=ENRICHMENT_TYPE_FORMULA_LATEX
            )
            assert len(enrichments) == 1
            enr = enrichments[0]
            assert enr.scope == "chunk" and enr.owner_id == chunk.id
            assert enr.type == "formula_latex"
            assert enr.params == MOCK_PARAMS, f"bad params: {enr.params}"
            assert enr.prompt_version == PROMPT_VERSION_FORMULA_LATEX
            assert enr.payload == {"latex": "\\frac{a}{b}", "status": "ready", "error": None}
    print("✅ formula_latex enrichment works")
    return True


def test_dedup_second_run():
    print("Testing dedup on second run...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        recognizer = MockRecognizer()
        service = FormulaVisionService(knowledge, _mock_factory(recognizer))
        first = service.enrich_formulas(document_id)
        calls_after_first = len(recognizer.calls)

        second = service.enrich_formulas(document_id)
        assert len(recognizer.calls) == calls_after_first, "recognizer called again"
        assert second["ready"] == 0 and second["skipped"] == first["ready"]
        assert len(_formula_enrichments(knowledge, document_id)) == first["ready"], (
            "duplicate enrichment records created"
        )
    print("✅ Dedup works")
    return True


def test_formula_text_never_calls_recognizer():
    print("Testing formula_text never reaches the recognizer...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        recognizer = MockRecognizer()
        FormulaVisionService(knowledge, _mock_factory(recognizer)).enrich_formulas(document_id)

        text_chunks = [
            c for c in knowledge.load_chunks(document_id)
            if c.locator_type == "formula_text"
        ]
        assert text_chunks, "fixture must contain a formula_text chunk"
        for chunk in text_chunks:
            assert knowledge.load_enrichments(
                "chunk", chunk.id, type=ENRICHMENT_TYPE_FORMULA_LATEX
            ) == []
        for call in recognizer.calls:
            assert "formula_text" not in call.name
    print("✅ formula_text is never sent to vision")
    return True


def test_missing_image_path_skipped():
    print("Testing missing image_path -> skipped, no call...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        # Strip image_path from every formula chunk.
        chunks = knowledge.load_chunks(document_id)
        for chunk in chunks:
            if (chunk.locator_type or "").startswith("formula_") and chunk.locator_payload:
                chunk.locator_payload = {
                    k: v for k, v in chunk.locator_payload.items() if k != "image_path"
                }
        knowledge.save_chunks(document_id, chunks)

        recognizer = MockRecognizer()
        counters = FormulaVisionService(
            knowledge, _mock_factory(recognizer)
        ).enrich_formulas(document_id)
        assert recognizer.calls == [], "recognizer must not be called"
        assert counters["ready"] == 0 and counters["skipped"] >= 1, counters
    print("✅ Missing image_path handled")
    return True


def test_missing_image_file_skipped():
    print("Testing missing PNG file -> skipped, no call...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        for chunk in knowledge.load_chunks(document_id):
            payload = chunk.locator_payload or {}
            if payload.get("image_path"):
                Path(payload["image_path"]).unlink()

        recognizer = MockRecognizer()
        counters = FormulaVisionService(
            knowledge, _mock_factory(recognizer)
        ).enrich_formulas(document_id)
        assert recognizer.calls == []
        assert counters["ready"] == 0 and counters["skipped"] >= 1, counters
    print("✅ Missing image file handled")
    return True


def test_recognizer_error_failed_then_overwritten():
    print("Testing recognizer error -> failed enrichment, rerun overwrites...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        failing = MockRecognizer(error=RuntimeError("AI timeout"))
        service = FormulaVisionService(knowledge, _mock_factory(failing))
        counters = service.enrich_formulas(document_id)
        assert counters["failed"] >= 1 and counters["ready"] == 0, counters

        failed_enrichments = _formula_enrichments(knowledge, document_id)
        assert all(e.payload["status"] == "failed" for e in failed_enrichments)
        assert all("AI timeout" in e.payload["error"] for e in failed_enrichments)
        failed_ids = {e.id for e in failed_enrichments}

        # Rerun with a healthy recognizer: same ids, status flips to ready.
        healthy = MockRecognizer()
        service2 = FormulaVisionService(knowledge, _mock_factory(healthy))
        counters2 = service2.enrich_formulas(document_id)
        assert counters2["ready"] == counters["failed"]
        now = _formula_enrichments(knowledge, document_id)
        assert {e.id for e in now} == failed_ids, "rerun must overwrite, not duplicate"
        assert all(e.payload["status"] == "ready" for e in now)
    print("✅ Recognizer error handled")
    return True


def test_unrecognized_marker_failed():
    print("Testing UNRECOGNIZED response -> failed enrichment...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        recognizer = MockRecognizer(latex=UNRECOGNIZED_MARKER)
        counters = FormulaVisionService(
            knowledge, _mock_factory(recognizer)
        ).enrich_formulas(document_id)
        assert counters["ready"] == 0 and counters["failed"] >= 1, counters
        for enr in _formula_enrichments(knowledge, document_id):
            assert enr.payload["status"] == "failed"
            assert enr.payload["latex"] is None
    print("✅ UNRECOGNIZED handled")
    return True


def test_factory_failure_returns_zeros():
    print("Testing recognizer factory failure -> zeros, no raise...")
    with tempfile.TemporaryDirectory() as tmp:
        knowledge, document_id = _ingest_with_formulas(tmp)
        counters = FormulaVisionService(knowledge, _failing_factory).enrich_formulas(document_id)
        assert counters == {"ready": 0, "failed": 0, "skipped": 0}, counters
        assert _formula_enrichments(knowledge, document_id) == []
        # Document and chunks are untouched.
        assert knowledge.load_chunks(document_id), "chunks must survive"
    print("✅ Factory failure handled")
    return True


def main() -> int:
    tests = [
        test_ready_enrichment_written,
        test_dedup_second_run,
        test_formula_text_never_calls_recognizer,
        test_missing_image_path_skipped,
        test_missing_image_file_skipped,
        test_recognizer_error_failed_then_overwritten,
        test_unrecognized_marker_failed,
        test_factory_failure_returns_zeros,
    ]
    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except AssertionError as exc:
            print(f"❌ Assertion failed: {exc}")
            results.append(False)
        except Exception as exc:
            print(f"❌ Test crashed: {exc}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    if all(results):
        print("✅ All tests passed!")
        return 0
    print("❌ Some tests failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
