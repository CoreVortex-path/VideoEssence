# Documentation Index

## Design Documents

- [domain-model.md](domain-model.md) — the frozen domain model: Document,
  KnowledgeChunk, Enrichment, Task; lifecycles, cascade rules, migration path.
- [storage-architecture.md](storage-architecture.md) — storage conventions
  (opaque payloads, atomic writes, composition root) and how the pattern
  extends to future stores.
- [operations.md](operations.md) — operator reference: backends, migration,
  backfill/repair, rollback, observability, data layout.

## Architectural Decision Records

- [ADR-0001](adr/0001-task-store-abstraction.md) — TaskStore interface,
  atomic JSON writes, schema ownership in `storage/models.py`.
- [ADR-0002](adr/0002-phase1-critical-security-fixes.md) — task_id
  validation, upload hardening, CORS lockdown, artifact retention.
- [ADR-0003](adr/0003-sqlite-task-store.md) — SQLite task backend,
  composition-root backend selection, JSON→SQLite migration.
- [ADR-0004](adr/0004-domain-model.md) — the domain model freeze:
  aggregates, locator, primary_language, enrichment registry, Workspace deferral.
- [ADR-0005](adr/0005-knowledge-schema.md) — knowledge tables, key-columns
  vs payload split, transactional cascade, DB rename to `videobrain.db`.
- [ADR-0006](adr/0006-shadow-dual-write.md) — shadow dual-write: source of
  truth, best-effort failures, content-addressed (uuid5) identity.
- [ADR-0007](adr/0007-backfill-orchestration.md) — backfill as pure
  orchestration over the ingest service; eligibility, repair, dry-run.
- [ADR-0008](adr/0008-read-flip.md) — status endpoint served from the
  knowledge layer; adapter contract, rollback layers, accepted differences.
