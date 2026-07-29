#!/usr/bin/env python3
"""
Tests for the Step 2c backfill orchestration (ADR-0007).

Covers:
- Eligibility rules (completed+segments imported; others skipped with reason)
- Idempotent re-runs (second run: everything already_linked, no new rows)
- Repair semantics (induced failure → retried and repaired on next run)
- Dry-run (correct report, zero writes, DB byte-identical)
- Per-task isolation (one bad record cannot abort the run)
- Translation backfill via the shared ingest service
- list_ids() on both task-store backends

Runs in temp directories with real stores and the real ingest service.
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


def _make_task(task_id: str, status: str = "completed", with_segments: bool = True):
    from backend.services.storage import Task

    return Task(
        id=task_id,
        source="file",
        status=status,
        transcript="first segment\nsecond segment" if with_segments else None,
        transcript_segments=[dict(s) for s in _SEGMENTS] if with_segments else [],
        chapters=[{"title": "Intro", "summary": "opening", "start": 0.0}] if with_segments else [],
        summary="a summary" if with_segments else None,
        language="russian",
        transcript_language="ru",
        ai_profile_id="gemini_flash",
        ai_model="gemini-2.5-flash",
    )


def _make_world(tmp: str):
    """Real stores + real ingest service over temp paths."""
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.storage import (
        JsonTaskStore,
        SqliteDocumentStore,
        SqliteKnowledgeStore,
    )

    db = Path(tmp) / "videobrain.db"
    task_store = JsonTaskStore(Path(tmp) / "tasks")
    docs = SqliteDocumentStore(db)
    knowledge = SqliteKnowledgeStore(db)
    ingest = KnowledgeIngestService(docs, knowledge)
    return task_store, docs, knowledge, ingest, db


def _row_count(db: Path, table: str) -> int:
    with closing(sqlite3.connect(db)) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_list_ids_backends():
    """list_ids() works on JSON and SQLite task stores."""
    print("Testing list_ids() on both backends...")
    from backend.services.storage import JsonTaskStore, SqliteTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        json_store = JsonTaskStore(Path(tmp) / "json")
        sqlite_store = SqliteTaskStore(Path(tmp) / "tasks.db")
        for store in (json_store, sqlite_store):
            assert store.list_ids() == []
            store.save(_make_task("b-task"))
            store.save(_make_task("a-task"))
            assert store.list_ids() == ["a-task", "b-task"]

    print("✅ list_ids(): JSON + SQLite, sorted, empty-safe")
    return True


def test_eligibility():
    """Only completed tasks with segments and no document_id are imported."""
    print("\nTesting eligibility rules...")
    from backend.services.storage.backfill import backfill_tasks

    with tempfile.TemporaryDirectory() as tmp:
        task_store, docs, knowledge, ingest, db = _make_world(tmp)

        task_store.save(_make_task("ok-1"))
        task_store.save(_make_task("failed-task", status="failed", with_segments=False))
        task_store.save(_make_task("no-segments", with_segments=False))
        linked = _make_task("already-linked")
        linked.document_id = "some-doc"
        task_store.save(linked)

        report = backfill_tasks(task_store, ingest)

        assert report.scanned == 4
        assert report.imported == 1
        assert report.skipped_failed_status == 1
        assert report.skipped_no_segments == 1
        assert report.already_linked == 1
        assert report.failed == 0

        # The imported task is fully shadow-written and linked.
        task = task_store.load("ok-1")
        assert task.document_id is not None
        assert docs.load(task.document_id) is not None
        assert len(knowledge.load_chunks(task.document_id)) == 2
        assert len(knowledge.load_enrichments("document", task.document_id)) == 2

    print("✅ Eligibility: import/skip rules and counters correct")
    return True


def test_idempotent_rerun():
    """Second run: everything already_linked, row counts unchanged."""
    print("\nTesting idempotent re-run...")
    from backend.services.storage.backfill import backfill_tasks

    with tempfile.TemporaryDirectory() as tmp:
        task_store, docs, knowledge, ingest, db = _make_world(tmp)
        task_store.save(_make_task("ok-1"))
        task_store.save(_make_task("ok-2"))

        first = backfill_tasks(task_store, ingest)
        assert first.imported == 2
        counts_after_first = {t: _row_count(db, t) for t in ("documents", "knowledge_chunks", "enrichments")}

        second = backfill_tasks(task_store, ingest)
        assert second.imported == 0
        assert second.already_linked == 2
        counts_after_second = {t: _row_count(db, t) for t in ("documents", "knowledge_chunks", "enrichments")}

        assert counts_after_first == counts_after_second

    print("✅ Re-run: no duplicates, all already_linked")
    return True


def test_repair_semantics():
    """A task whose shadow failed is retried and counted as repaired."""
    print("\nTesting repair semantics...")
    from backend.services.knowledge_ingest_service import KnowledgeIngestService, _LOG_PATH
    from backend.services.storage import SqliteKnowledgeStore
    from backend.services.storage.backfill import backfill_tasks

    class ExplodingKnowledgeStore(SqliteKnowledgeStore):
        def save_chunks(self, document_id, chunks):
            raise RuntimeError("boom")

    with tempfile.TemporaryDirectory() as tmp:
        task_store, docs, knowledge, _ingest, db = _make_world(tmp)
        task_store.save(_make_task("flaky-task"))

        # Run 1: shadow fails → task in 'failed', document_id stays NULL.
        bad_ingest = KnowledgeIngestService(docs, ExplodingKnowledgeStore(db))
        first = backfill_tasks(task_store, bad_ingest)
        assert first.failed == 1 and first.imported == 0
        assert task_store.load("flaky-task").document_id is None

        # Run 2: healthy store → retried, imported, counted as repaired.
        good_ingest = KnowledgeIngestService(docs, knowledge)
        second = backfill_tasks(task_store, good_ingest)
        assert second.imported == 1
        assert second.repaired == 1, f"expected repaired=1, got {second.repaired}"
        assert task_store.load("flaky-task").document_id is not None

        if _LOG_PATH.exists():
            _LOG_PATH.unlink()  # do not leave test entries in the real log

    print("✅ Repair: failed shadow retried automatically, counted as repaired")
    return True


def test_dry_run():
    """Dry-run reports decisions but writes nothing anywhere."""
    print("\nTesting dry-run mode...")
    from backend.services.storage.backfill import backfill_tasks

    with tempfile.TemporaryDirectory() as tmp:
        task_store, docs, knowledge, ingest, db = _make_world(tmp)
        task_store.save(_make_task("ok-1"))
        task_store.save(_make_task("failed-task", status="failed", with_segments=False))

        db_bytes_before = db.read_bytes()
        report = backfill_tasks(task_store, ingest, dry_run=True)

        assert report.dry_run is True
        assert report.scanned == 2
        assert report.imported == 1  # would-be import
        assert report.skipped_failed_status == 1
        assert db.read_bytes() == db_bytes_before, "dry-run must not touch the DB"
        assert task_store.load("ok-1").document_id is None, "dry-run must not link tasks"

    print("✅ Dry-run: correct report, zero writes")
    return True


def test_per_task_isolation():
    """One corrupt record lands in failed; the rest import normally."""
    print("\nTesting per-task isolation...")
    from backend.services.storage.backfill import backfill_tasks

    with tempfile.TemporaryDirectory() as tmp:
        task_store, docs, knowledge, ingest, db = _make_world(tmp)
        task_store.save(_make_task("good-1"))
        task_store.save(_make_task("good-2"))

        # Corrupt one record on disk (invalid JSON payload).
        bad_file = Path(tmp) / "tasks" / "corrupt.json"
        bad_file.write_text("{not json", encoding="utf-8")

        report = backfill_tasks(task_store, ingest)
        assert report.scanned == 3
        assert report.imported == 2
        assert report.failed == 1

    print("✅ Isolation: corrupt record failed, others imported")
    return True


def test_translation_backfill():
    """Tasks with translation_results get chunk-scoped translation enrichments."""
    print("\nTesting translation backfill...")
    from backend.services.storage.backfill import backfill_tasks

    with tempfile.TemporaryDirectory() as tmp:
        task_store, docs, knowledge, ingest, db = _make_world(tmp)

        task = _make_task("translated-task")
        task.translation_results = {
            "gemini_flash:russian": {
                "target_language": "Russian",
                "ai_profile_id": "gemini_flash",
                "transcript_segments": [
                    {**dict(_SEGMENTS[0]), "enrichment": {
                        "translation": "первый", "translation_status": "ready",
                        "translation_error": None,
                    }},
                    {**dict(_SEGMENTS[1]), "enrichment": {
                        "translation": "второй", "translation_status": "ready",
                        "translation_error": None,
                    }},
                ],
            }
        }
        task_store.save(task)

        report = backfill_tasks(task_store, ingest)
        assert report.imported == 1

        doc_id = task_store.load("translated-task").document_id
        chunks = knowledge.load_chunks(doc_id)
        translations = knowledge.load_enrichments("chunk", chunks[0].id, type="translation")
        assert len(translations) == 1
        assert translations[0].payload["text"] == "первый"
        # 2 document-level (summary, chapters) + 2 translations
        assert _row_count(db, "enrichments") == 4

    print("✅ Translation backfill: chunk enrichments via shared service")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Backfill (ADR-0007) - Test Suite")
    print("=" * 60)

    tests = [
        test_list_ids_backends,
        test_eligibility,
        test_idempotent_rerun,
        test_repair_semantics,
        test_dry_run,
        test_per_task_isolation,
        test_translation_backfill,
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
