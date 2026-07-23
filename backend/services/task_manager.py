from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any
from pathlib import Path
from threading import Lock
import json
import time

from ..config.settings import settings


@dataclass
class Task:
    id: str
    source: str
    status: str = "created"
    progress: str = "Task created"
    error: Optional[str] = None
    transcript_path: Optional[Path] = None
    summary_path: Optional[Path] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    language: Optional[str] = None
    transcript_segments: list[dict[str, Any]] | None = None
    chapters: list[dict[str, Any]] | None = None
    timings: dict[str, float] | None = None
    started_at: float | None = None


class TaskManager:
    def __init__(self) -> None:
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

    def set_status(self, task_id: str, status: str, progress: Optional[str] = None) -> None:
        t = self.get(task_id)
        if t:
            t.status = status
            if progress:
                t.progress = progress
            self._save(t)

    def set_error(self, task_id: str, err: str) -> None:
        t = self.get(task_id)
        if t:
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
        transcript_path: str,
        summary_path: str,
    ) -> None:
        t = self.get(task_id)
        if t:
            t.status = "completed"
            t.progress = "Task completed"
            t.transcript = transcript
            t.transcript_segments = transcript_segments
            t.chapters = chapters
            t.summary = summary
            t.language = language
            t.transcript_path = Path(transcript_path)
            t.summary_path = Path(summary_path)
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
            "source_type": t.source,
            "timings": t.timings or {},
        }

    def _task_file(self, task_id: str) -> Path:
        settings.tasks_dir.mkdir(parents=True, exist_ok=True)
        return settings.tasks_dir / f"{task_id}.json"

    def _save(self, task: Task) -> None:
        try:
            data = {
                "id": task.id,
                "source": task.source,
                "status": task.status,
                "progress": task.progress,
                "error": task.error,
                "transcript_path": str(task.transcript_path) if task.transcript_path else None,
                "summary_path": str(task.summary_path) if task.summary_path else None,
                "transcript": task.transcript,
                "summary": task.summary,
                "language": task.language,
                "transcript_segments": task.transcript_segments or [],
                "chapters": task.chapters or [],
                "timings": task.timings or {},
                "started_at": task.started_at,
            }
            self._task_file(task.id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"⚠️ Failed to persist task {task.id}: {exc}")

    def _load(self, task_id: str) -> Optional[Task]:
        file_path = self._task_file(task_id)
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            task = Task(
                id=data["id"],
                source=data.get("source", "file"),
                status=data.get("status", "created"),
                progress=data.get("progress", "Task created"),
                error=data.get("error"),
                transcript_path=Path(data["transcript_path"]) if data.get("transcript_path") else None,
                summary_path=Path(data["summary_path"]) if data.get("summary_path") else None,
                transcript=data.get("transcript"),
                summary=data.get("summary"),
                language=data.get("language"),
                transcript_segments=data.get("transcript_segments") or [],
                chapters=data.get("chapters") or [],
                timings=data.get("timings") or {},
                started_at=data.get("started_at"),
            )
            with self._lock:
                self._tasks[task_id] = task
            return task
        except Exception as exc:
            print(f"⚠️ Failed to load task {task_id}: {exc}")
            return None


task_manager = TaskManager()
