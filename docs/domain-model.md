# Domain Model: Task / Document / KnowledgeChunk / Enrichment

Status: Agreed (design freeze before schema implementation)
ADR: [0004-domain-model.md](adr/0004-domain-model.md)
Builds on: [storage-architecture.md](storage-architecture.md), ADR-0001..0003

This document defines the domain model for the knowledge-platform
direction. It is the contract the database schema will implement — no
tables yet.

## Aggregates at a glance

```
Workspace/Corpus  (FUTURE — grouping layer, not this phase)
    │
Document          provenance & identity of one ingested content item
    │ 1──N
KnowledgeChunk    immutable, source-faithful content unit (segment-level)
    │
    │ referenced by ordinal range
    ▼
Passage           (FUTURE — derived retrieval unit, separate entity)

Enrichment        derived, versioned knowledge attached to a Document
                  or a KnowledgeChunk (registry of types)

Task              job log: what the system did / is doing
    N──1 Document
```

## Document

**Definition:** the persistent identity of one ingested content item — the
thing knowledge is extracted *from*. One upload, one URL, one import = one
Document.

**Owns provenance, not content and not processing state.** Content lives in
chunks; job state lives in tasks; derived knowledge lives in enrichments.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | stable identity |
| `source_type` | string | open set: `file_media`, `youtube`, `pdf`, `epub`, `webpage`, `ocr`, `note` |
| `origin_uri` | string, null | URL or original filename |
| `title` | string, null | metadata or user-provided; fallback: filename |
| `media_path` | string, null | local media for playback/seek; null for text-native sources |
| `primary_language` | string, null | language of the *original* content (ASR-detected or declared). Translations never appear here — they are enrichments |
| `language_source` | string, null | provenance of `primary_language`: `asr`, `declared`, or `manual` — explicit from the start for debugging, quality control, and mixed-source imports |
| `duration_seconds` | float, null | media only |
| `content_hash` | string, null | sha256 of source bytes when available → cross-source dedup |
| `created_at` | UTC timestamp | wall clock (NOT the monotonic `started_at` from Task) |

Deliberately absent: `status`, `transcript`, `summary`, `segments`.
Readiness is **derived**: a Document with chunks is ready; in-flight work
is visible through its jobs. One writer per fact.

### Lifecycle

1. **Ingested** — created when processing starts; the job references
   `document_id` from its first write. A failed import still leaves a
   provenance record that can be retried or deleted.
2. **Materialized** — a job completes and attaches chunks + document-level
   enrichments; the Document becomes retrievable.
3. **Enriched** — the enrichment pipeline attaches more knowledge over time
   (translations, concepts, mind maps; embeddings live on passages, not in
   enrichments). The Document row itself barely changes.
4. **Re-processed** — a new job against the same Document replaces its
   chunks as a set (e.g. better ASR model). History lives in jobs.
   **Chunk-scoped enrichments are deleted together with the chunks they
   reference** — they derive from a specific chunk identity and never
   outlive it (same cascade rule as document deletion). Document-scoped
   enrichments survive until explicitly re-run; they may be temporarily
   stale, which `created_at`, `prompt_version`, and producer params make
   explicit — a re-run simply creates a newer enrichment.
5. **Archived/deleted** — retention policy (deferred decision): deleting a
   Document cascades to chunks, enrichments, embeddings, and media file.

## KnowledgeChunk

**Definition:** the smallest addressable unit of *source* content, with a
locator back into its origin. **Immutable after creation** — it is source
data, not a derived artifact.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `document_id` | FK → Document | cascade delete |
| `ordinal` | int | position within the document |
| `text` | string | the content |
| `start` / `end` | float, null | seconds; first-class columns because media seek is a core UI contract |
| `locator_type` | string, null | e.g. `page`, `chapter`, `dom_path`, `ocr_region` — validates how to read the payload |
| `locator_payload` | JSON, null | per-type position data: `{page: 3}`, `{chapter: 2, offset: ..}`, `{page: 1, box: [..]}` |

Today's `TranscriptSegment` maps to a KnowledgeChunk with `start`/`end`
set and no locator. Non-media sources set `locator_type`/`locator_payload`
and leave `start`/`end` null. Every locator type gets a documented payload
shape and validation when its source lands.

