# ADR-0007: Backfill as Pure Orchestration over the Ingest Service (Step 2c)

- Status: Accepted
- Date: 2026-07-28
- Context: Phase 2, step 2c. Imports legacy task records into the knowledge
  layer and serves as the permanent repair path for shadow failures
  (ADR-0006).

## Decision

**Orchestration only.** `backend/services/storage/backfill.py` contains no
mapping, identity, or persistence logic. It enumerates tasks, applies
eligibility rules, and calls the same `KnowledgeIngestService` methods the
live pipeline uses (`shadow_write_task`, `shadow_write_translations`).
Any fix in the service automatically applies to live ingestion and
historical imports alike.

**Eligibility.** Import: `status == "completed"` + has `transcript_segments`
+ `document_id IS NULL`. Skip with distinct counters: already linked,
non-completed, no segments. Keying on `document_id IS NULL` makes every run
an automatic retry of missing/failed shadows; deterministic uuid5 identity
(ADR-0006) makes re-runs non-duplicating. "Repaired" = imported tasks with
a prior FAILURE entry in `knowledge_shadow.log`.

**Transaction boundaries: per document, never global.** Guaranteed by the
stores (each method commits independently; `save_chunks` is one atomic
replace-set) plus a per-task try/except in the loop — one corrupt record
lands in `failed` and cannot abort the run.

**Dry-run** (`--dry-run`): full classification report with zero writes;
verified byte-identical DB in tests.

**Interface addition (justified).** `TaskStore.list_ids()` — enumeration
was impossible with save/load only; ADR-0001 anticipated non-breaking
method additions. Implemented on both backends, tested.

**Legacy identity fallback.** Legacy tasks have no source bytes, so no
`content_hash`: documents get the service's existing fallback id
(`uuid5("doc", "task:<task_id>")`), and `origin_uri`/`title` are NULL
(filenames were never persisted on tasks).

## Consequences

- Accepted limitation: re-uploading a video that was backfilled under the
  task-based fallback id creates a NEW hash-based Document instead of
  merging. If this ever matters, a merge tool can repoint
  `task.document_id` and rewrite chunk/enrichment owners — deferred until
  needed.
- The backfill is safe to run at any time, against either task backend
  (JSON or SQLite, via `_default_store()`), and doubles as the operational
  repair command for shadow failures.
