#!/usr/bin/env python3
"""
Tests for global notes (Этап: Smart PDF Workspace notes memory).

Covers:
- Note model: tag/page/position roundtrip, document_id nullable
- notes table migration: NOT NULL document_id -> nullable
- NotesService: validation (anchor rules), list_global filter/sort/limit/offset
- Routes: POST /notes, GET /notes with query params

No AI involved.
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _service(tmp: str):
    from backend.services.document_features_service import NotesService
    from backend.services.storage import (
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    db = Path(tmp) / "videobrain.db"
    return (
        NotesService(SqliteDocumentStore(db), SqliteInteractionStore(db), SqliteKnowledgeStore(db)),
        db,
    )


def test_note_model_roundtrip():
    print("Testing note model roundtrip (tag/page/position)...")
    from backend.services.storage import Note, SqliteInteractionStore

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteInteractionStore(Path(tmp) / "videobrain.db")
        note = Note(
            id="note-1",
            document_id=None,  # global note without a document
            text="Разобраться с методом Монте-Карло",
            tag="monte-carlo",
        )
        store.save_note(note)
        loaded = store.load_note("note-1")
        assert loaded is not None
        assert loaded.document_id is None
        assert loaded.tag == "monte-carlo"
        assert loaded.page is None and loaded.position is None

        anchored = Note(
            id="note-2",
            document_id="doc-1",
            text="проверить этот вывод",
            tag="monte-carlo",
            page=17,
            position=[342.5, 516.2],
        )
        store.save_note(anchored)
        loaded = store.load_note("note-2")
        assert loaded is not None
        assert loaded.page == 17 and loaded.position == [342.5, 516.2]
        assert len(store.list_all_notes()) == 2
    print("✅ Note model roundtrip works")
    return True


def test_notes_table_migration():
    print("Testing notes table migration (NOT NULL -> nullable)...")
    from backend.services.storage import Note, SqliteInteractionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "videobrain.db"
        # Simulate a pre-migration database.
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "CREATE TABLE notes ("
                "id TEXT PRIMARY KEY, document_id TEXT NOT NULL, chunk_id TEXT,"
                "note_text TEXT NOT NULL, schema_version INTEGER NOT NULL,"
                "payload TEXT NOT NULL, created_at TEXT, updated_at TEXT)"
            )
            conn.execute(
                "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "old-1", "doc-1", None, "legacy note", 1,
                    json.dumps({"schema_version": 1, "id": "old-1",
                                "document_id": "doc-1", "text": "legacy note"}),
                    "2026-01-01T00:00:00", "2026-01-01T00:00:00",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        # Opening the store must migrate the table and keep the data.
        store = SqliteInteractionStore(db)
        legacy = store.load_note("old-1")
        assert legacy is not None and legacy.text == "legacy note"
        store.save_note(Note(id="new-1", document_id=None, text="global"))
        assert store.load_note("new-1") is not None
    print("✅ Notes table migration works")
    return True


def test_service_validation():
    print("Testing NotesService validation...")
    from backend.services.document_features_service import FeatureValidationError

    with tempfile.TemporaryDirectory() as tmp:
        service, _ = _service(tmp)
        for kwargs in (
            {"position": [1.0, 2.0]},                 # position without page
            {"page": 0},                              # page < 1
            {"page": 1, "position": [1.0]},           # malformed position
            {"page": 1, "position": [1.0, "x"]},      # non-numeric
        ):
            try:
                service.create(None, "text", None, None, **kwargs)
            except FeatureValidationError:
                pass
            else:
                raise AssertionError(f"expected FeatureValidationError for {kwargs}")
        note = service.create(None, "ok", None, None, page=1, position=[1.0, 2.0])
        assert note.page == 1 and note.position == [1.0, 2.0]
    print("✅ NotesService validation works")
    return True


def test_list_global_filters():
    print("Testing list_global filter/sort/limit/offset...")
    with tempfile.TemporaryDirectory() as tmp:
        service, _ = _service(tmp)
        service.create(None, "a", None, None, tag="math")
        service.create(None, "b", None, None, tag="physics")
        service.create(None, "c", None, None, tag="math")
        assert len(service.list_global()) == 3
        assert {n.text for n in service.list_global(tag="Math")} == {"a", "c"}
        assert len(service.list_global(limit=1)) == 1
        assert len(service.list_global(limit=1, offset=2)) == 1
        assert len(service.list_global(offset=3)) == 0
        by_tag = service.list_global(sort="tag_asc")
        assert [n.tag for n in by_tag] == ["math", "math", "physics"]
        assert service.list_global(date_from="2999-01-01") == []
        assert len(service.list_global(date_to="2999-01-01")) == 3
        try:
            service.list_global(sort="bogus")
        except Exception as exc:
            assert "sort" in str(exc).lower()
        else:
            raise AssertionError("expected error for invalid sort")
    print("✅ list_global filter/sort/limit/offset works")
    return True


def test_global_note_routes():
    print("Testing global note routes...")
    import backend.routes.document_features as route_module
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.services.document_features_service import NotesService
    from backend.services.storage import (
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "videobrain.db"
        service = NotesService(
            SqliteDocumentStore(db), SqliteInteractionStore(db), SqliteKnowledgeStore(db)
        )
        original = route_module._notes_service
        try:
            route_module._notes_service = service
            app = FastAPI()
            app.include_router(route_module.router)
            client = TestClient(app)

            created = client.post("/notes", json={
                "text": "глобальная заметка", "tag": "ideas",
            })
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["document_id"] is None and body["tag"] == "ideas"
            assert body["page"] is None and body["position"] is None

            anchored = client.post("/notes", json={
                "text": "на странице", "page": 3, "position": [10.0, 20.0],
            })
            assert anchored.status_code == 201, anchored.text

            listed = client.get("/notes")
            assert listed.status_code == 200
            assert len(listed.json()) == 2

            filtered = client.get("/notes", params={"tag": "ideas"})
            assert [n["text"] for n in filtered.json()] == ["глобальная заметка"]

            paged = client.get("/notes", params={"limit": 1, "offset": 1})
            assert paged.status_code == 200 and len(paged.json()) == 1

            bad = client.post("/notes", json={"text": "x", "position": [1.0, 2.0]})
            assert bad.status_code in (400, 422), bad.status_code

            # global update/delete by id (notes without a document included)
            note_id = body["id"]
            updated = client.put(f"/notes/{note_id}", json={"text": "обновлено", "tag": ""})
            assert updated.status_code == 200, updated.text
            assert updated.json()["text"] == "обновлено"
            assert updated.json()["tag"] is None  # empty string clears the tag
            deleted = client.delete(f"/notes/{note_id}")
            assert deleted.status_code == 204
            assert len(client.get("/notes").json()) == 1
            missing = client.delete(f"/notes/{note_id}")
            assert missing.status_code == 404
        finally:
            route_module._notes_service = original
    print("✅ Global note routes work")
    return True


def test_note_video_time_roundtrip():
    print("Testing note video_time roundtrip...")
    from backend.services.storage import Note, SqliteInteractionStore

    with tempfile.TemporaryDirectory() as tmp:
        service, _ = _service(tmp)
        # Old notes without video_time keep working (field is optional).
        plain = service.create(None, "без таймкода", None, None)
        assert plain.video_time is None

        timed = service.create(None, "момент из видео", None, None, video_time=83.5)
        assert timed.video_time == 83.5

        store = SqliteInteractionStore(Path(tmp) / "videobrain.db")
        loaded = store.load_note(timed.id)
        assert loaded is not None and loaded.video_time == 83.5
        assert store.load_note(plain.id).video_time is None

        # Update keeps the value when video_time is omitted, overrides when given.
        service.update_global(timed.id, "момент из видео (upd)")
        assert service.get_global(timed.id).video_time == 83.5
    print("✅ Note video_time roundtrip works")
    return True


def test_note_video_time_routes():
    print("Testing note video_time via routes...")
    import backend.routes.document_features as route_module
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.services.document_features_service import NotesService
    from backend.services.storage import (
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "videobrain.db"
        documents = SqliteDocumentStore(db)
        documents.save(_make_document("doc-video"))
        service = NotesService(documents, SqliteInteractionStore(db), SqliteKnowledgeStore(db))
        original = route_module._notes_service
        try:
            route_module._notes_service = service
            app = FastAPI()
            app.include_router(route_module.router)
            client = TestClient(app)

            created = client.post(
                "/documents/doc-video/notes",
                json={"text": "заметка с таймкодом", "selected_text": "цитата", "video_time": 3723.0},
            )
            assert created.status_code == 201, created.text
            assert created.json()["video_time"] == 3723.0

            listed = client.get("/documents/doc-video/notes")
            assert listed.status_code == 200
            assert listed.json()[0]["video_time"] == 3723.0

            got = client.get(f"/documents/doc-video/notes/{created.json()['id']}")
            assert got.json()["video_time"] == 3723.0

            updated = client.put(
                f"/documents/doc-video/notes/{created.json()['id']}",
                json={"text": "заметка с таймкодом", "video_time": 4000.5},
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["video_time"] == 4000.5

            bad = client.post(
                "/documents/doc-video/notes",
                json={"text": "x", "video_time": -1.0},
            )
            assert bad.status_code in (400, 422), bad.status_code
        finally:
            route_module._notes_service = original
    print("✅ Note video_time routes work")
    return True


def _make_document(document_id: str):
    from backend.services.storage import Document

    return Document(id=document_id, source_type="video", title="Video doc")


def main() -> int:
    tests = [
        test_note_model_roundtrip,
        test_notes_table_migration,
        test_service_validation,
        test_list_global_filters,
        test_global_note_routes,
        test_note_video_time_roundtrip,
        test_note_video_time_routes,
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
