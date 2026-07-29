# Operations Reference

Day-to-day operator guide: storage backends, migration/backfill commands,
rollback, and observability. Run all commands from the project root with
the project venv active.

## Storage Backends

Task persistence is selectable; document/knowledge persistence is always
SQLite.

| Backend | Where | When |
|---|---|---|
| `json` (default) | `data/tasks/{task_id}.json` | default, zero setup |
| `sqlite` | `data/videobrain.db` | recommended for long-running installs |

Documents, chunks, and enrichments always live in `data/videobrain.db`
regardless of this setting.

### Switching to SQLite

```bash
# 1. Import existing JSON task files (idempotent, read-only on the JSON side)
python -m backend.services.storage.migration

# 2. Activate
#    .env: TASK_STORE_BACKEND=sqlite

# 3. Restart the server
```

Switching back to `json` is safe at any time — the JSON files are never
deleted by the migration.

## Backfill & Repair

The backfill imports historical tasks into the knowledge layer **and**
repairs any task whose shadow write failed (completed tasks without a
`document_id`). It uses the same ingestion path as live processing, is
idempotent, and is safe to run at any time.

```bash
# Preview decisions, zero writes
python -m backend.services.storage.backfill --dry-run

# Apply
python -m backend.services.storage.backfill
```

Report fields: `scanned`, `already linked`, `imported`, `repaired`,
`skipped (not done)`, `skipped (no segments)`, `failed`, `elapsed`.

- `repaired` counts tasks that had a previous shadow FAILURE and succeeded
  this run.
- Re-running immediately after a successful run reports everything as
  `already linked` — that is the idempotency guarantee.

## Rollback (Read-Flip)

The status endpoint serves content from the knowledge layer. Two
independent safety mechanisms:

1. **Automatic per-request fallback** — if knowledge data is missing or
   incomplete for a task, the endpoint silently serves the task record
   (which retains its content fields). A warning is printed to the server
   console.
2. **Kill switch** — set `KNOWLEDGE_READ_ENABLED=false` in `.env` and
   restart: all responses come from task records, exactly as before the
   read-flip. No data migration is involved either way.

## Observability

| Signal | Location |
|---|---|
| Shadow-write events (`SUCCESS` / `FAILURE` / `SKIP`, with task & document ids) | `data/logs/knowledge_shadow.log` |
| Raw AI responses (diagnostics) | `data/logs/ai_response_*.txt` |
| Last unparseable AI response | `data/logs/failed_ai_response.json` |
| Server console | pipeline progress, cleanup, read-fallback warnings |

Quick health checks:

```bash
# Completed tasks missing their knowledge-layer link (should be 0 after backfill)
python -m backend.services.storage.backfill --dry-run

# Gemini connectivity with the configured key
curl http://localhost:8000/videos/health/gemini
```

## Data Layout

| Path | Contents | Retention |
|---|---|---|
| `data/tasks/` | Task records (JSON backend) | kept (no TTL yet) |
| `data/videobrain.db` | SQLite: tasks (if enabled), documents, chunks, enrichments | kept |
| `data/transcripts/`, `data/summaries/` | Result text artifacts per task | kept |
| `data/audio/` | Uploads and extracted audio | deleted after processing |
| `data/logs/` | Shadow log, AI diagnostics | grows unbounded (rotation planned) |

## Test Suites

All suites are standalone scripts (`python test_<name>.py`; on Windows
consoles prefix `PYTHONIOENCODING=utf-8`): `test_refactoring`,
`test_task_store`, `test_sqlite_task_store`, `test_knowledge_stores`,
`test_security_fixes`, `test_shadow_ingest`, `test_backfill`,
`test_read_flip`. See the README's Development section for what each covers.
