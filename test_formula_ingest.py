#!/usr/bin/env python3
"""
Tests for formula candidate ingestion into the knowledge layer (Этап 6E).

Covers:
- formula_image -> KnowledgeChunk + PNG on disk
- formula_vector -> KnowledgeChunk + PNG on disk
- formula_text -> KnowledgeChunk without PNG / image_path
- locator_payload contents, ordinal sequencing after text chunks
- KnowledgeReadService sees formula chunks
- end-to-end via _process_document_file
- plain PDF (no formulas) ingests exactly as before

No AI involved.
"""

import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pymupdf


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


def _make_plain_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Just an ordinary paragraph.", fontsize=12)
    doc.save(path)
    doc.close()
    return path


def _stores(tmp: str):
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore

    db = Path(tmp) / "videobrain.db"
    return SqliteDocumentStore(db), SqliteKnowledgeStore(db)


def _ingest(tmp: str, extracted, source_path: Path | None, out_root: Path):
    from backend.services.formula_region_renderer import FormulaRegionRenderer
    from backend.services.knowledge_ingest_service import KnowledgeIngestService

    docs, knowledge = _stores(tmp)
    renderer = FormulaRegionRenderer(output_root=out_root)
    ingest = KnowledgeIngestService(docs, knowledge, formula_renderer=renderer)
    document_id = ingest.ingest_extracted_document(
        extracted,
        source_type="pdf",
        content_hash="formula-hash",
        origin_filename="doc.pdf",
        source_path=source_path,
    )
    return docs, knowledge, document_id


def _formula_chunks(chunks):
    return [c for c in chunks if (c.locator_type or "").startswith("formula_")]


