from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Task


class TaskStore(ABC):
    """Persistence contract for task records.

    Implementations must:
    - make save() atomic: a crash mid-write must never leave a
      partially written record (no truncated/corrupt state visible to load);
    - tolerate concurrent save()/load() calls;
    - return None from load() for missing or unreadable records instead
      of raising.

    The interface is intentionally minimal. Query/delete/list methods are
    deferred until retention and search requirements arrive (see ADR-0001).
    """

    @abstractmethod
    def save(self, task: Task) -> None:
        """Persist (upsert) a task record atomically."""
        raise NotImplementedError()

    @abstractmethod
    def load(self, task_id: str) -> Task | None:
        """Load a task record, or None if it does not exist or is unreadable."""
        raise NotImplementedError()

    @abstractmethod
    def list_ids(self) -> list[str]:
        """Return all stored task ids (for enumeration, e.g. backfill)."""
        raise NotImplementedError()
