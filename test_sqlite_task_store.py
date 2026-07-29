#!/usr/bin/env python3
"""
Tests for SqliteTaskStore and the JSON→SQLite migration (ADR-0003).

Covers:
- Round-trip, upsert, schema_version column storage
- Missing/corrupt record tolerance
- Unsafe id rejection (same contract as JsonTaskStore)
- Migration import path (v0 + v1 files, idempotent, bad files skipped)
- TaskManager working unchanged on top of the SQLite backend
- Composition-root backend selection via settings

Runs entirely in temp directories; never touches data/.
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


def _make_task(task_id: str = "sqlite-task-1"):
    from backend.services.storage import Task

    return Task(
        id=task_id,
        source="file",
        status="completed",
        progress="Task completed",
        transcript="hello transcript",
        summary="hello summary",
        language="russian",
        transcript_language="ru",
        transcript_segments=[{"start": 0.0, "end": 1.5, "text": "hello"}],
        chapters=[{"title": "Intro", "summary": "s", "start": 0.0}],
        translation_results={"gemini_flash:russian": {"transcript_segments": []}},
        ai_profile_id="gemini_flash",
        ai_profile_name="Gemini Flash",
        ai_provider="gemini",
        ai_model="gemini-2.5-flash",
        timings={"transcription_seconds": 1.5},
        started_at=123.456,
    )


def test_roundtrip_and_upsert():
    """save→load preserves all fields; re-save updates in place."""
    print("Testing SqliteTaskStore round-trip + upsert...")
    from backend.services.storage import SqliteTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteTaskStore(Path(tmp) / "tasks.db")
        store.save(_make_task())
        loaded = store.load("sqlite-task-1")

        assert loaded is not None
        assert loaded.transcript == "hello transcript"
        assert loaded.transcript_segments == [{"start": 0.0, "end": 1.5, "text": "hello"}]
        assert loaded.translation_results == {"gemini_flash:russian": {"transcript_segments": []}}
        assert loaded.timings == {"transcription_seconds": 1.5}
        assert loaded.started_at == 123.456

        # Upsert: modify and re-save; still exactly one row.
        loaded.summary = "updated summary"
        store.save(loaded)
        again = store.load("sqlite-task-1")
        assert again.summary == "updated summary"

        with closing(sqlite3.connect(Path(tmp) / "tasks.db")) as conn:
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert count == 1, f"Expected 1 row after upsert, got {count}"

    print("✅ Round-trip preserves all fields; upsert keeps one row")
    return True


def test_schema_version_column():
    """schema_version is stored as a queryable column and inside the payload."""
    print("\nTesting schema_version storage...")
    from backend.services.storage import SqliteTaskStore
    from backend.services.storage.models import TASK_SCHEMA_VERSION

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "tasks.db"
        store = SqliteTaskStore(db_path)
        store.save(_make_task())

        with closing(sqlite3.connect(db_path)) as conn:
            version, payload = conn.execute(
                "SELECT schema_version, payload FROM tasks WHERE id = ?",
                ("sqlite-task-1",),
            ).fetchone()

        assert version == TASK_SCHEMA_VERSION, f"Column version: {version}"
        assert json.loads(payload)["schema_version"] == TASK_SCHEMA_VERSION

    print("✅ schema_version stored in column and payload")
    return True


def test_missing_and_corrupt():
    """Missing ids and corrupt payloads yield None, never an exception."""
    print("\nTesting missing/corrupt tolerance...")
    from backend.services.storage import SqliteTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "tasks.db"
        store = SqliteTaskStore(db_path)

        assert store.load("missing") is None

        with closing(sqlite3.connect(db_path)) as conn:
            conn.execute(
                "INSERT INTO tasks (id, schema_version, payload) VALUES (?, ?, ?)",
                ("corrupt", 1, "{not valid json"),
            )
        assert store.load("corrupt") is None

    print("✅ Missing/corrupt records return None without raising")
    return True


def test_unsafe_ids():
    """Same id contract as JsonTaskStore: save raises, load returns None."""
    print("\nTesting unsafe id rejection...")
    from backend.services.storage import SqliteTaskStore, Task

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteTaskStore(Path(tmp) / "tasks.db")

        assert store.load("../evil") is None
        assert store.load("") is None

        try:
            store.save(Task(id="../evil", source="file"))
        except ValueError:
            pass
        else:
            raise AssertionError("save() accepted an unsafe task id")

    print("✅ Unsafe ids rejected (load→None, save→ValueError)")
    return True


def test_migration_import():
    """JSON files (v0 and v1) import into SQLite; idempotent; bad files skipped."""
    print("\nTesting JSON→SQLite migration...")
    from backend.services.storage import SqliteTaskStore
    from backend.services.storage.migration import import_json_tasks
    from backend.services.storage.models import TASK_SCHEMA_VERSION, task_to_dict

    with tempfile.TemporaryDirectory() as tmp:
        json_dir = Path(tmp) / "json"
        json_dir.mkdir()

        # v1 file: current schema.
        v1 = task_to_dict(_make_task("task-v1"))
        (json_dir / "task-v1.json").write_text(
            json.dumps(v1, ensure_ascii=False), encoding="utf-8"
        )

        # v0 file: pre-versioning schema (no schema_version key).
        v0 = task_to_dict(_make_task("task-v0"))
        del v0["schema_version"]
        (json_dir / "task-v0.json").write_text(
            json.dumps(v0, ensure_ascii=False), encoding="utf-8"
        )

        # Broken file: must be skipped, not fatal.
        (json_dir / "broken.json").write_text("{nope", encoding="utf-8")

        store = SqliteTaskStore(Path(tmp) / "tasks.db")
        imported, failed = import_json_tasks(json_dir, store)
        assert imported == 2 and failed == 1, f"imported={imported}, failed={failed}"

        for task_id in ("task-v0", "task-v1"):
            loaded = store.load(task_id)
            assert loaded is not None, f"{task_id} missing after import"
            assert loaded.transcript == "hello transcript"

        # v0 record was upgraded to the current schema version on import.
        with closing(sqlite3.connect(Path(tmp) / "tasks.db")) as conn:
            version = conn.execute(
                "SELECT schema_version FROM tasks WHERE id = ?", ("task-v0",)
            ).fetchone()[0]
        assert version == TASK_SCHEMA_VERSION

        # Idempotent: second import yields the same counts, still 2 rows.
        imported, failed = import_json_tasks(json_dir, store)
        assert imported == 2 and failed == 1
        with closing(sqlite3.connect(Path(tmp) / "tasks.db")) as conn:
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert count == 2

    print("✅ Migration imports v0+v1, upgrades schema, idempotent, skips bad files")
    return True


def test_task_manager_on_sqlite():
    """TaskManager works unchanged with the SQLite backend injected."""
    print("\nTesting TaskManager over SqliteTaskStore...")
    from backend.services.storage import SqliteTaskStore
    from backend.services.task_manager import TaskManager

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "tasks.db"
        manager = TaskManager(store=SqliteTaskStore(db_path))
        manager.create("mgr-1", source="file")
        manager.update("mgr-1", timings={"transcription_seconds": 1.0}, ai_model="m1")
        manager.set_status("mgr-1", "processing", "halfway")

        # A fresh manager over the same DB sees the persisted state.
        fresh = TaskManager(store=SqliteTaskStore(db_path))
        loaded = fresh.get("mgr-1")
        assert loaded is not None
        assert loaded.status == "processing"
        assert loaded.timings == {"transcription_seconds": 1.0}
        assert loaded.ai_model == "m1"
        assert fresh.to_dict("mgr-1")["source_type"] == "file"

    print("✅ TaskManager over SQLite: create/update/status persist across instances")
    return True


def test_backend_selection():
    """Composition root picks the backend from settings; app layer unaware."""
    print("\nTesting backend selection...")
    from backend.config.settings import settings
    from backend.services.storage import JsonTaskStore, SqliteTaskStore
    from backend.services.task_manager import _default_store

    original_backend = settings.task_store_backend
    original_db = settings.tasks_db_path
    try:
        settings.task_store_backend = "json"
        assert isinstance(_default_store(), JsonTaskStore)

        with tempfile.TemporaryDirectory() as tmp:
            settings.task_store_backend = "sqlite"
            settings.tasks_db_path = Path(tmp) / "tasks.db"
            assert isinstance(_default_store(), SqliteTaskStore)

        settings.task_store_backend = "bogus"
        try:
            _default_store()
        except ValueError:
            pass
        else:
            raise AssertionError("Unknown backend accepted")
    finally:
        settings.task_store_backend = original_backend
        settings.tasks_db_path = original_db

    print("✅ Backend selection: json/sqlite resolve, unknown rejected")
    return True


def main():
    print("=" * 60)
    print("VideoBrain SqliteTaskStore (ADR-0003) - Test Suite")
    print("=" * 60)

    tests = [
        test_roundtrip_and_upsert,
        test_schema_version_column,
        test_missing_and_corrupt,
        test_unsafe_ids,
        test_migration_import,
        test_task_manager_on_sqlite,
        test_backend_selection,
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
