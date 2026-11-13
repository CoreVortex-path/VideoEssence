# Storage Architecture

How persistence is organized today (post ADR-0001–0008), and the
conventions that let it extend without rewrites.

## Current state

```
routes / services                  ← application layer (backend-agnostic)
    │
    ├── TaskManager                ← in-memory cache + lock discipline
    │       │
    │       ▼  implements
    │   TaskStore (ABC)            ← save(task) atomic · load(id) → Task | None
    │       ├── JsonTaskStore      ← data/tasks/{id}.json (default)
    │       └── SqliteTaskStore    ← data/videobrain.db, tasks(id, schema_version, payload)
    │
    ├── DocumentStore (ABC)        ← save(document) · load(id) · delete(id) · update(id, pinned=, title=)
    │       └── SqliteDocumentStore    ← data/videobrain.db, documents(id, schema_version, payload, pinned)
    │
    └── KnowledgeStore (ABC)       ← save_chunks / chunks_of / enrichments
            └── SqliteKnowledgeStore   ← data/videobrain.db,
                                         knowledge_chunks + enrichments tables
```

Three sibling interfaces, one per aggregate — deliberately **not** a
generic repository, because the aggregates have different query shapes.

- **Task records** are the only selectable backend: `TASK_STORE_BACKEND`
  chooses `json` (files, the default) or `sqlite`. Documents, chunks, and
  enrichments are **always SQLite** in `data/videobrain.db` — the same file
  the SQLite task backend uses, so a fully-SQLite install has one database.
  A legacy `data/tasks.db` is renamed to `videobrain.db` once, on first
  open.
- **Model modules own their schemas.** `storage/models.py` (Task, schema
  v2 — adds `document_id`), `storage/document_models.py` (Document, v2 —
  adds `pinned`; the matching `pinned` column is added by a lazy
  PRAGMA-checked migration in `SqliteDocumentStore`),
  `storage/knowledge_models.py` (KnowledgeChunk + Enrichment, v1). Each
  provides `*_to_dict` / `*_from_dict` pairs; serialization stays out of
  SQL.
- **Composition roots.** Exactly one place per aggregate constructs the
  backend: `task_manager._default_store()` for tasks (reads
  `settings.task_store_backend`), `default_document_store()` /
  `default_knowledge_store()` in `storage/__init__.py` for the knowledge
  layer. The application layer talks to interfaces only; tests inject
  temp-backed stores.

Conventions every backend honors:

- **Opaque payloads.** Stores serialize/deserialize via functions owned by
  a `models` module (`task_to_dict` / `task_from_dict`). SQL and
  filesystems never interpret record content; business logic never appears
  in storage code. Key columns (ids, `document_id`, `(scope, owner_id,
  type)`) exist only for lookup and cascade.
- **Atomic `save`.** JSON: temp file + fsync + `os.replace`. SQLite:
  single-statement upsert in one transaction. `save_chunks` replaces a
  document's whole chunk set transactionally and cascade-deletes the
  chunk-scoped enrichments of the replaced chunks.
- **Document delete cascade.** `DELETE /videos/documents/{id}` removes the
  task records (`TaskStore.delete`), knowledge chunks + chunk- and
  document-scoped enrichments (`KnowledgeStore.delete_document`), notes,
  highlights and chat conversations with messages
  (`InteractionStore.delete_document_data`), the document record, and the
  document's files under `data/` (media, transcripts, summaries,
  task-prefixed audio artifacts, `formula_images/<document_id>/`).
- **`load` → `None`** for missing or unreadable records; invalid ids are
  rejected (`is_valid_task_id`): `load` refuses quietly, `save` raises.
- **`schema_version`** stored with every record (and as a queryable column
  in SQLite) so migrations branch on an explicit marker.

## Enrichments as a generalized cache

The pre-migration `translation_results` cache (keyed `"profile:language"`)
is now the `enrichments` table behind the `KnowledgeStore` — structured
`(scope, owner_id, type, params)` keys instead of stringly-typed ones, with
`prompt_version` for invalidation. Summary and chapters are document-scoped
enrichments; translations are chunk-scoped. New knowledge types register a
type name, params schema, and payload schema — no schema change.

## How a new aggregate joins (discipline established by ADR-0005)

Each new aggregate ships with:

1. A model module owning its schema (`*_to_dict` / `*_from_dict`,
   `schema_version`).
2. A sibling store ABC plus its backend(s), wired through a composition
   root — never constructed inside the application layer.
3. A versioned import/backfill path (like `storage/migration.py` /
   `storage/backfill.py`), dual-write during transition, and the old read
   path kept working until reads flip.

Because payloads are opaque, adding query capability later (FTS5, embedding
columns for the future Passage entity) is an `ALTER TABLE` plus a backfill
— not a migration of existing data.

## Explicitly not planned

- No vector database, no ORM, no connection pooling, no generic `Store[T]`.
  Each is a deliberate deferral with a known trigger: relational complexity
  → ORM; semantic search at scale → sqlite-vec or external index; pooling →
  measured connection overhead.
