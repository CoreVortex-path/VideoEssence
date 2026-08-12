#!/usr/bin/env python3
"""
Tests for library reuse (auto-dedup) and translation persistence.

Covers:
- process-file: same content twice -> same document and same completed
  task, pipeline runs once; unknown content -> fresh run (regression)
- process-url: watch?v=X and youtu.be/X resolve to one document
  (deterministic "youtube:{video_id}" content key), download happens once;
  downloaded media is kept for GET /documents/{id}/media
- translations: translate endpoint shadow-writes; the knowledge read path
  (assemble_status) serves translation_results after a "reopen"
- extract_youtube_video_id URL forms

Runs against TestClient with stubbed Whisper/AI/yt-dlp in temp directories.
"""

import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

# Windows consoles may default to cp1251; emoji markers need UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_SEGMENTS = [
    {"start": 0.0, "end": 1.5, "text": "first segment"},
    {"start": 1.5, "end": 3.0, "text": "second segment"},
]
_CHAPTERS = [{"title": "Intro", "summary": "opening", "start": 0.0}]


class _StubTranscriber:
    def __init__(self, model_size: str = "tiny"):
        pass

    def transcribe_with_segments(self, audio_path):
        return "first segment\nsecond segment", [dict(s) for s in _SEGMENTS], "ru"


class _StubProvider:
    def summarize_with_chapters(self, segments, source_language=None):
        return {
            "summary": "a summary",
            "chapters": [dict(c) for c in _CHAPTERS],
            "language": "russian",
        }


class _StubProfile:
    id = "gemini_flash"
    display_name = "Gemini Flash"
    provider = "gemini"
    model = "gemini-2.5-flash"


class _StubEnrichmentService:
    """Переводит без AI: оборачивает текст сегмента маркером."""

    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_NOT_GENERATED = "not_generated"

    def __init__(self, provider, token_limits=None, **kwargs):
        pass

    def enrich_segments(self, transcript_segments, source_language=None, target_language="Russian"):
        return [
            {
                **dict(seg),
                "enrichment": {
                    "translation": f"ПЕРЕВОД: {seg['text']}",
                    "translation_status": "ready",
                    "translation_error": None,
                    "key_concepts": [],
                    "entities": [],
                    "tags": [],
                    "extra": {},
                },
            }
            for seg in transcript_segments
        ]

    def build_full_translation(self, enriched):
        return "\n\n".join(seg["enrichment"]["translation"] for seg in enriched)


@contextmanager
def _patched_backend(tmp: str):
    """Real temp stores + stubbed Whisper/AI/download; restores everything."""
    import backend.routes.video as video_module
    from backend.config.settings import settings
    from backend.services.input_processor import InputSourceType
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import (
        JsonTaskStore,
        SqliteDocumentStore,
        SqliteKnowledgeStore,
    )
    from backend.services.task_manager import TaskManager

    db = Path(tmp) / "videobrain.db"
    docs = SqliteDocumentStore(db)
    knowledge = SqliteKnowledgeStore(db)
    manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))
    ingest = KnowledgeIngestService(docs, knowledge)
    reader = KnowledgeReadService(docs, knowledge)

    counters = {"pipeline": 0, "download": 0}
    original_pipeline = video_module._process_file_with_ai_profile

    def counting_pipeline(*args, **kwargs):
        counters["pipeline"] += 1
        return original_pipeline(*args, **kwargs)

    class StubFileSource:
        def extract_audio(self, input_data, task_id, output_dir):
            return input_data  # pretend extraction

    class StubYouTubeSource:
        def extract_audio(self, url, task_id, output_dir):
            counters["download"] += 1
            path = Path(output_dir) / f"{task_id}.mp3"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake youtube audio")
            return str(path)

    def fake_input_source(source_type):
        if source_type == InputSourceType.YOUTUBE:
            return StubYouTubeSource()
        return StubFileSource()

    originals = {
        "task_manager": video_module.task_manager,
        "_knowledge_ingest": video_module._knowledge_ingest,
        "_knowledge_reader": video_module._knowledge_reader,
        "_process_file_with_ai_profile": original_pipeline,
        "Transcriber": video_module.Transcriber,
        "get_ai_provider": video_module.get_ai_provider,
        "get_input_source": video_module.get_input_source,
        "fetch_youtube_title": video_module.fetch_youtube_title,
        "default_document_store": video_module.default_document_store,
        "TranscriptEnrichmentService": video_module.TranscriptEnrichmentService,
    }
    original_dirs = (settings.transcripts_dir, settings.summaries_dir, settings.audio_dir)
    try:
        video_module.task_manager = manager
        video_module._knowledge_ingest = ingest
        video_module._knowledge_reader = reader
        video_module._process_file_with_ai_profile = counting_pipeline
        video_module.Transcriber = _StubTranscriber
        video_module.get_ai_provider = lambda pid: (_StubProfile(), _StubProvider())
        video_module.get_input_source = fake_input_source
        video_module.fetch_youtube_title = lambda url: "Stub Title"
        video_module.default_document_store = lambda: docs
        video_module.TranscriptEnrichmentService = _StubEnrichmentService
        settings.transcripts_dir = Path(tmp) / "transcripts"
        settings.summaries_dir = Path(tmp) / "summaries"
        settings.audio_dir = Path(tmp) / "audio"
        yield SimpleNamespace(
            manager=manager,
            docs=docs,
            knowledge=knowledge,
            ingest=ingest,
            reader=reader,
            counters=counters,
        )
    finally:
        for name, value in originals.items():
            setattr(video_module, name, value)
        (settings.transcripts_dir, settings.summaries_dir, settings.audio_dir) = original_dirs
        # Do not pollute the real shadow log with test entries.
        from backend.services.knowledge_ingest_service import _LOG_PATH
        if _LOG_PATH.exists():
            _LOG_PATH.unlink()


