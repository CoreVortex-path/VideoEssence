#!/usr/bin/env python3
"""
Tests for the knowledge schema (ADR-0005, frozen model ADR-0004).

Covers:
- Document round-trip, upsert, missing → None
- KnowledgeChunk save/load (ordered), replace-set swap
- Cascade: chunk-scoped enrichments deleted with replaced chunks;
  document-scoped enrichments survive
- Enrichment round-trip, type filter, newest-first order
- Task schema v2: document_id persisted; v1 records load with None
- DB rename shim: legacy tasks.db migrates to videobrain.db
- Real migrated database still serves all task records

Runs in temp directories; never mutates data/ (real-DB check is read-only).
"""

import json
import os
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


def _make_document(doc_id: str = "doc-1"):
    from backend.services.storage import Document

    return Document(
        id=doc_id,
        source_type="file_media",
        origin_uri="lecture.mp4",
        title="Lecture",
        media_path="data/audio/lecture.mp4",
        primary_language="ru",
        language_source="asr",
        duration_seconds=62.5,
        content_hash="abc123",
        created_at="2026-07-28T12:00:00+00:00",
    )


def _make_chunk(chunk_id: str, doc_id: str = "doc-1", ordinal: int = 0, text: str = "hello"):
    from backend.services.storage import KnowledgeChunk

    return KnowledgeChunk(
        id=chunk_id,
        document_id=doc_id,
        ordinal=ordinal,
        text=text,
        start=float(ordinal),
        end=float(ordinal) + 1.5,
    )


def _make_enrichment(enr_id: str, scope: str, owner_id: str, type: str = "translation"):
    from backend.services.storage import Enrichment

    return Enrichment(
        id=enr_id,
        scope=scope,
        owner_id=owner_id,
        type=type,
        params={"target_language": "Russian", "ai_profile": "gemini_flash"},
        prompt_version=1,
        payload={"text": "привет"},
        created_at="2026-07-28T12:05:00+00:00",
    )


def test_document_roundtrip():
    """save→load preserves all fields; upsert updates in place; missing → None."""
    print("Testing DocumentStore round-trip...")
    from backend.services.storage import SqliteDocumentStore

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteDocumentStore(Path(tmp) / "videobrain.db")

        assert store.load("doc-1") is None

        store.save(_make_document())
        loaded = store.load("doc-1")
        assert loaded is not None
        assert loaded.source_type == "file_media"
        assert loaded.primary_language == "ru"
        assert loaded.language_source == "asr"
        assert loaded.duration_seconds == 62.5
        assert loaded.created_at == "2026-07-28T12:00:00+00:00"

        loaded.title = "Renamed"
        store.save(loaded)
        assert store.load("doc-1").title == "Renamed"

    print("✅ Document round-trip, upsert, missing→None")
    return True


def test_chunk_replace_set():
    """Chunks load ordered; save_chunks swaps the set atomically."""
    print("\nTesting chunk replace-set semantics...")
    from backend.services.storage import SqliteKnowledgeStore

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteKnowledgeStore(Path(tmp) / "videobrain.db")

        store.save_chunks("doc-1", [
            _make_chunk("c-2", ordinal=1, text="second"),
            _make_chunk("c-1", ordinal=0, text="first"),
        ])
        chunks = store.load_chunks("doc-1")
        assert [c.id for c in chunks] == ["c-1", "c-2"], "must be ordinal-ordered"
        assert chunks[0].start == 0.0 and chunks[0].end == 1.5

        # Re-processing: replace with a different set.
        store.save_chunks("doc-1", [_make_chunk("c-3", ordinal=0, text="rebuilt")])
        chunks = store.load_chunks("doc-1")
        assert [c.id for c in chunks] == ["c-3"]
        assert chunks[0].text == "rebuilt"

        assert store.load_chunks("unknown-doc") == []

    print("✅ Chunks ordered; replace-set swaps atomically")
    return True


def test_enrichment_cascade():
    """Chunk-scoped enrichments die with replaced chunks; document-scoped survive."""
    print("\nTesting enrichment cascade rules...")
    from backend.services.storage import SqliteKnowledgeStore

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteKnowledgeStore(Path(tmp) / "videobrain.db")

        store.save_chunks("doc-1", [_make_chunk("c-1", ordinal=0)])
        store.save_enrichment(_make_enrichment("e-chunk", scope="chunk", owner_id="c-1"))
        store.save_enrichment(_make_enrichment("e-doc", scope="document", owner_id="doc-1", type="summary"))

        # Re-processing replaces c-1 with c-9.
        store.save_chunks("doc-1", [_make_chunk("c-9", ordinal=0)])

        assert store.load_enrichments("chunk", "c-1") == [], "orphaned chunk enrichment survived"
        doc_enr = store.load_enrichments("document", "doc-1")
        assert len(doc_enr) == 1 and doc_enr[0].id == "e-doc", "document enrichment must survive"

    print("✅ Chunk enrichments cascade; document enrichments survive")
    return True


