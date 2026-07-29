# ADR-0002: Phase 1 Critical Security Fixes (C1, C2, C4, C5)

- Status: Accepted
- Date: 2026-07-28
- Context: Remaining critical issues from the Phase 1 roadmap, after the
  TaskStore abstraction (ADR-0001) and the `schema_version` amendment.

## Context

Four critical issues remained after C3:

- **C1** — `task_id` from URL paths was interpolated into storage paths
  without validation (path traversal: arbitrary file read via `load`,
  arbitrary write via the translate endpoint's `save`).
- **C2** — Uploads were read fully into memory, had no size limit, and the
  format was validated only after the file was already on disk.
- **C4** — CORS allowed any origin with credentials (an invalid combination
  browsers reject, signaling "allow everything" intent on an unauthenticated
  API), and `/videos/health/gemini` disclosed API key prefix and length.
- **C5** — The pipeline's `finally` cleanup deleted the transcript/summary
  files it had just saved, leaving dangling paths in task records — a data
  loss trap the moment anyone trusts those paths, and incompatible with the
  persistent-artifacts direction of the knowledge platform.

## Decision

- **C1: validate at the boundary, defend in depth.**
  `validate_task_id()` in `routes/video.py` accepts only canonical UUIDs
  (the format the app generates; all 66 existing task files conform) and is
  applied to both endpoints taking `task_id` from the URL. Independently,
  `JsonTaskStore` rejects ids outside a conservative charset
  (`^[A-Za-z0-9][A-Za-z0-9_-]*$`): `load` refuses safely (returns `None`),
  `save` raises `ValueError` loudly. The store never trusts its callers.
- **C2: stream, cap, validate early.**
  `save_uploaded_file` validates the extension against the input sources'
  supported sets *before* writing, streams in 1 MiB chunks (constant memory),
  enforces `settings.max_upload_size_mb` (new setting, default 2048), and
  deletes partial files on any failure. Rejections raise
  `UploadValidationError` carrying the HTTP status (422 type, 413 size);
  the route maps it accordingly.
- **C4: minimal trust surface.**
  CORS restricted to `http://localhost:8000` / `http://127.0.0.1:8000` with
  `allow_credentials=False` (matches the local single-user trust model; the
  UI is served same-origin anyway). Health endpoint responses no longer
  include `key_prefix`/`key_length`.
- **C5: artifacts persist.**
  Cleanup no longer receives `transcript_path`/`summary_path`. Task-owned
  temp files (uploads, extracted audio) are still removed; result artifacts
  are persistent and their stored paths are now real. Full retention policy
  (media files, TTLs) remains an explicit Phase 2 decision.

## Alternatives considered

- **C1: sanitize-only (strip separators) instead of UUID validation** —
  rejected: silent normalization hides bugs and still permits weird ids;
  strict format acceptance fails fast and matches reality (UUID4 only).
- **C2: rely on a reverse proxy / server limits** — rejected: the app must
  be safe when run directly with uvicorn, which is the documented setup.
- **C4: token authentication now** — deferred: the trust-model decision
  (local single-user vs multi-user) is a Phase 2 architectural question;
  C4 only removes the accidental exposure.

## Consequences

- Traversal into `data/tasks` is closed at two independent layers.
- Upload memory usage is constant regardless of file size; junk never
  reaches disk; clients get precise 413/422 errors instead of 500s.
- Cross-origin calls from arbitrary websites no longer succeed.
- Transcript/summary files accumulate on disk (by design); retention/TTL
  is scheduled as Phase 2 debt alongside task retention.

## Compatibility

- API: same endpoints and shapes; only error codes for previously-500
  rejection cases are now 400/413/422 — these were failure paths, not
  contracts.
- Storage: unchanged schema (`schema_version` remains 1; no field changes).
- Frontend: unchanged behavior (same-origin, handles error details).