def test_formula_image_chunk_and_png():
    print("Testing formula_image -> chunk + PNG...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_formula_pdf(Path(tmp) / "doc.pdf")
        from backend.services.extractors.pdf_extractor import PdfExtractor
        extracted = PdfExtractor().extract(pdf)

        out_root = Path(tmp) / "formula_images"
        docs, knowledge, document_id = _ingest(tmp, extracted, pdf, out_root)
        assert document_id is not None

        chunks = knowledge.load_chunks(document_id)
        image = [c for c in chunks if c.locator_type == "formula_image"]
        assert len(image) == 1, f"expected 1 formula_image chunk, got {len(image)}"
        chunk = image[0]
        assert chunk.text == "", f"formula_image text must be empty: {chunk.text!r}"
        payload = chunk.locator_payload
        assert payload["page"] == 1 and payload["kind"] == "formula_image"
        assert payload["bbox"] == extracted.formulas[1].bbox, f"bbox mismatch: {payload}"
        image_path = Path(payload["image_path"])
        assert image_path.exists(), f"PNG missing: {image_path}"
        assert image_path.parent == out_root / document_id
        assert image_path.name.startswith("p01_f"), f"bad name: {image_path.name}"
    print("✅ formula_image chunk + PNG works")
    return True


def test_formula_vector_chunk_and_png():
    print("Testing formula_vector -> chunk + PNG...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_formula_pdf(Path(tmp) / "doc.pdf")
        from backend.services.extractors.pdf_extractor import PdfExtractor
        extracted = PdfExtractor().extract(pdf)

        docs, knowledge, document_id = _ingest(tmp, extracted, pdf, Path(tmp) / "formula_images")
        chunks = knowledge.load_chunks(document_id)
        vector = [c for c in chunks if c.locator_type == "formula_vector"]
        assert len(vector) == 1, f"expected 1 formula_vector chunk, got {len(vector)}"
        chunk = vector[0]
        assert chunk.text == ""
        payload = chunk.locator_payload
        assert payload["kind"] == "formula_vector" and payload["page"] == 1
        assert "image_path" in payload, f"no image_path: {payload}"
        assert Path(payload["image_path"]).exists()
    print("✅ formula_vector chunk + PNG works")
    return True


def test_formula_text_chunk_without_png():
    print("Testing formula_text -> chunk without PNG...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_formula_pdf(Path(tmp) / "doc.pdf")
        from backend.services.extractors.pdf_extractor import PdfExtractor
        extracted = PdfExtractor().extract(pdf)

        docs, knowledge, document_id = _ingest(tmp, extracted, pdf, Path(tmp) / "formula_images")
        chunks = knowledge.load_chunks(document_id)
        text = [c for c in chunks if c.locator_type == "formula_text"]
        assert len(text) == 1, f"expected 1 formula_text chunk, got {len(text)}"
        chunk = text[0]
        assert "∫" in chunk.text, f"formula_text must carry candidate text: {chunk.text!r}"
        payload = chunk.locator_payload
        assert payload["kind"] == "formula_text"
        assert "image_path" not in payload, f"formula_text must not have image_path: {payload}"
    print("✅ formula_text chunk without PNG works")
    return True


def test_locator_payload_and_ordinals():
    print("Testing locator_payload and ordinal sequencing...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_formula_pdf(Path(tmp) / "doc.pdf")
        from backend.services.extractors.pdf_extractor import PdfExtractor
        extracted = PdfExtractor().extract(pdf)
        text_chunk_count = len(extracted.chunks)
        assert len(extracted.formulas) == 3, f"expected 3 candidates, got {extracted.formulas}"

        docs, knowledge, document_id = _ingest(tmp, extracted, pdf, Path(tmp) / "formula_images")
        chunks = knowledge.load_chunks(document_id)
        assert len(chunks) == text_chunk_count + 3

        # text chunks keep their original ordinals and locators
        for i in range(text_chunk_count):
            assert chunks[i].ordinal == i
            assert chunks[i].locator_type == "pdf_page"
            assert chunks[i].locator_payload == {"page": 1}

        # formula chunks continue the sequence without gaps or collisions
        formula = _formula_chunks(chunks)
        assert [c.ordinal for c in formula] == [
            text_chunk_count, text_chunk_count + 1, text_chunk_count + 2
        ]
        for chunk, candidate in zip(formula, extracted.formulas):
            assert chunk.locator_type == candidate.kind
            assert chunk.locator_payload["page"] == candidate.page
            assert chunk.locator_payload["bbox"] == candidate.bbox
            assert chunk.locator_payload["kind"] == candidate.kind
        # chunk ids stay unique
        assert len({c.id for c in chunks}) == len(chunks)
    print("✅ locator_payload and ordinals work")
    return True


def test_read_service_sees_formula_chunks():
    print("Testing KnowledgeReadService sees formula chunks...")
    from backend.services.extractors.pdf_extractor import PdfExtractor
    from backend.services.knowledge_read_service import KnowledgeReadService

    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_formula_pdf(Path(tmp) / "doc.pdf")
        extracted = PdfExtractor().extract(pdf)
        docs, knowledge, document_id = _ingest(tmp, extracted, pdf, Path(tmp) / "formula_images")

        reader = KnowledgeReadService(docs, knowledge)
        context = reader.get_document_context(document_id)
        assert context is not None
        texts = [c["text"] for c in context["chunks"]]
        assert any("∫" in t for t in texts), f"formula_text not visible: {texts}"
        # image/vector chunks are present too (empty text by design)
        assert len(context["chunks"]) == len(extracted.chunks) + 3
    print("✅ KnowledgeReadService sees formula chunks")
    return True


@contextmanager
def _patched_backend(tmp: str):
    """Route module wired to temp stores with a tmp-rooted formula renderer."""
    import backend.routes.video as video_module
    from backend.config.settings import settings
    from backend.services.formula_region_renderer import FormulaRegionRenderer
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import JsonTaskStore
    from backend.services.task_manager import TaskManager

    docs, knowledge = _stores(tmp)
    manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))
    renderer = FormulaRegionRenderer(output_root=Path(tmp) / "formula_images")
    ingest = KnowledgeIngestService(docs, knowledge, formula_renderer=renderer)
    reader = KnowledgeReadService(docs, knowledge)

    originals = {
        "task_manager": video_module.task_manager,
        "_knowledge_ingest": video_module._knowledge_ingest,
        "_knowledge_reader": video_module._knowledge_reader,
        "default_document_store": video_module.default_document_store,
    }
    original_audio_dir = settings.audio_dir
    try:
        video_module.task_manager = manager
        video_module._knowledge_ingest = ingest
        video_module._knowledge_reader = reader
        video_module.default_document_store = lambda: docs
        settings.audio_dir = Path(tmp) / "audio"
        yield SimpleNamespace(
            manager=manager, docs=docs, knowledge=knowledge,
            ingest=ingest, reader=reader, out_root=Path(tmp) / "formula_images",
        )
    finally:
        for name, value in originals.items():
            setattr(video_module, name, value)
        settings.audio_dir = original_audio_dir
        from backend.services.knowledge_ingest_service import _LOG_PATH
        if _LOG_PATH.exists():
            _LOG_PATH.unlink()


def test_process_document_file_with_formulas():
    print("Testing _process_document_file end-to-end with formulas...")
    import backend.routes.video as video_module

    with tempfile.TemporaryDirectory() as tmp, _patched_backend(tmp) as env:
        pdf = _make_formula_pdf(Path(tmp) / "upload.pdf")

        task_id = str(uuid.uuid4())
        env.manager.create(task_id, source="file")
        video_module._process_document_file(
            task_id, str(pdf), content_hash="e2e-hash", origin_filename="upload.pdf",
        )

        task = env.manager.get(task_id)
        assert task.status == "completed", f"task failed: {task.error}"
        assert task.document_id is not None

        chunks = env.knowledge.load_chunks(task.document_id)
        formula = _formula_chunks(chunks)
        assert len(formula) == 3, f"expected 3 formula chunks, got {len(formula)}"
        for chunk in formula:
            if chunk.locator_type in ("formula_image", "formula_vector"):
                image_path = Path(chunk.locator_payload["image_path"])
                assert image_path.exists(), f"PNG missing: {image_path}"
                assert env.out_root in image_path.parents
    print("✅ _process_document_file with formulas works")
    return True


def test_plain_pdf_unchanged():
    print("Testing plain PDF ingests as before...")
    from backend.services.extractors.pdf_extractor import PdfExtractor

    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_plain_pdf(Path(tmp) / "doc.pdf")
        extracted = PdfExtractor().extract(pdf)
        assert extracted.formulas == []

        out_root = Path(tmp) / "formula_images"
        docs, knowledge, document_id = _ingest(tmp, extracted, pdf, out_root)
        chunks = knowledge.load_chunks(document_id)
        assert len(chunks) == 1
        assert chunks[0].ordinal == 0
        assert chunks[0].locator_type == "pdf_page"
        assert chunks[0].locator_payload == {"page": 1}
        assert _formula_chunks(chunks) == []
        assert not out_root.exists(), "no formula images may be rendered"
    print("✅ Plain PDF unchanged")
    return True


def main() -> int:
    tests = [
        test_formula_image_chunk_and_png,
        test_formula_vector_chunk_and_png,
        test_formula_text_chunk_without_png,
        test_locator_payload_and_ordinals,
        test_read_service_sees_formula_chunks,
        test_process_document_file_with_formulas,
        test_plain_pdf_unchanged,
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
