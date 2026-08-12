#!/usr/bin/env python3
"""
Tests for the PDF/FB2 document ingestion pipeline (Этап 5).

Covers:
- get_extractor registry (pdf / fb2 / unsupported)
- KnowledgeIngestService.ingest_extracted_document: PDF and FB2,
  deterministic document_id, locator preservation, language_source
- _process_document_file: task completed, KnowledgeReadService sees chunks
- broken PDF/FB2 -> task failed with a clear error
- POST /videos/process-file: same file twice -> library reuse path

Runs against real temp stores; no AI involved (document path bypasses it).
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

FB2_NS = "http://www.gribuser.ru/xml/fictionbook/2.0"


def _pdf_bytes(pages: list[str], title: str | None = None) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    if title is not None:
        doc.set_metadata({"title": title})
    data = doc.tobytes()
    doc.close()
    return data


def _fb2_text(sections: list[str], title: str | None = "FB2 Book", lang: str | None = "ru") -> str:
    title_xml = f"<book-title>{title}</book-title>" if title is not None else ""
    lang_xml = f"<lang>{lang}</lang>" if lang is not None else ""
    body = "".join(
        f"<section><p>{paragraph}</p></section>" for paragraph in sections
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<FictionBook xmlns="{FB2_NS}">'
        f"<description><title-info>{title_xml}{lang_xml}</title-info></description>"
        f"<body>{body}</body>"
        "</FictionBook>"
    )


def _stores(tmp: str):
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore

    db = Path(tmp) / "videobrain.db"
    return SqliteDocumentStore(db), SqliteKnowledgeStore(db)


@contextmanager
def _patched_backend(tmp: str):
    """Route module wired to temp stores/task manager; restores everything."""
    import backend.routes.video as video_module
    from backend.config.settings import settings
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import JsonTaskStore
    from backend.services.task_manager import TaskManager

    docs, knowledge = _stores(tmp)
    manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))
    ingest = KnowledgeIngestService(docs, knowledge)
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
            ingest=ingest, reader=reader,
        )
    finally:
        for name, value in originals.items():
            setattr(video_module, name, value)
        settings.audio_dir = original_audio_dir
        # Do not pollute the real shadow log with test entries.
        from backend.services.knowledge_ingest_service import _LOG_PATH
        if _LOG_PATH.exists():
            _LOG_PATH.unlink()


def test_get_extractor():
    print("Testing get_extractor registry...")
    from backend.services.extractors import (
        get_document_source_type,
        get_extractor,
    )
    from backend.services.extractors.fb2_extractor import Fb2Extractor
    from backend.services.extractors.pdf_extractor import PdfExtractor

    assert isinstance(get_extractor(Path("book.pdf")), PdfExtractor)
    assert isinstance(get_extractor(Path("BOOK.PDF")), PdfExtractor)
    assert isinstance(get_extractor(Path("book.fb2")), Fb2Extractor)
    assert get_extractor(Path("song.mp3")) is None
    assert get_extractor(Path("movie.mp4")) is None
    assert get_extractor(Path("noext")) is None

    assert get_document_source_type(Path("book.pdf")) == "pdf"
    assert get_document_source_type(Path("book.fb2")) == "fb2"
    assert get_document_source_type(Path("song.mp3")) is None
    print("✅ get_extractor registry works")
    return True


def test_pdf_ingestion():
    print("Testing PDF ingestion...")
    from backend.services.extractors import get_extractor
    from backend.services.knowledge_ingest_service import KnowledgeIngestService

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "doc.pdf"
        pdf.write_bytes(_pdf_bytes(["Page one text", "Page two text"], title="PDF Title"))
        extracted = get_extractor(pdf).extract(pdf)

        docs, knowledge = _stores(tmp)
        ingest = KnowledgeIngestService(docs, knowledge)
        document_id = ingest.ingest_extracted_document(
            extracted,
            source_type="pdf",
            content_hash="pdf-hash-1",
            origin_filename="doc.pdf",
        )
        assert document_id is not None

        document = docs.load(document_id)
        assert document.source_type == "pdf", f"bad source_type: {document.source_type}"
        assert document.title == "PDF Title"
        assert document.content_hash == "pdf-hash-1"
        assert document.primary_language is None  # PDFs carry no language metadata
        assert document.language_source is None

        chunks = knowledge.load_chunks(document_id)
        assert len(chunks) == 2
        for i, chunk in enumerate(chunks):
            assert chunk.ordinal == i
            assert chunk.locator_type == "pdf_page"
            assert chunk.locator_payload == {"page": i + 1}
            assert chunk.start is None and chunk.end is None
    print("✅ PDF ingestion works")
    return True


def test_fb2_ingestion():
    print("Testing FB2 ingestion...")
    from backend.services.extractors import get_extractor
    from backend.services.knowledge_ingest_service import KnowledgeIngestService

    with tempfile.TemporaryDirectory() as tmp:
        fb2 = Path(tmp) / "book.fb2"
        fb2.write_text(_fb2_text(["Section one", "Section two"]), encoding="utf-8")
        extracted = get_extractor(fb2).extract(fb2)

        docs, knowledge = _stores(tmp)
        ingest = KnowledgeIngestService(docs, knowledge)
        document_id = ingest.ingest_extracted_document(
            extracted,
            source_type="fb2",
            content_hash="fb2-hash-1",
            origin_filename="book.fb2",
        )
        assert document_id is not None

        document = docs.load(document_id)
        assert document.source_type == "fb2"
        assert document.title == "FB2 Book"
        assert document.primary_language == "ru"
        assert document.language_source == "declared", (
            f"bad language_source: {document.language_source}"
        )

        chunks = knowledge.load_chunks(document_id)
        assert len(chunks) == 2
        for i, chunk in enumerate(chunks):
            assert chunk.ordinal == i
            assert chunk.locator_type == "fb2_section"
            assert chunk.locator_payload == {"section": i + 1}

        # No language in metadata -> language_source stays unset.
        fb2_no_lang = Path(tmp) / "nolаng.fb2".replace("а", "a")
        fb2_no_lang.write_text(_fb2_text(["Text"], lang=None), encoding="utf-8")
        extracted2 = get_extractor(fb2_no_lang).extract(fb2_no_lang)
        document_id2 = ingest.ingest_extracted_document(
            extracted2, source_type="fb2",
            content_hash="fb2-hash-2", origin_filename="nolang.fb2",
        )
        document2 = docs.load(document_id2)
        assert document2.primary_language is None
        assert document2.language_source is None
    print("✅ FB2 ingestion works")
    return True


def test_deterministic_document_id():
    print("Testing deterministic document_id...")
    from backend.services.extractors import get_extractor
    from backend.services.knowledge_ingest_service import KnowledgeIngestService

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "doc.pdf"
        pdf.write_bytes(_pdf_bytes(["Same content"]))
        extracted = get_extractor(pdf).extract(pdf)

        docs, knowledge = _stores(tmp)
        first = KnowledgeIngestService(docs, knowledge).ingest_extracted_document(
            extracted, source_type="pdf",
            content_hash="same-hash", origin_filename="doc.pdf",
        )
        # Fresh service instance over the same stores: same content hash ->
        # the very same document id (this is what library reuse relies on).
        second = KnowledgeIngestService(docs, knowledge).ingest_extracted_document(
            extracted, source_type="pdf",
            content_hash="same-hash", origin_filename="renamed.pdf",
        )
        assert first == second, f"ids differ: {first} vs {second}"
        assert len(docs.list_ids()) == 1
    print("✅ Deterministic document_id works")
    return True


def test_process_document_file_completed():
    print("Testing _process_document_file -> completed...")
    import backend.routes.video as video_module

    with tempfile.TemporaryDirectory() as tmp, _patched_backend(tmp) as env:
        pdf = Path(tmp) / "upload.pdf"
        pdf.write_bytes(_pdf_bytes(["Hello document pipeline"], title="Pipe Title"))

        task_id = str(uuid.uuid4())
        env.manager.create(task_id, source="file")
        video_module._process_document_file(
            task_id, str(pdf), content_hash="pipe-hash", origin_filename="upload.pdf",
        )

        task = env.manager.get(task_id)
        assert task.status == "completed", f"task failed: {task.error}"
        assert task.document_id is not None
        assert "Hello document pipeline" in task.transcript
        assert task.title == "Pipe Title"

        # The read service sees the ingested chunks.
        context = env.reader.get_document_context(task.document_id)
        assert context is not None
        assert context["title"] == "Pipe Title"
        assert len(context["chunks"]) == 1
        assert context["chunks"][0]["text"] == "Hello document pipeline"
    print("✅ _process_document_file completes and is readable")
    return True


def test_broken_document_failed():
    print("Testing broken PDF/FB2 -> failed...")
    import backend.routes.video as video_module

    with tempfile.TemporaryDirectory() as tmp, _patched_backend(tmp) as env:
        for name, content in (
            ("broken.pdf", b"this is not a pdf at all"),
            ("broken.fb2", "not xml <".encode()),
        ):
            path = Path(tmp) / name
            path.write_bytes(content)
            task_id = str(uuid.uuid4())
            env.manager.create(task_id, source="file")
            video_module._process_document_file(
                task_id, str(path), content_hash=f"hash-{name}", origin_filename=name,
            )
            task = env.manager.get(task_id)
            assert task.status == "failed", f"{name}: status {task.status}"
            assert task.error, f"{name}: empty error message"
        assert env.docs.list_ids() == [], "no documents may be created on failure"
    print("✅ Broken documents fail with a clear error")
    return True


def test_http_upload_and_reuse():
    print("Testing POST /process-file for PDF + reuse...")
    from fastapi.testclient import TestClient
    from backend.app import app

    with tempfile.TemporaryDirectory() as tmp, _patched_backend(tmp) as env:
        client = TestClient(app)
        pdf = _pdf_bytes(["Reuse me"], title="Reuse Title")

        r1 = client.post(
            "/videos/process-file",
            files={"file": ("paper.pdf", pdf, "application/pdf")},
            data={"model_size": "tiny", "ai_profile": "gemini_flash"},
        )
        assert r1.status_code == 202, r1.text
        task_id = r1.json()["task_id"]
        task = env.manager.get(task_id)
        assert task.status == "completed", f"task failed: {task.error}"
        assert task.document_id is not None
        assert env.docs.load(task.document_id).source_type == "pdf"

        # The uploaded source file is kept.
        assert task.media_path and Path(task.media_path).exists()

        # Second upload of the same bytes: existing reuse path, no new task.
        r2 = client.post(
            "/videos/process-file",
            files={"file": ("paper-copy.pdf", pdf, "application/pdf")},
            data={"model_size": "tiny", "ai_profile": "gemini_flash"},
        )
        assert r2.status_code == 202, r2.text
        assert r2.json()["task_id"] == task_id, "must reuse the existing task"
        assert r2.json()["status"] == "completed"
        assert len(env.docs.list_ids()) == 1

        # Regression: different content -> new task.
        r3 = client.post(
            "/videos/process-file",
            files={"file": ("other.pdf", _pdf_bytes(["Different"]), "application/pdf")},
            data={"model_size": "tiny", "ai_profile": "gemini_flash"},
        )
        assert r3.status_code == 202, r3.text
        assert r3.json()["task_id"] != task_id
        assert len(env.docs.list_ids()) == 2

        # FB2 upload goes through the same endpoint.
        r4 = client.post(
            "/videos/process-file",
            files={"file": ("book.fb2", _fb2_text(["FB2 via HTTP"]), "application/octet-stream")},
            data={"model_size": "tiny", "ai_profile": "gemini_flash"},
        )
        assert r4.status_code == 202, r4.text
        task4 = env.manager.get(r4.json()["task_id"])
        assert task4.status == "completed", f"task failed: {task4.error}"
        assert env.docs.load(task4.document_id).source_type == "fb2"
    print("✅ HTTP upload + library reuse works")
    return True


def main() -> int:
    tests = [
        test_get_extractor,
        test_pdf_ingestion,
        test_fb2_ingestion,
        test_deterministic_document_id,
        test_process_document_file_completed,
        test_broken_document_failed,
        test_http_upload_and_reuse,
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
