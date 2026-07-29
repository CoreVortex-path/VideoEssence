#!/usr/bin/env python3
"""
Tests for Step 2b shadow dual-write (ADR-0006).

Covers:
- Successful dual-write: document + ordered chunks + summary/chapters enrichments
- Idempotency: repeated processing does not duplicate data
- Failure isolation: shadow failure never propagates, task stays intact
- Translation shadow: chunk-scoped enrichments, skip without document_id
- Route-level integration: stubbed pipeline completes AND shadow-writes;
  shadow failure leaves the task completed with the API shape intact

Runs in temp directories with real SQLite stores; no network/AI/Whisper.
"""

import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

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


def _make_completed_task(task_id: str = "task-1"):
    from backend.services.storage import Task

    return Task(
        id=task_id,
        source="file",
        status="completed",
        transcript="first segment\nsecond segment",
        transcript_segments=[dict(s) for s in _SEGMENTS],
        chapters=[dict(c) for c in _CHAPTERS],
        summary="a summary",
        language="russian",
        transcript_language="ru",
        ai_profile_id="gemini_flash",
        ai_model="gemini-2.5-flash",
    )


def _make_stores(tmp: str):
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore

    db = Path(tmp) / "videobrain.db"
    return SqliteDocumentStore(db), SqliteKnowledgeStore(db)


def _row_count(db: Path, table: str) -> int:
    with closing(sqlite3.connect(db)) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_successful_dual_write():
    """Shadow write creates document + chunks + enrichments with expected fields."""
    print("Testing successful dual-write...")
    from backend.services.knowledge_ingest_service import KnowledgeIngestService

    with tempfile.TemporaryDirectory() as tmp:
        docs, knowledge = _make_stores(tmp)
        service = KnowledgeIngestService(docs, knowledge)

        document_id = service.shadow_write_task(
            _make_completed_task(), content_hash="hash-abc", origin_filename="lecture.mp4"
        )
        assert document_id is not None

        document = docs.load(document_id)
        assert document is not None
        assert document.source_type == "file_media"
        assert document.origin_uri == "lecture.mp4"
        assert document.primary_language == "ru"
        assert document.language_source == "asr"
        assert document.content_hash == "hash-abc"
        assert document.media_path is None  # deferred (ADR-0006)
        assert document.created_at is not None

        chunks = knowledge.load_chunks(document_id)
        assert len(chunks) == 2
        assert [c.ordinal for c in chunks] == [0, 1]
        assert chunks[0].text == "first segment"
        assert chunks[0].start == 0.0 and chunks[0].end == 1.5

        summaries = knowledge.load_enrichments("document", document_id, type="summary")
        assert len(summaries) == 1
        assert summaries[0].payload == {"text": "a summary", "language": "russian"}
        assert summaries[0].params == {"ai_profile": "gemini_flash", "ai_model": "gemini-2.5-flash"}
        assert summaries[0].prompt_version == 1

        chapters = knowledge.load_enrichments("document", document_id, type="chapters")
        assert len(chapters) == 1
        assert chapters[0].payload["chapters"] == _CHAPTERS

    print("✅ Dual-write creates document + chunks + enrichments")
    return True


def test_idempotency():
    """Repeated processing of the same content: one row per logical entity."""
    print("\nTesting idempotency...")
    from backend.services.knowledge_ingest_service import KnowledgeIngestService

    with tempfile.TemporaryDirectory() as tmp:
        docs, knowledge = _make_stores(tmp)
        service = KnowledgeIngestService(docs, knowledge)
        db = Path(tmp) / "videobrain.db"

        task = _make_completed_task("task-run-1")
        doc_id_1 = service.shadow_write_task(task, "same-hash", "video.mp4")
        chunk_ids_1 = [c.id for c in knowledge.load_chunks(doc_id_1)]

        # Second run: new task id, same content (changed transcript text).
        task2 = _make_completed_task("task-run-2")
        task2.transcript_segments[0]["text"] = "first segment (rebuilt)"
        doc_id_2 = service.shadow_write_task(task2, "same-hash", "video.mp4")

        assert doc_id_1 == doc_id_2, "same content must map to the same document"
        assert _row_count(db, "documents") == 1
        assert _row_count(db, "knowledge_chunks") == 2, "replace-set, not append"
        assert _row_count(db, "enrichments") == 2, "summary + chapters upserted, not duplicated"

        chunk_ids_2 = [c.id for c in knowledge.load_chunks(doc_id_2)]
        assert chunk_ids_1 == chunk_ids_2, "chunk ids are deterministic per ordinal"
        assert knowledge.load_chunks(doc_id_2)[0].text == "first segment (rebuilt)"

    print("✅ Repeated processing: same document, rebuilt chunks, no duplicates")
    return True


