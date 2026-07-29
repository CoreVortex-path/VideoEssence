# ADR-0003: SQLite TaskStore Backend with Composition-Root Selection

- Status: Accepted
- Date: 2026-07-28
- Context: Phase 2, step 1 of the knowledge-platform roadmap. Builds on the
  TaskStore interface (ADR-0001) and the `schema_version` marker.

## Context

The JSON-file backend works but does not scale as a foundation: no atomic
multi-record operations, no queries, unbounded directory growth, and fragile
corruption recovery. Phase 2 needs a real database behind the existing
`TaskStore` interface without the application layer noticing the swap, and
without losing the 66 existing JSON task records.

## Decision

**`SqliteTaskStore`** (`backend/services/storage/sqlite_store.py`):

- One table: `tasks(id TEXT PRIMARY KEY, schema_version INTEGER, payload TEXT)`.
- `payload` is the exact `task_to_dict()` JSON. SQL never interprets record
  content — serialization/deserialization stays in `storage/models.py`. No
  business logic in SQL; the database is an opaque record container with
  atomicity and durability guarantees.
- `schema_version` is duplicated as a column so future migrations can filter
  records by version without deserializing every payload.
- Writes are single-statement `INSERT OR REPLACE` upserts — atomic by
  transaction. Reads/writes use per-operation connections (WAL journal),
  guarded by a lock, mirroring `JsonTaskStore`'s concurrency contract.
- Same id contract as the JSON backend via the shared
  `is_valid_task_id()` helper (now in `storage/models.py`).

**Backend selection at the composition root only.** New settings
`task_store_backend` (`"json"` default) and `tasks_db_path`.
`TaskManager`'s default factory (`_default_store()`) is the single place
that knows which backend is active. Routes, pipeline, and services talk only
to the `TaskStore` interface.

**Migration path.** `backend/services/storage/migration.py`:
`import_json_tasks(json_dir, store)` upserts every `data/tasks/*.json` into
SQLite. Idempotent, read-only on the source files, skips corrupt files with
a warning. v0 records (no `schema_version` key) are upgraded implicitly by
re-serialization through `task_to_dict`. Run with
`python -m backend.services.storage.migration` from the project root.

**JSON backend remains fully functional** and stays the default until the
operator flips `task_store_backend=sqlite` after running the import.

## Alternatives considered

- **Columnar schema (status, source, timings as columns)** — rejected for
  now: it duplicates the schema in SQL and Python and invites query logic
  into the store before query requirements exist. The payload column keeps
  one schema owner (`storage/models.py`). Columns can be added later,
  populated from payloads, when retention/search requirements arrive.
- **SQLAlchemy/SQLModel** — rejected as premature: two methods over one
  table need no ORM; stdlib `sqlite3` has zero dependency cost. An ORM can
  be introduced when Document/KnowledgeChunk add relational complexity.
- **Shared persistent connection** — rejected: per-operation connections are
  simpler and avoid cross-thread connection state; the operation rate
  (status writes) does not justify connection pooling yet.
- **Delete JSON files after import** — rejected: the import is read-only so
  the JSON directory remains a working fallback during the migration window.

## Consequences

- Swapping persistence for the whole app = run the import once, set
  `task_store_backend=sqlite` in `.env`, restart.
- The interface, API, and task JSON schema are unchanged; `schema_version`
  continues to be stored (column + payload).
- Remaining debt unchanged: no retention/TTL, no list/query methods on the
  interface (added when requirements arrive, non-breaking).
- Extension path to `DocumentStore` / `KnowledgeStore` is documented in
  `docs/storage-architecture.md`.