Per-chunk `enrichment` dicts (today's translation cache shape) do **not**
live on the chunk — derived data is always an Enrichment row.

## Passage (future entity, modeled now, implemented with embeddings)

**Definition:** a *derived* retrieval unit spanning a contiguous range of
chunks, produced by a chunking strategy. Separate entity — **not** a row in
the chunk table — because its lifecycle differs: it depends on chunking
strategy, tokenizer, and embedding model, and is rebuilt when any of those
change, while chunks are immutable.

Planned shape: `id`, `document_id`, `start_ordinal`, `end_ordinal`
(range over KnowledgeChunk), `text` (materialized), `strategy`,
`strategy_version`, `created_at`. Embeddings attach to passages
(`passage_embeddings(passage_id, model, vector BLOB)`), not to chunks.

## Enrichment

**Definition:** derived, versioned knowledge attached to a Document or a
KnowledgeChunk. Generalizes today's `translation_results` cache.

| Field | Notes |
|---|---|
| `id` | uuid |
| `scope` | `document` or `chunk` |
| `owner_id` | document_id or chunk_id, per scope |
| `type` | open set: `summary`, `chapters`, `translation`, `concepts`, `entities`, `mind_map`, `qa` |
| `params` | JSON: `{target_language, ai_profile, model}` — structured replacement for the stringly `"gemini_flash:russian"` key |
| `prompt_version` | int — bump invalidates old results without deleting them |
| `payload` | JSON — the result (see registry note) |
| `created_at` | UTC; "current" = latest per (owner, type, params) |

**Registry, not a JSON dump.** Each enrichment type is registered with:
input scope, producer (provider + prompt), params schema, and payload
schema. The store interface exposes enrichments by (owner, type, params) —
*where* a type's payload physically lives is a storage detail. Types with
large or query-heavy payloads (mind maps, QA sets, flashcards) may graduate
to specialized tables later without changing the public model or the API.

Summary and chapters are **document-scoped enrichments**, not Document
fields: they are AI-generated, profile-dependent, and re-runnable.

## Task

**Definition:** the job log — what the system did or is doing. Not content.

Keeps: `id`, `status`, `progress`, `error`, `timings`, ai-profile fields,
job params (`model_size`, target language), `started_at`.
Gains: `document_id` (nullable during transition).
Loses at read-flip (Phase 2 step 3): `transcript`, `transcript_segments`,
`chapters`, `summary`, `translation_results`.

Name stays `Task` for now; renaming to `Job` is a future cosmetic alias.

## Workspace / Corpus (future parent layer)

Eventually Documents need a grouping parent for multi-document search and
knowledge management (projects, topics, corpora). Not this phase. The model
anticipates it: Document gets a nullable `workspace_id` later (additive,
no rework of existing fields), and retrieval scopes become
workspace → documents → passages.

## Relationships

```
Task        N ──→ 1  Document
Document    1 ──→ N  KnowledgeChunk      (cascade delete)
Passage     N ──→ N  KnowledgeChunk      (via ordinal range, same document)
Enrichment  N ──→ 1  Document            (scope=document)
Enrichment  N ──→ 1  KnowledgeChunk      (scope=chunk)
Workspace   1 ──→ N  Document            (future)
```

The hub is the Document. Tasks are disposable history; chunks and
enrichments are the asset.

## Source extensibility (PDF, EPUB, web, OCR, notes)

Three mechanisms, zero schema changes per source:

1. **`source_type` + extractor strategy.** Every extractor produces the
   same bundle: Document metadata + ordered chunks + optional media file.
   (Generalizes the existing `InputSource` pattern.)
2. **`locator_type` / `locator_payload`** absorbs per-source position
   formats with validation per type.
3. **Null tolerance by design.** No duration for PDFs, no media_path for
   notes, no timestamps for web pages — absent data, not special cases.
   `content_hash` dedup works uniformly.

Acceptance test: importing a PDF requires one extractor, one `source_type`
value, one locator type. No migrations.

## Migration from the current Task model

- **Step 2a — tables + task link.** `documents`, `knowledge_chunks`,
  `enrichments` tables (same SQLite DB). `document_id` added to the Task
  payload; `TASK_SCHEMA_VERSION` → 2 (`task_from_dict` fills `None` for
  v0/v1).
- **Step 2b — dual-write.** On completion the pipeline also writes
  Document + chunks + summary/chapters as enrichments. Task payload keeps
  its content fields; API and frontend unchanged (shadow mode).
- **Step 2c — backfill.** Script over existing tasks: Document from
  `task.source`/`transcript_language`; chunks from `transcript_segments`;
  enrichments from `summary`/`chapters`/`translation_results` (stringly
  cache keys parsed once, here, into structured params); `document_id` set
  on each task.
- **Step 3 (separate approval)** — flip reads: the status endpoint
  assembles its unchanged response shape from Document + chunks +
  enrichments. Task payload slims to job state.

Each step is independently shippable and reversible; the API contract never
breaks.
