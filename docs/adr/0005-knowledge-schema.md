# ADR-0005: Knowledge Schema Implementation (Step 2a)

- Status: Accepted
- Date: 2026-07-28
- Context: Implements the frozen domain model ([docs/domain-model.md](../domain-model.md), ADR-0004) as persistence. Records implementation-level decisions only; the design contract is ADR-0004 and is not modified here.

## Decision

**Tables** (same database as tasks): `documents`, `knowledge_chunks`,
`enrichments` — each `(id PK, schema_version, payload)` with query keys as
columns: `knowledge_chunks(document_id, ordinal)` + index,
`enrichments(scope, owner_id, type)` + index.

**Key-columns vs payload split.** Only values the store actually filters or
sorts on are columns; everything else stays in the opaque payload owned by
the per-aggregate `*_models.py` serializers. This preserves the
"no business logic in SQL" rule while keeping lookups indexed.

**No FOREIGN KEY constraints.** Consistency is enforced by store methods,
not the database: `save_chunks` runs the frozen cascade (delete the
document's chunks + their chunk-scoped enrichments, insert the new set) in
ONE transaction, making re-processing atomic. Rationale: FK enforcement
would couple the tables' lifecycles to SQL-level rules while the domain
rules (replace-set semantics, scope-dependent cascade) live in the domain —
and opaque-payload tables gain little from relational constraints.

**Sibling interfaces.** `DocumentStore` (`save`/`load`) and
`KnowledgeStore` (`save_chunks`/`load_chunks`/`save_enrichment`/
`load_enrichments`) mirror `TaskStore`'s contract. Composition-root
factories `default_document_store()` / `default_knowledge_store()` sit in
`storage/__init__.py` next to the task factory. `load_enrichments` orders
newest-first by `rowid` (insertion order) rather than a payload field.

**Database rename.** `data/tasks.db` → `data/videobrain.db` (the file now
holds four aggregates, per approved storage-architecture.md). `ensure_db_path()`
in `sqlite_store.py` performs a one-time `os.replace` migration when the
legacy file exists and the new one doesn't; if both exist, the new path
wins and the legacy file is left untouched. All three SQLite stores call it
at init. `settings.tasks_db_path` default updated; explicit `.env` override
still wins.

**Task link.** `Task.document_id` (nullable), `TASK_SCHEMA_VERSION = 2`.
v0/v1 records deserialize with `document_id=None`.

## Alternatives considered

- **FK constraints with ON DELETE CASCADE** — rejected: pushes domain
  lifecycle rules into SQL; the scope-dependent cascade (chunk-scoped dies,
  document-scoped survives) is a domain rule and belongs in the store.
- **`created_at` as a sortable column on enrichments** — rejected for now:
  `rowid` matches insertion order without duplicating a payload field; a
  column can be added when time-range queries arrive.
- **Separate JSON backends for documents/knowledge** — rejected: the
  knowledge layer is new with no legacy format to stay compatible with;
  SQLite-only keeps one backend to maintain.

## Consequences

- Zero behavioral change to the running app: no routes, pipeline, or
  dual-write yet (steps 2b/2c). The new layer is exercised only by tests.
- The real database was migrated: `data/videobrain.db` contains all task
  records plus the three new (empty) tables.
- Step 2b (dual-write) now has everything it needs: models, stores with
  cascade semantics, composition-root factories, and the `document_id`
  link on Task.
