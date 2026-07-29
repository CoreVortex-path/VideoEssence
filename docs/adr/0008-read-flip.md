# ADR-0008: Read-Flip — Status Endpoint Served from the Knowledge Layer (Step 3)

- Status: Accepted
- Date: 2026-07-28
- Context: Phase 2, step 3. Completes the migration arc: the knowledge layer
  (ADR-0004..0007) becomes a read source for the primary status endpoint.

## Decision

**One read path flips.** `GET /videos/status/{task_id}` serves content
fields (transcript, transcript_segments, chapters, summary, language) from
Document/KnowledgeChunk/Enrichment via `KnowledgeReadService.assemble_status()`.
Job state (status/progress/error/timings/ai-profile) always comes from the
task record — the frozen domain split (Task = job log).

**Compatibility adapter, not a new contract.** The service reproduces the
exact `TaskManager.to_dict()` shape; `TaskStatusResponse` and the frontend
are untouched. Segments are served plain (no inline translations) — exactly
today's behavior.

**All-or-nothing rule.** Assembly returns `None` unless document, chunks,
AND summary+chapters enrichments are all present — a partially shadowed
task never yields a partially flipped response.

**Three-layer rollback.**
1. Kill switch: `settings.knowledge_read_enabled` (env
   `KNOWLEDGE_READ_ENABLED`) — instant global revert, no deploy.
2. Automatic per-request fallback: missing/incomplete knowledge data or any
   assembly error → the legacy task-record payload, silently (with a
   one-line warning log). The dual-write keeps task content fields
   populated, so the fallback is always complete.
3. No data rollback needed: the flip writes nothing; task records retain
   their content fields.

**Explicitly unchanged.** The translate endpoint keeps reading
`task.transcript_segments`/`translation_results` (still written by the
pipeline) — its flip rides with the future task-slimming decision. No new
domain concepts, no storage model changes, no write-path changes.

## Alternatives considered

- **Flip all read paths at once (including translate)** — rejected: larger
  blast radius; the translate cache semantics (stringly keys) deserve their
  own designed migration rather than a ride-along.
- **Partial flip (serve whichever fields are available)** — rejected:
  mixed-source responses make debugging and contract reasoning hard;
  all-or-nothing keeps every response single-sourced.
- **Slim the task payload in the same step** — rejected: that is a
  write-path/storage change, out of the declared scope; it becomes safe
  only after the flipped read path proves itself in production.

## Consequences

- The status endpoint now depends on the knowledge layer for content, with
  automatic degradation to the legacy path — the knowledge store can never
  break the API.
- Task content fields are now write-only legacy; their removal (task
  slimming, schema v3) is the next candidate step, separately approved.
- The architecture migration (Task-centric → Document/Knowledge) is
  functionally complete: writes shadow, reads flipped, rollback instant.

## Accepted differences (real-data A/B check, 40 backfilled tasks)

The A/B comparison found three difference classes, all reviewed and
accepted (uniform contract chosen over special-casing legacy artifacts):

1. **`transcript_language` (40 tasks, improvement):** legacy `None` →
   assembled value filled (ingest falls back to `task.language`). Strictly
   more informative; frontend header reads `language`, which matches.
2. **`transcript` rendering (9 tasks, cosmetic):** older pipeline versions
   joined some sentences with `". "` instead of the canonical `".\n"`
   segment join. Same words; assembled form is canonical going forward.
3. **Inline segment `enrichment` (6 tasks, contract normalization):**
   tasks processed by an older pipeline carry translations inline in
   `task.transcript_segments`. The flipped endpoint serves plain segments
   everywhere — one contract: translations come via the translate flow.
   Nothing is lost: the translations exist as chunk-scoped enrichments in
   the knowledge layer and in the task's `translation_results` cache, so
   the next Translate action is served from cache with no AI call.
