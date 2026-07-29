# ADR-0004: Domain Model for the Knowledge Platform

- Status: Accepted
- Date: 2026-07-28
- Context: Phase 2 domain design, agreed before any schema work. Full model:
  [docs/domain-model.md](../domain-model.md). Builds on ADR-0001..0003.

## Context

VideoBrain is evolving from a video-processing app into a personal knowledge
platform. The current `Task` record conflates job state with produced
content (transcript, segments, summary, translation cache), which blocks
persistent knowledge, multi-source ingestion, semantic retrieval, and safe
re-processing. The domain model had to be fixed *before* the persistence
model, so tables implement the domain rather than fossilize today's
conveniences.

## Decisions

1. **Four aggregates with strict ownership.**
   `Task` = job log (no content). `Document` = provenance/identity (no
   content, no job state). `KnowledgeChunk` = immutable source content.
   `Enrichment` = derived, versioned knowledge. One writer per fact;
   Document readiness is derived, not stored.

2. **Segments and passages are separate entities.**
   A `KnowledgeChunk` is immutable source data (segment-level). A `Passage`
   is a *derived* retrieval unit depending on chunking strategy, tokenizer,
   and embedding model — a different lifecycle, so it gets its own entity
   referencing a chunk ordinal range. Modeled now, implemented with
   embeddings. (Rejected: one chunk table with a `kind` discriminator —
   mixes immutable source data with rebuildable artifacts.)

3. **`locator_type` + `locator_payload`** on KnowledgeChunk instead of a
   bare JSON locator: extensible to any source while keeping per-type
   validation possible. Media sources keep first-class `start`/`end`
   columns (seek is a core UI contract).

4. **`primary_language` + `language_source`** on Document (not generic
   `language`): names the original content's language with explicit
   provenance (`asr` | `declared` | `manual`); translated text exists only
   as enrichment payloads. Provenance is one nullable column now instead
   of a retrofit onto a frozen field later.

5. **Enrichment is a registry, not a JSON dump.** Each type declares scope,
   producer, params schema, payload schema. Storage exposes enrichments by
   (owner, type, params); large/query-heavy types (mind maps, QA,
   flashcards) may graduate to specialized tables later without changing
   the public model. Summary and chapters are document-scoped enrichments,
   not Document fields. Stringly cache keys (`"profile:language"`) are
   replaced by structured `params` + `prompt_version`.

6. **Workspace/Corpus is anticipated, not built.** A future parent grouping
   Documents for multi-document search; lands as an additive nullable
   `workspace_id` later. Designing for it now would be speculative.

7. **Migration preserves the API contract at every step**: tables +
   `document_id` link → dual-write in shadow → backfill existing tasks →
   (separately approved) read-flip with unchanged response shapes.
   `TASK_SCHEMA_VERSION` bumps to 2; v0/v1 records load with
   `document_id=None`.

## Alternatives considered

- **Content fields stay on Task, Document links to them** — rejected:
  keeps job state and knowledge coupled; re-processing and retention become
  entangled with the job log.
- **Summary/chapters as Document columns** — rejected: they are
  profile-dependent, re-runnable AI outputs; versioning them requires the
  enrichment machinery anyway.
- **Generic `Store[T]` repository for all aggregates** — rejected (again,
  per ADR-0001 checkpoint): aggregates have different query shapes;
  sibling interfaces (`DocumentStore`, `KnowledgeStore`) mirror TaskStore's
  contract instead.
- **Fixed locator columns per source** — rejected: every new source would
  force a schema change; locator_type/payload keeps sources pluggable.

## Consequences

- Schema work (Phase 2 step 2a) has a frozen contract to implement:
  `documents`, `knowledge_chunks`, `enrichments` + `document_id` on tasks.
- **Cascade rules are part of the contract:** deleting a Document cascades
  to its chunks and enrichments; re-processing a Document (chunk set
  replacement) cascades to the chunk-scoped enrichments of the replaced
  chunks — derived data never outlives the chunk identity it came from.
  Document-scoped enrichments survive re-processing as explicitly stale
  (visible via `created_at`, `prompt_version`, producer params) until
  re-run.
- Embeddings are not enrichments: they live in the future
  `passage_embeddings` table attached to Passages. Documentation must not
  describe them as enrichment types.
- New sources (PDF, EPUB, web, OCR, notes) require: one extractor, one
  `source_type`, one locator type — zero migrations.
- Deferred decisions explicitly recorded: retention/TTL policy, Workspace
  layer, Passage implementation, enrichment types graduating to specialized
  tables, `Task`→`Job` rename.
