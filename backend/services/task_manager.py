from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from threading import Lock
import time

from ..config.settings import settings
from .storage import JsonTaskStore, SqliteTaskStore, Task, TaskStore

# Re-exported so existing ``from ..services.task_manager import Task``
# keeps working after the model moved to the storage package.
__all__ = ["Task", "TaskManager", "task_manager"]


def _default_store() -> TaskStore:
    """Pick the persistence backend from settings.

    This is the composition root for task storage: the only place that
    knows which backend is active. The application layer always talks to
    the TaskStore interface and never branches on the backend.
    """
    backend = (settings.task_store_backend or "json").strip().lower()
    if backend == "json":
        return JsonTaskStore(settings.tasks_dir)
    if backend == "sqlite":
        return SqliteTaskStore(settings.tasks_db_path)
    raise ValueError(
        f"Unsupported task_store_backend {settings.task_store_backend!r}. "
        "Supported values: 'json', 'sqlite'"
    )


class TaskManager:
    """In-memory task registry coordinating state changes and persistence.

    All disk I/O is delegated to a TaskStore backend (JSON files today,
    swappable later). Mutation + persist happen under the manager lock so
    concurrent status updates cannot interleave into a torn write.
    """

    def __init__(self, store: TaskStore | None = None) -> None:
        self._store: TaskStore = store or _default_store()
        self._tasks: Dict[str, Task] = {}
        self._lock = Lock()

    def create(self, task_id: str, source: str) -> Task:
        task = Task(id=task_id, source=source, started_at=time.perf_counter(), timings={})
        with self._lock:
            self._tasks[task_id] = task
            self._save(task)
        return task

    def get(self, task_id: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
        if task:
            return task
        return self._load(task_id)

    def update(self, task_id: str, **fields: Any) -> None:
        """Set fields on a task and persist, under the lock.

        Special case: ``timings`` is merged into the existing timings dict
        rather than replaced, matching incremental timing collection.
        Unknown task ids are a no-op.
        """
        t = self.get(task_id)
        if not t:
            return
        with self._lock:
            for key, value in fields.items():
                if key == "timings" and isinstance(value, dict):
                    merged = dict(t.timings or {})
                    merged.update(value)
                    t.timings = merged
                else:
                    setattr(t, key, value)
            self._save(t)

    def set_status(self, task_id: str, status: str, progress: Optional[str] = None) -> None:
        t = self.get(task_id)
        if t:
            with self._lock:
                t.status = status
                if progress:
                    t.progress = progress
                self._save(t)

    def set_error(self, task_id: str, err: str) -> None:
        t = self.get(task_id)
        if t:
            with self._lock:
                t.status = "failed"
                t.error = err
                t.progress = "Task failed"
                self._save(t)

    def set_result(
        self,
        task_id: str,
        transcript: str,
        transcript_segments: list[dict[str, Any]],
        chapters: list[dict[str, Any]],
        summary: str,
        language: Optional[str],
        transcript_language: Optional[str],
        transcript_path: str,
        summary_path: str,
        ai_profile_id: Optional[str] = None,
        ai_profile_name: Optional[str] = None,
        ai_provider: Optional[str] = None,
        ai_model: Optional[str] = None,
    ) -> None:
        t = self.get(task_id)
        if t:
            with self._lock:
                t.status = "completed"
                t.progress = "Task completed"
                t.transcript = transcript
                t.transcript_segments = transcript_segments
                t.chapters = chapters
                t.summary = summary
                t.language = language
                t.transcript_language = transcript_language
                t.transcript_path = Path(transcript_path)
                t.summary_path = Path(summary_path)
                t.ai_profile_id = ai_profile_id or t.ai_profile_id
                t.ai_profile_name = ai_profile_name or t.ai_profile_name
                t.ai_provider = ai_provider or t.ai_provider
                t.ai_model = ai_model or t.ai_model
                self._save(t)

    def get_status(self, task_id: str) -> Optional[str]:
        t = self.get(task_id)
        return t.status if t else None

    def to_dict(self, task_id: str) -> Optional[dict]:
        t = self.get(task_id)
        if not t:
            return None

        return {
            "task_id": t.id,
            "status": t.status,
            "progress": t.progress,
            "error": t.error,
            "transcript": t.transcript,
            "transcript_segments": t.transcript_segments or [],
            "chapters": t.chapters or [],
            "summary": t.summary,
            "language": t.language,
            "transcript_language": t.transcript_language,
            "source_type": t.source,
            "ai_profile_id": t.ai_profile_id,
            "ai_profile_name": t.ai_profile_name,
            "ai_provider": t.ai_provider,
            "ai_model": t.ai_model,
            "translation_results": t.translation_results or {},
            "timings": t.timings or {},
        }

    def _save(self, task: Task) -> None:
        self._store.save(task)

    def _load(self, task_id: str) -> Optional[Task]:
        task = self._store.load(task_id)
        if task:
            with self._lock:
                self._tasks[task_id] = task
        return task


task_manager = TaskManager()
