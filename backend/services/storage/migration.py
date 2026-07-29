"""One-shot import of legacy JSON task files into the SQLite backend.

Run from the project root:

    python -m backend.services.storage.migration

The import is idempotent (upserts by task id), read-only on the JSON
files, and upgrades records implicitly: files written before versioning
(no ``schema_version`` key, i.e. v0) are re-serialized through
``task_to_dict`` and stored at the current schema version.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import task_from_dict
from .sqlite_store import SqliteTaskStore


def import_json_tasks(json_dir: Path, store: SqliteTaskStore) -> tuple[int, int]:
    """Import every ``*.json`` task file from *json_dir* into *store*.

    Returns (imported, failed). Existing rows are overwritten (upsert),
    so re-running is safe. Unreadable/invalid files are skipped with a
    warning and counted as failed.
    """
    json_dir = Path(json_dir)
    imported = 0
    failed = 0

    files = sorted(json_dir.glob("*.json")) if json_dir.exists() else []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            task = task_from_dict(data)
            store.save(task)
            imported += 1
        except Exception as exc:
            print(f"⚠️ Skipping {path.name}: {exc}")
            failed += 1

    return imported, failed


def main() -> int:
    from ...config.settings import settings  # deferred: needs project root cwd

    store = SqliteTaskStore(settings.tasks_db_path)
    imported, failed = import_json_tasks(settings.tasks_dir, store)
    print(
        f"Migration complete: {imported} task(s) imported into "
        f"{settings.tasks_db_path}, {failed} file(s) skipped."
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