def _client():
    from fastapi.testclient import TestClient
    from backend.app import app

    return TestClient(app)


def _post_file(client, content: bytes, filename: str = "lecture.mp3"):
    return client.post(
        "/videos/process-file",
        files={"file": (filename, content, "audio/mpeg")},
        data={"model_size": "tiny", "ai_profile": "gemini_flash"},
    )


def test_process_file_reuse():
    """Same file content twice -> same task/document, pipeline runs once."""
    print("Testing process-file library reuse...")
    with tempfile.TemporaryDirectory() as tmp, _patched_backend(tmp) as env:
        client = _client()

        r1 = _post_file(client, b"same audio content")
        assert r1.status_code == 202, r1.text
        task_id = r1.json()["task_id"]
        task = env.manager.get(task_id)
        assert task.status == "completed", f"task failed: {task.error}"
        assert task.document_id is not None
        assert env.counters["pipeline"] == 1

        # Second upload of the same content: reuse, no new pipeline run.
        r2 = _post_file(client, b"same audio content")
        assert r2.status_code == 202, r2.text
        assert r2.json()["task_id"] == task_id, "must return the existing task"
        assert r2.json()["status"] == "completed"
        assert env.counters["pipeline"] == 1, "pipeline must not re-run"
        assert len(env.docs.list_ids()) == 1

        # The returned task is immediately pollable with the full result.
        status = client.get(f"/videos/status/{task_id}")
        assert status.status_code == 200
        assert status.json()["summary"] == "a summary"

        # Regression: different content -> fresh run, new task.
        r3 = _post_file(client, b"another audio content")
        assert r3.status_code == 202, r3.text
        assert r3.json()["task_id"] != task_id
        assert env.counters["pipeline"] == 2

    print("✅ process-file: reuse by content hash, regression intact")
    return True


def test_process_url_reuse():
    """watch?v=X and youtu.be/X -> one document, one download, media kept."""
    print("\nTesting process-url library reuse...")
    with tempfile.TemporaryDirectory() as tmp, _patched_backend(tmp) as env:
        client = _client()
        video_id = "abc123XYZ_0"

        r1 = client.post(
            "/videos/process-url",
            json={"url": f"https://www.youtube.com/watch?v={video_id}"},
        )
        assert r1.status_code == 202, r1.text
        task_id = r1.json()["task_id"]
        task = env.manager.get(task_id)
        assert task.status == "completed", f"task failed: {task.error}"
        assert env.counters["download"] == 1

        # Deterministic content key: youtube:{video_id}.
        document = env.docs.load(task.document_id)
        assert document is not None
        assert document.content_hash == f"youtube:{video_id}"

        # Same video, different URL form -> reuse before downloading.
        r2 = client.post(
            "/videos/process-url",
            json={"url": f"https://youtu.be/{video_id}"},
        )
        assert r2.status_code == 202, r2.text
        assert r2.json()["task_id"] == task_id
        assert env.counters["download"] == 1, "download must not re-run"
        assert len(env.docs.list_ids()) == 1

        # Media survives (no cleanup): document media endpoint serves it.
        assert task.media_path and Path(task.media_path).exists()
        media = client.get(f"/videos/documents/{task.document_id}/media")
        assert media.status_code == 200

        # Regression: unknown video id -> fresh download, new task.
        r3 = client.post(
            "/videos/process-url",
            json={"url": "https://www.youtube.com/watch?v=zzz999YYY_8"},
        )
        assert r3.status_code == 202, r3.text
        assert r3.json()["task_id"] != task_id
        assert env.counters["download"] == 2

    print("✅ process-url: reuse by youtube:{video_id}, media kept, regression intact")
    return True