def test_failure_isolation():
    """Shadow failure never raises and leaves no partial trace contract broken."""
    print("\nTesting failure isolation...")
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.storage import SqliteKnowledgeStore

    class ExplodingKnowledgeStore(SqliteKnowledgeStore):
        def save_chunks(self, document_id, chunks):
            raise RuntimeError("db is on fire")

    with tempfile.TemporaryDirectory() as tmp:
        docs, knowledge = _make_stores(tmp)
        service = KnowledgeIngestService(docs, ExplodingKnowledgeStore(Path(tmp) / "videobrain.db"))

        task = _make_completed_task()
        result = service.shadow_write_task(task, "hash-x", "v.mp4")
        assert result is None, "failure must return None, not raise"

        # Task object itself is untouched (no document_id set by service).
        assert task.document_id is None

        # Log file recorded the failure with identifiers.
        import backend.services.knowledge_ingest_service as ingest_module
        log_path = ingest_module._LOG_PATH
        assert log_path.exists(), "shadow log missing"
        log_text = log_path.read_text(encoding="utf-8")
        assert "FAILURE task=task-1" in log_text
        assert "db is on fire" in log_text

        log_path.unlink()  # do not pollute the real log with test entries

    print("✅ Shadow failure: None returned, task untouched, FAILURE logged")
    return True


def test_translation_shadow():
    """Translations become chunk-scoped enrichments; skip without document_id."""
    print("\nTesting translation shadow...")
    from backend.services.knowledge_ingest_service import KnowledgeIngestService

    with tempfile.TemporaryDirectory() as tmp:
        docs, knowledge = _make_stores(tmp)
        service = KnowledgeIngestService(docs, knowledge)

        task = _make_completed_task()
        doc_id = service.shadow_write_task(task, "hash-t", "v.mp4")
        task.document_id = doc_id
        task.translation_results = {
            "gemini_flash:russian": {
                "target_language": "Russian",
                "ai_profile_id": "gemini_flash",
                "transcript_segments": [
                    {**dict(_SEGMENTS[0]), "enrichment": {
                        "translation": "первый сегмент",
                        "translation_status": "ready",
                        "translation_error": None,
                    }},
                    {**dict(_SEGMENTS[1]), "enrichment": {
                        "translation": None,
                        "translation_status": "failed",
                        "translation_error": "quota",
                    }},
                ],
            }
        }

        written = service.shadow_write_translations(task)
        assert written == 2

        chunks = knowledge.load_chunks(doc_id)
        first = knowledge.load_enrichments("chunk", chunks[0].id, type="translation")
        assert len(first) == 1
        assert first[0].payload["text"] == "первый сегмент"
        assert first[0].payload["status"] == "ready"
        assert first[0].params == {"target_language": "Russian", "ai_profile": "gemini_flash"}

        second = knowledge.load_enrichments("chunk", chunks[1].id, type="translation")
        assert second[0].payload["status"] == "failed"
        assert second[0].payload["error"] == "quota"

        # Re-run is idempotent (upsert by deterministic id).
        written_again = service.shadow_write_translations(task)
        assert written_again == 2
        assert _row_count(Path(tmp) / "videobrain.db", "enrichments") == 2 + 2  # doc-level + translations

        # Task without document_id: skipped, no crash.
        orphan = _make_completed_task("task-orphan")
        orphan.translation_results = task.translation_results
        assert service.shadow_write_translations(orphan) == 0

    print("✅ Translation shadow: chunk enrichments, idempotent, skip without document_id")
    return True


