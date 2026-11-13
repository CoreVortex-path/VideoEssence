#!/usr/bin/env python3
"""
Tests for document delete + patch (pin/rename) (Library panel).

Covers:
- documents table lazy migration: ADD COLUMN pinned (PRAGMA-checked)
- DocumentStore: pinned round-trip, update(pinned/title), delete
- Cascade stores: knowledge chunks/enrichments, notes/highlights/chat
- TaskStore.delete (JSON + SQLite backends)
- Routes: PATCH /videos/documents/{id} (pin round-trip, rename round-trip,
  combined update, 400 on empty/blank/absent fields, 404), list sorting and
  title exposure, DELETE /videos/documents/{id} (record + related data +
  files, 404)

No AI involved. Runs in temp directories; never mutates data/.
"""

import json
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _doc_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"test-delete-pin:{name}"))


def _make_document(doc_id: str):
    from backend.services.storage import Document

    return Document(id=doc_id, source_type="file_media", title=f"Doc {doc_id[:8]}")


def test_pinned_column_migration():
    print("Testing documents table migration (ADD COLUMN pinned)...")
    from backend.services.storage import SqliteDocumentStore

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "videobrain.db"
        # Simulate a pre-migration database (no pinned column).
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "CREATE TABLE documents ("
                "id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, payload TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT INTO documents VALUES (?, ?, ?)",
                (
                    "old-1", 1,
                    json.dumps({"schema_version": 1, "id": "old-1",
                                "source_type": "file_media", "title": "legacy"}),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        # Opening the store must add the column and keep the data.
        store = SqliteDocumentStore(db)
        legacy = store.load("old-1")
        assert legacy is not None and legacy.title == "legacy"
        assert legacy.pinned is False
        store.update("old-1", pinned=True)
        assert store.load("old-1").pinned is True
    print("✅ Documents pinned migration works")
    return True


def test_update_roundtrip():
    print("Testing DocumentStore update (pinned/title) round-trip...")
    from backend.services.storage import SqliteDocumentStore

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteDocumentStore(Path(tmp) / "videobrain.db")
        doc = _make_document("doc-1")
        assert doc.pinned is False
        store.save(doc)
        assert store.load("doc-1").pinned is False

        assert store.update("doc-1", pinned=True) is True
        assert store.load("doc-1").pinned is True
        assert store.update("doc-1", pinned=False) is True
        assert store.load("doc-1").pinned is False

        # Title update keeps pinned; pinned update keeps title.
        assert store.update("doc-1", title="Renamed") is True
        loaded = store.load("doc-1")
        assert loaded.title == "Renamed" and loaded.pinned is False
        store.update("doc-1", pinned=True, title="Both")
        loaded = store.load("doc-1")
        assert loaded.title == "Both" and loaded.pinned is True

        # No-op update (both fields None) is a valid touch.
        assert store.update("doc-1") is True
        assert store.load("doc-1").title == "Both"

        # Pin/title survive a plain re-save of a loaded document.
        loaded = store.load("doc-1")
        loaded.title = "Re-save"
        store.save(loaded)
        assert store.load("doc-1").pinned is True

        assert store.update("missing", pinned=True) is False
    print("✅ Update round-trip works")
    return True


def test_store_delete_cascade():
    print("Testing store-level delete cascade...")
    from backend.services.storage import (
        ChatConversation,
        ChatMessage,
        Enrichment,
        Highlight,
        KnowledgeChunk,
        Note,
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "videobrain.db"
        documents = SqliteDocumentStore(db)
        knowledge = SqliteKnowledgeStore(db)
        interactions = SqliteInteractionStore(db)

        documents.save(_make_document("doc-1"))
        documents.save(_make_document("doc-2"))
        knowledge.save_chunks("doc-1", [
            KnowledgeChunk(id="c-1", document_id="doc-1", ordinal=0, text="hello", start=0.0, end=1.0),
        ])
        knowledge.save_enrichment(Enrichment(
            id="e-chunk", scope="chunk", owner_id="c-1", type="translation",
            params={}, prompt_version=1, payload={"text": "x"},
        ))
        knowledge.save_enrichment(Enrichment(
            id="e-doc", scope="document", owner_id="doc-1", type="summary",
            params={}, prompt_version=1, payload={"text": "x"},
        ))
        interactions.save_note(Note(id="n-1", document_id="doc-1", text="note"))
        interactions.save_note(Note(id="n-global", document_id=None, text="global"))
        interactions.save_highlight(Highlight(
            id="h-1", document_id="doc-1", chunk_id="c-1",
            start_offset=0, end_offset=2, text="he", color="yellow",
        ))
        interactions.save_conversation(ChatConversation(id="conv-1", document_id="doc-1"))
        interactions.save_message(ChatMessage(
            id="m-1", conversation_id="conv-1", role="user", content="hi",
        ))

        # Delete everything of doc-1.
        knowledge.delete_document("doc-1")
        interactions.delete_document_data("doc-1")
        assert documents.delete("doc-1") is True
        assert documents.delete("doc-1") is False  # already gone

        assert documents.load("doc-1") is None
        assert documents.load("doc-2") is not None
        assert knowledge.load_chunks("doc-1") == []
        assert knowledge.load_enrichments("chunk", "c-1") == []
        assert knowledge.load_enrichments("document", "doc-1") == []
        assert interactions.list_notes("doc-1") == []
        assert interactions.load_note("n-global") is not None
        assert interactions.list_highlights("doc-1") == []
        assert interactions.list_conversations("doc-1") == []
        assert interactions.list_messages("conv-1") == []
    print("✅ Store-level delete cascade works")
    return True


def test_task_store_delete():
    print("Testing TaskStore.delete (JSON + SQLite)...")
    from backend.services.storage import JsonTaskStore, SqliteTaskStore, Task
    from backend.services.task_manager import TaskManager

    with tempfile.TemporaryDirectory() as tmp:
        json_store = JsonTaskStore(Path(tmp) / "tasks-json")
        json_store.save(Task(id="t-1", source="file"))
        assert json_store.delete("t-1") is True
        assert json_store.load("t-1") is None
        assert json_store.delete("t-1") is False

        sqlite_store = SqliteTaskStore(Path(tmp) / "tasks.db")
        sqlite_store.save(Task(id="t-2", source="file"))
        assert sqlite_store.delete("t-2") is True
        assert sqlite_store.load("t-2") is None

        # TaskManager.delete drops both the in-memory entry and the record.
        manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks-mgr"))
        manager.create("t-3", "file")
        assert manager.get("t-3") is not None
        assert manager.delete("t-3") is True
        assert manager.get("t-3") is None
        assert "t-3" not in manager._store.list_ids()
    print("✅ TaskStore.delete works")
    return True


def _patched_route_env(tmp: str):
    """Route module with temp-backed stores; returns (module, manager, db)."""
    import backend.routes.video as route_module
    from backend.config.settings import settings
    from backend.services.storage import JsonTaskStore
    from backend.services.task_manager import TaskManager

    db = Path(tmp) / "videobrain.db"
    manager = TaskManager(store=JsonTaskStore(Path(tmp) / "tasks"))
    originals = (
        route_module.task_manager,
        settings.tasks_db_path,
        settings.audio_dir,
        settings.transcripts_dir,
        settings.summaries_dir,
    )
    route_module.task_manager = manager
    settings.tasks_db_path = db
    settings.audio_dir = Path(tmp) / "audio"
    settings.transcripts_dir = Path(tmp) / "transcripts"
    settings.summaries_dir = Path(tmp) / "summaries"
    return route_module, manager, originals


def _restore_route_env(route_module, originals):
    from backend.config.settings import settings

    (route_module.task_manager, settings.tasks_db_path, settings.audio_dir,
     settings.transcripts_dir, settings.summaries_dir) = originals


def test_patch_route_roundtrip_and_sorting():
    print("Testing PATCH route round-trip (pin + rename) + list sorting...")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmp:
        route_module, manager, originals = _patched_route_env(tmp)
        try:
            app = FastAPI()
            app.include_router(route_module.router, prefix="/videos")
            client = TestClient(app)

            doc_a, doc_b = _doc_id("a"), _doc_id("b")
            manager.create("task-a", "file")
            manager.update("task-a", document_id=doc_a, status="completed",
                           title="Original A")
            manager.create("task-b", "file")
            manager.update("task-b", document_id=doc_b, status="completed",
                           title="Original B")

            # Newest first: B before A; titles come from the tasks.
            listed = client.get("/videos/documents")
            assert listed.status_code == 200
            assert [i["document_id"] for i in listed.json()] == [doc_b, doc_a]
            assert all(i["pinned"] is False for i in listed.json())
            assert listed.json()[1]["title"] == "Original A"

            # Pin A (no Document record yet -> materialized from the task).
            pinned = client.patch(f"/videos/documents/{doc_a}", json={"pinned": True})
            assert pinned.status_code == 200, pinned.text
            assert pinned.json() == {
                "document_id": doc_a, "title": "Original A", "pinned": True,
            }

            listed = client.get("/videos/documents")
            items = listed.json()
            assert [i["document_id"] for i in items] == [doc_a, doc_b]
            assert items[0]["pinned"] is True and items[1]["pinned"] is False

            # Snapshot exposes the flag too.
            snapshot = client.get(f"/videos/documents/{doc_a}")
            assert snapshot.status_code == 200
            assert snapshot.json()["pinned"] is True

            # Unpin restores the original order.
            unpinned = client.patch(f"/videos/documents/{doc_a}", json={"pinned": False})
            assert unpinned.status_code == 200
            listed = client.get("/videos/documents")
            assert [i["document_id"] for i in listed.json()] == [doc_b, doc_a]

            # Rename round-trip: PATCH title -> snapshot list sees it.
            renamed = client.patch(
                f"/videos/documents/{doc_b}", json={"title": "  Renamed B  "}
            )
            assert renamed.status_code == 200, renamed.text
            assert renamed.json() == {
                "document_id": doc_b, "title": "Renamed B", "pinned": False,
            }
            listed = client.get("/videos/documents")
            assert listed.json()[0]["document_id"] == doc_b
            assert listed.json()[0]["title"] == "Renamed B"

            # Rename keeps the pinned flag; combined update sets both.
            client.patch(f"/videos/documents/{doc_b}", json={"pinned": True})
            combined = client.patch(
                f"/videos/documents/{doc_b}",
                json={"pinned": False, "title": "Final B"},
            )
            assert combined.status_code == 200
            assert combined.json() == {
                "document_id": doc_b, "title": "Final B", "pinned": False,
            }
            listed = client.get("/videos/documents")
            assert listed.json()[0]["title"] == "Final B"

            # Validation: no fields -> 400; empty/blank title -> 400.
            assert client.patch(
                f"/videos/documents/{doc_a}", json={}
            ).status_code == 400
            assert client.patch(
                f"/videos/documents/{doc_a}", json={"title": ""}
            ).status_code == 400
            assert client.patch(
                f"/videos/documents/{doc_a}", json={"title": "   "}
            ).status_code == 400

            # Unknown document -> 404; malformed id -> 400.
            assert client.patch(
                f"/videos/documents/{_doc_id('unknown')}", json={"pinned": True}
            ).status_code == 404
            assert client.patch(
                "/videos/documents/not-a-uuid", json={"pinned": True}
            ).status_code == 400
        finally:
            _restore_route_env(route_module, originals)
    print("✅ PATCH route round-trip (pin + rename) + sorting works")
    return True


def test_delete_route_removes_data_and_files():
    print("Testing DELETE route (record + related data + files)...")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.config.settings import settings
    from backend.services.storage import (
        Note,
        KnowledgeChunk,
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        route_module, manager, originals = _patched_route_env(tmp)
        try:
            app = FastAPI()
            app.include_router(route_module.router, prefix="/videos")
            client = TestClient(app)

            doc_id = _doc_id("delete-me")
            manager.create("task-1", "file")
            manager.update("task-1", document_id=doc_id, status="completed")

            db = settings.tasks_db_path
            SqliteDocumentStore(db).save(_make_document(doc_id))
            SqliteKnowledgeStore(db).save_chunks(doc_id, [
                KnowledgeChunk(id="c-1", document_id=doc_id, ordinal=0,
                               text="hello", start=0.0, end=1.0),
            ])
            SqliteInteractionStore(db).save_note(
                Note(id="n-1", document_id=doc_id, text="note")
            )

            # Files owned by the document/task.
            audio_dir = settings.audio_dir
            audio_dir.mkdir(parents=True, exist_ok=True)
            media_file = audio_dir / "task-1_media.mp4"
            media_file.write_bytes(b"media")
            derived_file = audio_dir / "task-1-extra.wav"
            derived_file.write_bytes(b"derived")
            settings.transcripts_dir.mkdir(parents=True, exist_ok=True)
            transcript_file = settings.transcripts_dir / "task-1.txt"
            transcript_file.write_text("transcript", encoding="utf-8")
            manager.update(
                "task-1", media_path=media_file, transcript_path=transcript_file,
            )

            deleted = client.delete(f"/videos/documents/{doc_id}")
            assert deleted.status_code == 204, deleted.text

            # Records and related data are gone.
            assert SqliteDocumentStore(db).load(doc_id) is None
            assert SqliteKnowledgeStore(db).load_chunks(doc_id) == []
            assert SqliteInteractionStore(db).list_notes(doc_id) == []
            assert manager.get("task-1") is None
            assert client.get("/videos/documents").json() == []

            # Files are gone from disk.
            assert not media_file.exists()
            assert not derived_file.exists()
            assert not transcript_file.exists()

            # Second delete -> 404; malformed id -> 400.
            assert client.delete(f"/videos/documents/{doc_id}").status_code == 404
            assert client.delete("/videos/documents/not-a-uuid").status_code == 400
        finally:
            _restore_route_env(route_module, originals)
    print("✅ DELETE route removes record, related data and files")
    return True


def main() -> int:
    tests = [
        test_pinned_column_migration,
        test_update_roundtrip,
        test_store_delete_cascade,
        test_task_store_delete,
        test_patch_route_roundtrip_and_sorting,
        test_delete_route_removes_data_and_files,
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
            print(f"❌ Test crashed: {exc!r}")
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
    raise SystemExit(main())
