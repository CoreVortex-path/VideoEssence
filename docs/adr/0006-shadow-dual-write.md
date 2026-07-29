# ADR-0006: Shadow Dual-Write into the Knowledge Layer (Step 2b)

- Status: Accepted
- Date: 2026-07-28
- Context: Phase 2, step 2b. Activates the knowledge schema (ADR-0005) as a
  shadow of the task pipeline, per the frozen domain model (ADR-0004).

## Decision

**Source of truth.** The task pipeline remains authoritative; every API
response is served from the task record exactly as before. The knowledge
layer receives a shadow copy only. The single task-side mutation is
`task.document_id`, set after a successful shadow write (schema v2 field,
no API exposure).

**Failure policy: best-effort, never propagate.** The shadow write runs
after `task_manager.set_result()`. `KnowledgeIngestService` catches all
exceptions, logs them, returns `None`; routes add a second `try/except`.
A completed task without `document_id` is the failure inventory and the
repair queue.

**Content-addressed identity (idempotency).** `document_id` derives from
the sha256 of the uploaded source bytes (computed during the streaming
upload): `uuid5("videobrain:doc:<hash>")`. Chunk ids are
`uuid5("chunk:<doc>:<ordinal>")`; enrichment ids are
`uuid5("enr:<owner>:<type>:<canonical params>:<prompt_version>")`.
Consequences: re-processing the same video resolves to the same Document
(new task, same document — the frozen "re-processed" lifecycle); chunk
sets are rebuilt via replace-set; enrichments upsert instead of
duplicating; a bumped `prompt_version` creates a new record (history
preserved). Identical bytes from different uploads intentionally merge
into one Document (dedup semantics, domain model §1).

**Enrichment mapping.** All derived outputs live in the single
`enrichments` table — no per-type tables: `summary`/`chapters` as
document-scoped (`params={ai_profile, ai_model}`, `prompt_version=1`),
translations as chunk-scoped (`params={target_language, ai_profile}`).
Segment→chunk mapping is by ordinal against `load_chunks(document_id)`.
New enrichment types register a type string + params/payload shape — no
schema work.

**Deferred: media_path and duration_seconds are written as NULL.** Uploads
are still deleted by cleanup; recording a path to a deleted file would
recreate the dangling-path problem fixed in C5. Media retention is an
explicit Phase 2 decision.

**Excluded: the legacy YouTube `/process` endpoint.** It creates no task
record; it will be folded into the task pipeline separately (roadmap M3).

**Observability.** Append-only `data/logs/knowledge_shadow.log` + console:
`SUCCESS`/`FAILURE`/`SKIP` lines with task id, document id, stage, and
error+traceback. No automatic retries — the step 2c backfill (idempotent
thanks to deterministic ids) is the repair path for the
`document_id IS NULL` inventory.

## Alternatives considered

- **Propagate shadow failures (fail the task)** — rejected: the knowledge
  layer is a shadow in this phase; coupling task success to it would make
  a non-authoritative store a runtime dependency.
- **task_id-based document identity** — rejected: every re-upload would
  create a new Document, breaking the re-processing lifecycle and dedup.
- **Random enrichment ids (append-only history)** — rejected for shadow
  writes: re-running the shadow would duplicate rows; deterministic ids
  give idempotency, while `prompt_version` still preserves history.
- **Automatic retry with backoff** — rejected as premature: failures are
  rare, visible, and repairable via the idempotent backfill.

## Consequences

- Processing behavior, API shapes, and frontend are unchanged; suites prove
  failure isolation (task completes even when the ingest explodes).
- Every processed upload now leaves: one Document, an ordered chunk set,
  summary/chapters enrichments; translations shadow on demand.
- The knowledge layer accumulates real data from this point on, so step 2c
  (backfill + read-flip preparation) works against production-shaped data.
