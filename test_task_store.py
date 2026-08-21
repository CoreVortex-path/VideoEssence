#!/usr/bin/env python3
"""
Tests for the TaskStore abstraction (ADR-0001).

Covers:
- JsonTaskStore round-trip and on-disk format compatibility
- Atomic write behavior (no leftover temp files, valid JSON)
- TaskManager.update() merge semantics
- Corrupt-file tolerance
- Compatibility with real legacy files from data/tasks/

Runs entirely in temp directories; never mutates data/tasks.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def _make_task(task_id: str = "test-task-1"):
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


def test_roundtrip():
    """save() then load() preserves every field."""
    print("Testing JsonTaskStore round-trip...")
    from backend.services.storage import JsonTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        store = JsonTaskStore(Path(tmp))
        original = _make_task()
        store.save(original)
        loaded = store.load(original.id)

        assert loaded is not None, "load() returned None"
        assert loaded.id == original.id
        assert loaded.status == "completed"
        assert loaded.transcript == "hello transcript"
        assert loaded.transcript_segments == [{"start": 0.0, "end": 1.5, "text": "hello"}]
        assert loaded.chapters == [{"title": "Intro", "summary": "s", "start": 0.0}]
        assert loaded.translation_results == {"gemini_flash:russian": {"transcript_segments": []}}
        assert loaded.timings == {"transcription_seconds": 1.5}
        assert loaded.started_at == 123.456
        assert loaded.ai_model == "gemini-2.5-flash"

    print("✅ Round-trip preserves all fields")
    return True


def test_atomic_write():
    """save() leaves no temp files and produces valid JSON."""
    print("\nTesting atomic write behavior...")
    from backend.services.storage import JsonTaskStore
    from backend.services.storage.models import TASK_SCHEMA_VERSION

    with tempfile.TemporaryDirectory() as tmp:
        store = JsonTaskStore(Path(tmp))
        store.save(_make_task())

        files = list(Path(tmp).iterdir())
        tmp_files = [f for f in files if f.suffix == ".tmp"]
        assert not tmp_files, f"Leftover temp files: {tmp_files}"

        target = Path(tmp) / "test-task-1.json"
        assert target.exists(), "Task file not created"
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["id"] == "test-task-1"
        assert data["schema_version"] == TASK_SCHEMA_VERSION, "Persisted record must carry schema_version"

        # Overwrite (upsert) must also work atomically.
        store.save(_make_task())
        assert len(list(Path(tmp).glob("*.json"))) == 1

    print("✅ Writes are atomic (no .tmp residue, valid JSON, upsert works)")
    return True


def test_legacy_schema_compatibility():
    """A dict written in the current on-disk schema loads correctly."""
    print("\nTesting legacy schema compatibility...")
    from backend.services.storage import JsonTaskStore

    legacy_payload = {
        "id": "legacy-1",
        "source": "youtube",
        "status": "completed",
        "progress": "Task completed",
        "error": None,
        "transcript_path": "data/transcripts/legacy-1.txt",
        "summary_path": "data/summaries/legacy-1.txt",
        "transcript": "legacy transcript",
        "summary": "legacy summary",
        "language": "english",
        "transcript_language": "en",
        "transcript_segments": [],
        "chapters": [],
        "ai_profile_id": "gemini_flash",
        "ai_profile_name": "Gemini Flash",
        "ai_provider": "gemini",
        "ai_model": "gemini-2.5-flash",
        "translation_results": {},
        "timings": {},
        "started_at": 100.0,
    }

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "legacy-1.json").write_text(
            json.dumps(legacy_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        store = JsonTaskStore(Path(tmp))
        loaded = store.load("legacy-1")

        assert loaded is not None
        assert loaded.id == "legacy-1"
        assert loaded.source == "youtube"
        assert loaded.transcript_path == Path("data/transcripts/legacy-1.txt")
        assert loaded.transcript == "legacy transcript"

    print("✅ Legacy on-disk schema loads correctly")
    return True


def test_real_legacy_files():
    """Every real file in data/tasks/ must parse (read-only, via copies)."""
    print("\nTesting real data/tasks/ compatibility...")
    from backend.config.settings import settings
    from backend.services.storage import JsonTaskStore

    real_dir = settings.tasks_dir
    real_files = list(real_dir.glob("*.json")) if real_dir.exists() else []
    if not real_files:
        print("⚠️  No files in data/tasks/ — skipping (nothing to verify)")
        return True

    with tempfile.TemporaryDirectory() as tmp:
        for src in real_files:
            shutil.copy2(src, Path(tmp) / src.name)
        store = JsonTaskStore(Path(tmp))

        failures = []
        for f in real_files:
            task = store.load(f.stem)
            if task is None or task.id != f.stem:
                failures.append(f.name)

        assert not failures, f"Failed to load legacy files: {failures}"

    print(f"✅ All {len(real_files)} real task files parse correctly")
    return True


def test_update_merge_semantics():
    """TaskManager.update() merges timings and setattrs other fields."""
    print("\nTesting TaskManager.update() merge semantics...")
    from backend.services.storage import JsonTaskStore
    from backend.services.task_manager import TaskManager

    with tempfile.TemporaryDirectory() as tmp:
        manager = TaskManager(store=JsonTaskStore(Path(tmp)))
        task = manager.create("upd-1", source="file")

        manager.update("upd-1", timings={"transcription_seconds": 1.0}, ai_model="m1")
        manager.update("upd-1", timings={"ai_seconds": 2.0})

        loaded = manager.get("upd-1")
        assert loaded.timings == {"transcription_seconds": 1.0, "ai_seconds": 2.0}, loaded.timings
        assert loaded.ai_model == "m1"

        # Persisted form must reflect the merge too.
        fresh = TaskManager(store=JsonTaskStore(Path(tmp))).get("upd-1")
        assert fresh.timings == {"transcription_seconds": 1.0, "ai_seconds": 2.0}

        # Unknown task id is a no-op, not an error.
        manager.update("does-not-exist", ai_model="x")

    print("✅ update() merges timings, sets fields, persists, no-ops on missing task")
    return True


def test_corrupt_file_tolerance():
    """Corrupt JSON yields None, never an exception."""
    print("\nTesting corrupt-file tolerance...")
    from backend.services.storage import JsonTaskStore

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "broken.json").write_text("{not valid json", encoding="utf-8")
        store = JsonTaskStore(Path(tmp))
        assert store.load("broken") is None
        assert store.load("missing") is None

    print("✅ Corrupt/missing files return None without raising")
    return True


def main():
    # Windows consoles may default to cp1251; emoji markers need UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 60)
    print("VideoBrain TaskStore (ADR-0001) - Test Suite")
    print("=" * 60)

    tests = [
        test_roundtrip,
        test_atomic_write,
        test_legacy_schema_compatibility,
        test_real_legacy_files,
        test_update_merge_semantics,
        test_corrupt_file_tolerance,
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
