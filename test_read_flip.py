#!/usr/bin/env python3
"""
Tests for the Step 3 read-flip (ADR-0008).

Covers:
- Equivalence: knowledge-assembled payload matches the legacy payload
- Actually-flipped proof: knowledge edits surface through the endpoint
- Fallback cases: no document_id, missing document, missing enrichments,
  assembly error → legacy payload served
- Kill switch: knowledge_read_enabled=False → legacy path always
- Endpoint level: TestClient 200/400/404 behavior unchanged

Runs in temp directories with real stores and the real ingest service.
"""

import sys
import tempfile
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

FLIPPED_FIELDS = (
    "transcript", "transcript_segments", "summary", "chapters",
    "language", "transcript_language",
)


def _make_task(task_id: str = "task-1"):
    from backend.services.storage import Task

    return Task(
        id=task_id,
        source="file",
        status="completed",
        progress="Task completed",
        transcript="first segment\nsecond segment",
        transcript_segments=[dict(s) for s in _SEGMENTS],
        chapters=[dict(c) for c in _CHAPTERS],
        summary="a summary",
        language="russian",
        transcript_language="ru",
        ai_profile_id="gemini_flash",
        ai_profile_name="Gemini Flash",
        ai_provider="gemini",
        ai_model="gemini-2.5-flash",
        timings={"ai_seconds": 1.0},
    )


def _seed(tmp: str, task=None):
    """Real stores + knowledge seeded via the real ingest service."""
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore

    db = Path(tmp) / "videobrain.db"
    docs = SqliteDocumentStore(db)
    knowledge = SqliteKnowledgeStore(db)
    task = task or _make_task()
    document_id = KnowledgeIngestService(docs, knowledge).shadow_write_task(
        task, "hash-1", "video.mp4"
    )
    assert document_id is not None
    task.document_id = document_id
    reader = KnowledgeReadService(docs, knowledge)
    return task, docs, knowledge, reader


def test_equivalence():
    """Assembled payload matches the legacy payload on all flipped fields."""
    print("Testing assembled/legacy equivalence...")
    from backend.services.task_manager import TaskManager
    from backend.services.storage import JsonTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        task, docs, knowledge, reader = _seed(tmp)
        assembled = reader.assemble_status(task)
        assert assembled is not None

        manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))
        manager._tasks[task.id] = task
        legacy = manager.to_dict(task.id)

        for field in FLIPPED_FIELDS:
            assert assembled[field] == legacy[field], f"{field}: {assembled[field]!r} != {legacy[field]!r}"

        # Job-state fields come from the task verbatim.
        assert assembled["status"] == "completed"
        assert assembled["timings"] == {"ai_seconds": 1.0}
        assert assembled["ai_profile_name"] == "Gemini Flash"

    print("✅ Assembled payload identical to legacy on all fields")
    return True


def test_actually_flipped():
    """Edits in the knowledge layer surface in the assembled payload."""
    print("\nTesting the read path is truly flipped...")
    from backend.services.storage import KnowledgeChunk

    with tempfile.TemporaryDirectory() as tmp:
        task, docs, knowledge, reader = _seed(tmp)

        # Rewrite the chunk set with different text (simulates knowledge-layer edit).
        chunks = knowledge.load_chunks(task.document_id)
        edited = [
            KnowledgeChunk(
                id=c.id, document_id=c.document_id, ordinal=c.ordinal,
                text="EDITED " + c.text, start=c.start, end=c.end,
            )
            for c in chunks
        ]
        knowledge.save_chunks(task.document_id, edited)

        assembled = reader.assemble_status(task)
        assert assembled["transcript"].startswith("EDITED first segment")
        assert task.transcript.startswith("first segment"), "task record untouched"

    print("✅ Knowledge-layer edits surface; task record untouched")
    return True


def test_fallbacks():
    """Every incomplete-shadow case returns None (caller serves legacy)."""
    print("\nTesting fallback cases...")
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore

    with tempfile.TemporaryDirectory() as tmp:
        task, docs, knowledge, reader = _seed(tmp)

        # No document_id.
        orphan = _make_task("orphan")
        assert reader.assemble_status(orphan) is None

        # Missing document (document_id points nowhere).
        ghost = _make_task("ghost")
        ghost.document_id = "no-such-doc"
        assert reader.assemble_status(ghost) is None

        # Missing summary enrichment: fresh document with chunks but no enrichments.
        db = Path(tmp) / "videobrain.db"
        bare_task = _make_task("bare")
        bare_task.summary = None
        bare_task.chapters = None
        from backend.services.knowledge_ingest_service import KnowledgeIngestService
        bare_doc_id = KnowledgeIngestService(docs, knowledge).shadow_write_task(
            bare_task, "hash-bare", "bare.mp4"
        )
        bare_task.document_id = bare_doc_id
        assert reader.assemble_status(bare_task) is None

        # Assembly error (store raising) → None, never an exception.
        class ExplodingDocs(SqliteDocumentStore):
            def load(self, document_id):
                raise RuntimeError("db down")

        exploding_reader = KnowledgeReadService(ExplodingDocs(db), knowledge)
        assert exploding_reader.assemble_status(task) is None

    print("✅ All fallback cases return None without raising")
    return True


def test_endpoint_flip_and_killswitch():
    """Endpoint serves knowledge path when enabled, legacy when switched off."""
    print("\nTesting endpoint flip + kill switch...")
    import backend.routes.video as video_module
    from backend.config.settings import settings
    from backend.services.task_manager import TaskManager
    from backend.services.storage import JsonTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        # Endpoint validates UUID task ids — use one here.
        task, docs, knowledge, reader = _seed(tmp, task=_make_task("11111111-2222-3333-4444-555555555555"))

        manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))
        manager._tasks[task.id] = task

        original_manager = video_module.task_manager
        original_reader = video_module._knowledge_reader
        original_flag = settings.knowledge_read_enabled
        try:
            video_module.task_manager = manager
            video_module._knowledge_reader = reader

            from fastapi.testclient import TestClient
            from backend.app import app
            client = TestClient(app)

            # Flip ON: serves knowledge data (200, correct content).
            settings.knowledge_read_enabled = True
            r = client.get(f"/videos/status/{task.id}")
            assert r.status_code == 200
            body = r.json()
            assert body["summary"] == "a summary"
            assert body["transcript"] == "first segment\nsecond segment"
            assert body["transcript_language"] == "ru"
            assert len(body["transcript_segments"]) == 2

            # Kill switch OFF: legacy path — same body (contract preserved).
            settings.knowledge_read_enabled = False
            r = client.get(f"/videos/status/{task.id}")
            assert r.status_code == 200
            assert r.json()["summary"] == "a summary"

            # Errors unchanged.
            assert client.get("/videos/status/nope").status_code == 400
            assert client.get(
                "/videos/status/00000000-0000-0000-0000-000000000000"
            ).status_code == 404
        finally:
            video_module.task_manager = original_manager
            video_module._knowledge_reader = original_reader
            settings.knowledge_read_enabled = original_flag

    print("✅ Endpoint: flip on/off, contract preserved, errors unchanged")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Read-Flip (ADR-0008) - Test Suite")
    print("=" * 60)

    tests = [
        test_equivalence,
        test_actually_flipped,
        test_fallbacks,
        test_endpoint_flip_and_killswitch,
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