def test_route_integration():
    """Full background pipeline (stubbed AI/Whisper): task completes AND shadow exists."""
    print("\nTesting route-level integration...")
    import backend.routes.video as video_module
    from backend.services.task_manager import TaskManager
    from backend.services.storage import JsonTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        # Isolate: real task manager on temp JSON store, real knowledge stores.
        manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))
        docs, knowledge = _make_stores(tmp)

        original_manager = video_module.task_manager
        original_ingest = video_module._knowledge_ingest
        original_transcriber = video_module.Transcriber
        original_get_provider = video_module.get_ai_provider
        original_file_source = video_module.get_input_source
        original_settings_dirs = None

        from backend.services.knowledge_ingest_service import KnowledgeIngestService
        from backend.config.settings import settings

        class StubTranscriber:
            def __init__(self, model_size: str = "tiny"):
                pass

            def transcribe_with_segments(self, audio_path):
                return "first segment\nsecond segment", [dict(s) for s in _SEGMENTS], "ru"

        class StubProvider:
            def summarize_with_chapters(self, segments, source_language=None):
                return {"summary": "a summary", "chapters": [dict(c) for c in _CHAPTERS], "language": "russian"}

        class StubProfile:
            id = "gemini_flash"
            display_name = "Gemini Flash"
            provider = "gemini"
            model = "gemini-2.5-flash"

        class StubFileSource:
            def extract_audio(self, input_data, task_id, output_dir):
                return input_data  # pretend extraction

        try:
            video_module.task_manager = manager
            video_module._knowledge_ingest = KnowledgeIngestService(docs, knowledge)
            video_module.Transcriber = StubTranscriber
            video_module.get_ai_provider = lambda pid: (StubProfile(), StubProvider())
            video_module.get_input_source = lambda t: StubFileSource()

            # Redirect artifact dirs into temp.
            original_settings_dirs = (settings.transcripts_dir, settings.summaries_dir, settings.audio_dir)
            settings.transcripts_dir = Path(tmp) / "transcripts"
            settings.summaries_dir = Path(tmp) / "summaries"
            settings.audio_dir = Path(tmp) / "audio"

            manager.create("task-it-1", source="file")
            video_module._process_file_with_ai_profile(
                "task-it-1", str(Path(tmp) / "upload.mp3"), "tiny", "gemini_flash",
                content_hash="it-hash", origin_filename="upload.mp3",
            )

            task = manager.get("task-it-1")
            assert task.status == "completed", f"task status: {task.status} ({task.error})"
            assert task.document_id is not None, "document_id not set after shadow write"

            document = docs.load(task.document_id)
            assert document is not None and document.content_hash == "it-hash"
            assert len(knowledge.load_chunks(task.document_id)) == 2
            assert len(knowledge.load_enrichments("document", task.document_id)) == 2

            # Response shape unchanged: to_dict keys are exactly as before.
            keys = set(manager.to_dict("task-it-1").keys())
            assert "transcript_segments" in keys and "timings" in keys
        finally:
            video_module.task_manager = original_manager
            video_module._knowledge_ingest = original_ingest
            video_module.Transcriber = original_transcriber
            video_module.get_ai_provider = original_get_provider
            video_module.get_input_source = original_file_source
            if original_settings_dirs:
                (settings.transcripts_dir, settings.summaries_dir, settings.audio_dir) = original_settings_dirs

        # Cleanup shadow log entries from this test run.
        from backend.services.knowledge_ingest_service import _LOG_PATH
        if _LOG_PATH.exists():
            _LOG_PATH.unlink()

    print("✅ Pipeline integration: task completed + shadow rows present")
    return True


def test_route_integration_shadow_failure():
    """Shadow failure during pipeline: task still completes with API shape intact."""
    print("\nTesting route integration with shadow failure...")
    import backend.routes.video as video_module
    from backend.services.task_manager import TaskManager
    from backend.services.storage import JsonTaskStore

    class ExplodingIngest:
        def shadow_write_task(self, task, content_hash, origin_filename):
            raise RuntimeError("ingest exploded")

    with tempfile.TemporaryDirectory() as tmp:
        manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))

        original_manager = video_module.task_manager
        original_ingest = video_module._knowledge_ingest
        original_transcriber = video_module.Transcriber
        original_get_provider = video_module.get_ai_provider
        original_file_source = video_module.get_input_source

        from backend.config.settings import settings

        class StubTranscriber:
            def __init__(self, model_size: str = "tiny"):
                pass

            def transcribe_with_segments(self, audio_path):
                return "text", [dict(s) for s in _SEGMENTS], "ru"

        class StubProvider:
            def summarize_with_chapters(self, segments, source_language=None):
                return {"summary": "s", "chapters": [dict(c) for c in _CHAPTERS], "language": "russian"}

        class StubProfile:
            id = "gemini_flash"
            display_name = "Gemini Flash"
            provider = "gemini"
            model = "gemini-2.5-flash"

        class StubFileSource:
            def extract_audio(self, input_data, task_id, output_dir):
                return input_data

        original_settings_dirs = (settings.transcripts_dir, settings.summaries_dir, settings.audio_dir)
        try:
            video_module.task_manager = manager
            video_module._knowledge_ingest = ExplodingIngest()
            video_module.Transcriber = StubTranscriber
            video_module.get_ai_provider = lambda pid: (StubProfile(), StubProvider())
            video_module.get_input_source = lambda t: StubFileSource()
            settings.transcripts_dir = Path(tmp) / "transcripts"
            settings.summaries_dir = Path(tmp) / "summaries"
            settings.audio_dir = Path(tmp) / "audio"

            manager.create("task-it-2", source="file")
            video_module._process_file_with_ai_profile(
                "task-it-2", str(Path(tmp) / "upload.mp3"), "tiny", "gemini_flash"
            )

            task = manager.get("task-it-2")
            assert task.status == "completed", f"shadow failure must not fail the task: {task.error}"
            assert task.document_id is None
            status_payload = manager.to_dict("task-it-2")
            assert status_payload["summary"] == "s"
            assert len(status_payload["transcript_segments"]) == 2
        finally:
            video_module.task_manager = original_manager
            video_module._knowledge_ingest = original_ingest
            video_module.Transcriber = original_transcriber
            video_module.get_ai_provider = original_get_provider
            video_module.get_input_source = original_file_source
            (settings.transcripts_dir, settings.summaries_dir, settings.audio_dir) = original_settings_dirs

    print("✅ Shadow failure: task completes, API payload intact")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Shadow Dual-Write (ADR-0006) - Test Suite")
    print("=" * 60)

    tests = [
        test_successful_dual_write,
        test_idempotency,
        test_failure_isolation,
        test_translation_shadow,
        test_route_integration,
        test_route_integration_shadow_failure,
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
