# Storage Architecture

How persistence is organized today, and how it extends to the knowledge
platform (`Document`, `KnowledgeChunk`, `Enrichment`) without rewrites.

## Current state (after ADR-0003)

```
routes / services                ← application layer (backend-agnostic)
    │
    ▼
TaskManager                      ← in-memory cache + lock discipline
    │
    ▼  implements
TaskStore (ABC)                  ← save(task) atomic · load(id) → Task | None
    │
    ├── JsonTaskStore            ← data/tasks/{id}.json (default, atomic tmp+rename)
    └── SqliteTaskStore          ← data/tasks.db, tasks(id, schema_version, payload)
```

Conventions every backend honors:

- **Opaque payloads.** Stores serialize/deserialize via functions owned by a
  `models` module (`task_to_dict` / `task_from_dict`). SQL and filesystems
  never interpret record content; business logic never appears in storage
  code.
- **Atomic `save`.** JSON: temp file + fsync + `os.replace`. SQLite:
  single-statement upsert in one transaction.
- **`load` → `None`** for missing or unreadable records; invalid ids are
  rejected (`is_valid_task_id`): `load` refuses quietly, `save` raises.
- **`schema_version`** stored with every record (and as a queryable column
  in SQLite) so migrations branch on an explicit marker.
- **Composition-root selection.** Exactly one place (`_default_store()` in
  `task_manager.py`) reads `settings.task_store_backend` and constructs the
  backend. The rest of the app cannot tell which backend is active.

## How this extends to DocumentStore / KnowledgeStore

The pattern replicates per aggregate — **sibling interfaces, not a generic
repository** (aggregates have different query shapes):

```
DocumentStore (ABC)              ← save(document) · load(id) · (later: list/query)
KnowledgeStore (ABC)             ← save_chunks(doc_id, chunks) · chunks_of(doc_id)
                                   · (later: search, nearest_neighbors)
```

1. **New model modules own their schemas.**
   `storage/document_models.py`, `storage/chunk_models.py` with
   `*_to_dict` / `*_from_dict` pairs and their own `schema_version`.
   Serialization stays out of SQL, exactly as with tasks.

2. **One database, new tables.**
   `SqliteDocumentStore` / `SqliteKnowledgeStore` reuse the same
   `data/tasks.db` file (rename to `data/videobrain.db` at that point) with
   new tables: `documents(id, schema_version, payload)`,
   `chunks(id, document_id, ordinal, schema_version, payload)`.
   Because payloads are opaque, adding FTS5 or embedding columns later is an
   `ALTER TABLE` plus a backfill — not a migration of existing data.

3. **Composition root grows one branch per aggregate.**
   `_default_document_store()` next to `_default_store()`. The application
   layer keeps talking to interfaces; tests keep injecting temp-backed
   stores.

4. **Enrichment generalizes the existing cache.**
   Today's `translation_results` (keyed `"profile:language"`) becomes an
   `enrichments(chunk_id, type, params_json, prompt_version, payload)`
   table behind the `KnowledgeStore` — same idempotency idea, structured
   keys instead of stringly-typed ones.

5. **Migration discipline repeats.**
   Each new aggregate ships with: versioned schema, an import/backfill
   script (like `storage/migration.py`), dual-write during transition, and
   the old path kept working until reads flip.

## Explicitly not planned

- No vector database, no ORM, no connection pooling, no generic `Store[T]`.
  Each is a deliberate deferral with a known trigger: relational complexity
  → ORM; semantic search at scale → sqlite-vec or external index; pooling →
  measured connection overhead.