def test_translations_survive_reopen():
    """Translate -> shadow write -> assemble_status serves translations."""
    print("\nTesting translation persistence across reopen...")
    with tempfile.TemporaryDirectory() as tmp, _patched_backend(tmp) as env:
        client = _client()

        r = _post_file(client, b"translatable content")
        assert r.status_code == 202, r.text
        task_id = r.json()["task_id"]
        task = env.manager.get(task_id)
        assert task.status == "completed", f"task failed: {task.error}"

        r = client.post(
            f"/videos/status/{task_id}/translate",
            json={"target_language": "ru"},
        )
        assert r.status_code == 200, r.text
        segments = r.json()["transcript_segments"]
        assert segments[0]["enrichment"]["translation"] == "ПЕРЕВОД: first segment"

        # Shadow write happened: chunk-scoped translation enrichments exist.
        chunks = env.knowledge.load_chunks(task.document_id)
        assert len(chunks) == 2
        enrichments = env.knowledge.load_enrichments(
            "chunk", chunks[0].id, type="translation"
        )
        assert len(enrichments) == 1
        assert enrichments[0].payload["text"] == "ПЕРЕВОД: first segment"

        # Reopen via the knowledge read path: same task AND a fresh task
        # record for the same document (no translation_results of its own).
        from backend.services.storage import Task

        for reopened in (
            env.manager.get(task_id),
            Task(
                id=str(uuid.uuid4()),
                source="file",
                status="completed",
                progress="Task completed",
                document_id=task.document_id,
            ),
        ):
            payload = env.reader.assemble_status(reopened)
            assert payload is not None
            results = payload["translation_results"]
            assert "gemini_flash:russian" in results, f"cache keys: {list(results)}"
            entry = results["gemini_flash:russian"]
            assert entry["target_language"] == "Russian"
            assert len(entry["transcript_segments"]) == 2
            assert (
                entry["transcript_segments"][1]["enrichment"]["translation"]
                == "ПЕРЕВОД: second segment"
            )
            assert "ПЕРЕВОД: first segment" in entry["full_translation"]

        # Status endpoint (knowledge read is enabled by default) exposes them.
        status = client.get(f"/videos/status/{task_id}")
        assert status.status_code == 200
        assert "gemini_flash:russian" in status.json()["translation_results"]

    print("✅ Translations shadow-written and served after reopen")
    return True


def test_extract_youtube_video_id():
    """URL forms normalize to the same video id; junk -> None."""
    print("\nTesting extract_youtube_video_id forms...")
    from backend.services.input_sources.youtube_source import extract_youtube_video_id

    video_id = "abc123XYZ_0"
    forms = [
        f"https://www.youtube.com/watch?v={video_id}",
        f"https://youtube.com/watch?v={video_id}&t=42s",
        f"https://m.youtube.com/watch?v={video_id}",
        f"https://youtu.be/{video_id}",
        f"https://youtu.be/{video_id}?si=tracker",
        f"https://www.youtube.com/shorts/{video_id}",
        f"https://www.youtube.com/embed/{video_id}",
    ]
    for url in forms:
        assert extract_youtube_video_id(url) == video_id, url

    assert extract_youtube_video_id("https://example.com/watch?v=nope") is None
    assert extract_youtube_video_id("") is None
    assert extract_youtube_video_id("not a url") is None

    print("✅ extract_youtube_video_id: all forms parsed, junk rejected")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Library Reuse - Test Suite")
    print("=" * 60)

    tests = [
        test_process_file_reuse,
        test_process_url_reuse,
        test_translations_survive_reopen,
        test_extract_youtube_video_id,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except AssertionError as e:
            print(f"❌ Assertion failed: {e}")
            results.append(False)
        except Exception as e:
            print(f"❌ Test crashed: {e}")
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