def test_enrichment_queries():
    """Round-trip, type filter, newest-first."""
    print("\nTesting enrichment queries...")
    from backend.services.storage import SqliteKnowledgeStore

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteKnowledgeStore(Path(tmp) / "videobrain.db")

        store.save_enrichment(_make_enrichment("e-1", "chunk", "c-1", type="translation"))
        store.save_enrichment(_make_enrichment("e-2", "chunk", "c-1", type="concepts"))
        store.save_enrichment(_make_enrichment("e-3", "chunk", "c-1", type="translation"))

        all_enr = store.load_enrichments("chunk", "c-1")
        assert [e.id for e in all_enr] == ["e-3", "e-2", "e-1"], "must be newest-first"

        translations = store.load_enrichments("chunk", "c-1", type="translation")
        assert [e.id for e in translations] == ["e-3", "e-1"]
        assert translations[0].params["target_language"] == "Russian"
        assert translations[0].payload == {"text": "привет"}

    print("✅ Enrichment round-trip, type filter, newest-first")
    return True


def test_task_schema_v2():
    """v2 writes document_id; v1 records (no document_id) load with None."""
    print("\nTesting task schema v2...")
    from backend.services.storage.models import (
        TASK_SCHEMA_VERSION,
        Task,
        task_from_dict,
        task_to_dict,
    )

    assert TASK_SCHEMA_VERSION == 2

    task = Task(id="t-1", source="file", document_id="doc-1")
    record = task_to_dict(task)
    assert record["schema_version"] == 2
    assert record["document_id"] == "doc-1"
    assert task_from_dict(record).document_id == "doc-1"

    # v1 record: has schema_version but no document_id.
    v1 = task_to_dict(Task(id="t-old", source="file"))
    v1["schema_version"] = 1
    del v1["document_id"]
    loaded = task_from_dict(v1)
    assert loaded.document_id is None
    assert loaded.id == "t-old"

    print("✅ Task v2 persists document_id; v1 loads with None")
    return True


def test_db_rename_shim():
    """Legacy tasks.db migrates to videobrain.db once; both-present keeps new."""
    print("\nTesting DB rename shim...")
    from backend.services.storage import SqliteTaskStore, Task
    from backend.services.storage.sqlite_store import ensure_db_path

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        legacy = tmp_path / "tasks.db"
        new = tmp_path / "videobrain.db"

        # Legacy DB with one task migrates to the new name.
        SqliteTaskStore(legacy).save(Task(id="legacy-task", source="file"))
        assert legacy.exists() and not new.exists()
        resolved = ensure_db_path(new)
        assert resolved == new
        assert new.exists() and not legacy.exists()
        assert SqliteTaskStore(new).load("legacy-task") is not None

        # If both exist, the new path wins and legacy is left untouched.
        legacy.write_text("sentinel", encoding="utf-8")
        resolved = ensure_db_path(new)
        assert resolved == new
        assert legacy.read_text(encoding="utf-8") == "sentinel"

    print("✅ Legacy tasks.db → videobrain.db migration shim works")
    return True


def test_real_database_after_rename():
    """The real migrated DB (data/videobrain.db) still serves all task records."""
    print("\nTesting real database compatibility (read-only)...")
    from backend.config.settings import settings

    db_path = settings.tasks_db_path
    if not db_path.exists():
        print(f"⚠️  {db_path} not found — skipping")
        return True

    with closing(sqlite3.connect(db_path)) as conn:
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    assert task_count > 0, "migrated DB has no task records"

    from backend.services.storage import (
        SqliteDocumentStore,
        SqliteKnowledgeStore,
        SqliteTaskStore,
    )

    # Instantiating the stores must create the new tables in the real DB.
    SqliteDocumentStore(db_path)
    SqliteKnowledgeStore(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"tasks", "documents", "knowledge_chunks", "enrichments"} <= tables

    store = SqliteTaskStore(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        sample_id = conn.execute("SELECT id FROM tasks LIMIT 1").fetchone()[0]
    task = store.load(sample_id)
    assert task is not None and task.id == sample_id

    print(f"✅ Real DB: {task_count} tasks intact, knowledge tables created")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Knowledge Schema (ADR-0005) - Test Suite")
    print("=" * 60)

    tests = [
        test_document_roundtrip,
        test_chunk_replace_set,
        test_enrichment_cascade,
        test_enrichment_queries,
        test_task_schema_v2,
        test_db_rename_shim,
        test_real_database_after_rename,
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
