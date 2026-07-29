# ADR-0001: TaskStore Persistence Abstraction

- Status: Accepted
- Date: 2026-07-28
- Context: C3 of the critical-issues roadmap; foundation for the Phase 2 knowledge-platform migration (Document / KnowledgeChunk / KnowledgeStore).

## Context

Task persistence was tangled inside `TaskManager`: it owned the in-memory
cache, the JSON serialization schema, and file I/O in one class. Writes were
non-atomic (`write_text` directly to the target file), so a crash mid-write
could corrupt a task record. `routes/video.py` called the private
`task_manager._save(task)` five times after mutating tasks outside the lock,
bypassing any concurrency discipline.

The long-term direction (personal knowledge platform) requires a storage seam
where a SQLite-backed store — and later persistent knowledge objects — can be
introduced without touching route or pipeline code.

## Decision

Introduce a storage package `backend/services/storage/`:

- `base.py` — `TaskStore` ABC with exactly two methods: `save(task)` (atomic
  upsert) and `load(task_id)` (returns `None` for missing/unreadable records).
- `json_store.py` — `JsonTaskStore`, preserving the existing on-disk format
  byte-compatibly. Writes go to a unique temp file, are flushed + fsynced,
  then swapped onto the target with `os.replace()` (atomic same-volume rename
  on Windows and POSIX). Carries its own write lock.
- `models.py` — the `Task` dataclass plus `task_to_dict` / `task_from_dict`,
  making the serialization schema a single, reusable owner.

`TaskManager` keeps the in-memory cache and lock discipline, delegates all
disk I/O to an injected `TaskStore` (default: `JsonTaskStore`), and gains a
public `update(task_id, **fields)` method (`timings` merges; other fields are
set). Routes no longer call any private persistence method.

## Alternatives considered

- **SQLite now** — rejected: user constraint for this phase; the JSON backend
  stays. The interface makes the later swap a new class plus constructor
  injection, nothing more.
- **Keep `_save` public and let routes mutate tasks directly** — rejected:
  mutations outside the lock race with the status writer and produced the
  original torn-state risk.
- **Full repository interface (delete/list/query)** — rejected as speculative:
  retention and search requirements are not here yet; adding methods to the
  ABC later is non-breaking.

## Consequences

- A crash can no longer leave a truncated task JSON; at worst an orphan
  `*.tmp` file remains (harmless; cleanup deferred).
- The SQLite migration (Phase 2, step 1) requires only: a new
  `SqliteTaskStore(TaskStore)` and one changed constructor argument at the
  singleton.
- `Task` is re-exported from `task_manager` — no import breakage.
- API, on-disk schema, and frontend behavior are unchanged.

## Known remaining debt (explicitly not addressed here)

- Unbounded growth: no retention/TTL for tasks, in-memory cache never evicts.
- `Task` still conflates job state with produced artifacts; separating them
  is Phase 2 (Document/KnowledgeChunk).
