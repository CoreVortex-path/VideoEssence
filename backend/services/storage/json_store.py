from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from threading import Lock

from .base import TaskStore
from .models import Task, is_valid_task_id, task_from_dict, task_to_dict


class JsonTaskStore(TaskStore):
    """JSON-file TaskStore backend.

    Preserves the existing on-disk format exactly: one
    ``{task_id}.json`` file per task in the configured directory.

    Writes are atomic: payload goes to a unique temp file in the same
    directory, is flushed + fsynced, then os.replace() swaps it onto the
    target path (atomic same-volume rename on Windows and POSIX).
    """

    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._lock = Lock()

    def save(self, task: Task) -> None:
        path = self._task_file(task.id)
        tmp_path = self._dir / f"{task.id}.{uuid.uuid4().hex}.tmp"
        payload = json.dumps(task_to_dict(task), ensure_ascii=False, indent=2)

        with self._lock:
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, path)
            except Exception as exc:
                # Persistence failures must not crash the worker; same
                # tolerance policy as the previous inline implementation.
                print(f"⚠️ Failed to persist task {task.id}: {exc}")
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def load(self, task_id: str) -> Task | None:
        try:
            file_path = self._task_file(task_id)
        except ValueError as exc:
            print(f"⚠️ Refusing to load task: {exc}")
            return None
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return task_from_dict(data)
        except Exception as exc:
            print(f"⚠️ Failed to load task {task_id}: {exc}")
            return None

    def list_ids(self) -> list[str]:
        if not self._dir.exists():
            return []
        return sorted(p.stem for p in self._dir.glob("*.json"))

    def _task_file(self, task_id: str) -> Path:
        if not is_valid_task_id(task_id):
            raise ValueError(f"Unsafe task id rejected: {task_id!r}")
        self._dir.mkdir(parents=True, exist_ok=True)
        return self._dir / f"{task_id}.json"
