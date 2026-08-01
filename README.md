# VideoBrain

An AI-powered media processor that converts audio and video into transcriptions, summaries, chapters, and translations — and stores the results as a **persistent, queryable knowledge layer** rather than throwaway job output.

## 🎯 Features

- **Primary Input**: Upload local audio/video files (MP3, WAV, M4A, MP4, MKV, AVI, etc.)
- **Optional Input**: YouTube URLs (legacy endpoint)
- **Transcription**: fast CPU transcription using faster-whisper (chunked for long media)
- **Summarization & Chapters**: Google Gemini or OpenRouter, with timestamp-accurate chapter navigation
- **Translation**: on-demand per-segment translation, cached per profile/language
- **Knowledge Layer**: every processed item becomes a persistent `Document` with immutable content chunks and versioned enrichments — the foundation for semantic search and an AI assistant

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- ffmpeg (required for video files and long-audio chunking)
- Google Gemini API key and/or OpenRouter API key

### Setup

1. **Create virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env`** (see [Configuration](#️-configuration) for all options):
   ```
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

4. **Start the server**:
   ```bash
   uvicorn backend.app:app --reload --port 8000
   ```

5. **Open in browser**: `http://localhost:8000`

## 🏗️ Architecture

VideoBrain is built around a small domain model. Full details: [docs/domain-model.md](docs/domain-model.md).

### Domain Model

| Aggregate | Role |
|---|---|
| `Document` | Persistent identity & provenance of one ingested item (file, YouTube, future: PDF/web/OCR). Owns no content and no job state. |
| `KnowledgeChunk` | Immutable, source-faithful content unit (a transcript segment today; a PDF block tomorrow), with a locator back into the source. |
| `Enrichment` | Derived, versioned knowledge attached to a Document or chunk: summaries, chapters, translations. A registry, not a JSON dump. |
| `Task` | **Job record** — status, progress, timings, errors. Also retains legacy content fields as the **rollback layer** for reads. |

### Storage

Persistence lives behind sibling interfaces in `backend/services/storage/` — the application never knows which backend is active:

- `TaskStore` — task/job records. Backends: **JSON files** (default) or **SQLite** (`TASK_STORE_BACKEND`).
- `DocumentStore` — documents (SQLite).
- `KnowledgeStore` — chunks + enrichments (SQLite, transactional replace-set with cascade rules).

Conventions: opaque serialized payloads (no business logic in SQL), atomic writes, `schema_version` on every record. Details: [docs/storage-architecture.md](docs/storage-architecture.md).

### Processing Pipeline

```
upload → validate + stream + sha256 → audio extraction (ffmpeg)
       → Whisper transcription (chunked >15 min)
       → AI summary + chapters (Gemini / OpenRouter)
       → task result persisted (job state + rollback copy)
       → shadow ingest → Document + chunks + enrichments  (best-effort, logged)
read:  GET /videos/status/{id} → knowledge layer via read adapter
       (automatic fallback to task record; KNOWLEDGE_READ_ENABLED=false reverts globally)
```

Identity is content-addressed: the same source bytes always map to the same `Document` (uuid5 of the file's sha256), so re-processing rebuilds instead of duplicating.

## ⚙️ Configuration

Environment variables (`.env`):

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | — | Gemini API key (required for `gemini_*` profiles) |
| `OPENROUTER_API_KEY` | — | OpenRouter key (required for `openrouter_default` profile) |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model used by the OpenRouter profile |
| `TASK_STORE_BACKEND` | `json` | Task persistence: `json` (files in `data/tasks/`) or `sqlite` |
| `TASKS_DB_PATH` | `data/videobrain.db` | SQLite database file (tasks + knowledge tables) |
| `KNOWLEDGE_READ_ENABLED` | `true` | Read-flip switch: serve status responses from the knowledge layer. `false` = instant global rollback to task records |
| `MAX_UPLOAD_SIZE_MB` | `2048` | Upload size cap (413 beyond this) |

## 🛠️ Operations

```bash
# Import legacy JSON task files into SQLite (idempotent)
python -m backend.services.storage.migration

# Backfill knowledge layer from existing tasks + repair failed shadow writes
python -m backend.services.storage.backfill --dry-run   # report only, zero writes
python -m backend.services.storage.backfill             # apply
```

Shadow-write events are logged to `data/logs/knowledge_shadow.log`. Full operator reference: [docs/operations.md](docs/operations.md).

## 🎬 Usage

### Web UI
1. Open `http://localhost:8000`
2. Upload a file (or paste a YouTube URL), pick an AI profile, click Process
3. Navigate by chapters/segments, translate on demand

### API (async pattern)

```bash
# 1. Submit → 202 Accepted with task_id
curl -X POST "http://localhost:8000/videos/process-file" \
  -F "file=@audio.mp3" -F "model_size=small" -F "ai_profile=gemini_flash"

# 2. Poll until completed
curl "http://localhost:8000/videos/status/<task_id>"

# 3. Translate on demand (cached per profile+language)
curl -X POST "http://localhost:8000/videos/status/<task_id>/translate" \
  -H "Content-Type: application/json" -d '{"target_language":"ru"}'
```

Full examples in cURL/Python/JavaScript: [API_EXAMPLES.md](API_EXAMPLES.md). Interactive docs: `http://localhost:8000/docs`.

### API (document features)

After processing is complete, use `document_id` from `/videos/status/{task_id}` to work with persistent document features:

- `POST /documents/{document_id}/chat/conversations` — create a document-scoped chat
- `GET /documents/{document_id}/chat/conversations` — list chats for a document
- `GET /documents/{document_id}/chat/conversations/{conversation_id}/messages` — list message history
- `POST /documents/{document_id}/chat/conversations/{conversation_id}/messages` — ask a question (context from Knowledge Layer)
- `POST /documents/{document_id}/notes` / `GET /documents/{document_id}/notes` / `GET|PUT|DELETE /documents/{document_id}/notes/{note_id}`
- `POST /documents/{document_id}/highlights` / `GET /documents/{document_id}/highlights` / `GET|PUT|DELETE /documents/{document_id}/highlights/{highlight_id}`
- `GET /documents/{document_id}/search?q=...` — search transcript, translations, and notes
- `GET /documents/{document_id}/knowledge-graph` — temporary graph stub (mock entities/relations/stats)

## 📁 Project Structure

```
VideoEssense/
├── backend/
│   ├── routes/video.py            # API endpoints (upload, status, translate, profiles, health)
│   ├── routes/document_features.py # Chat, notes, highlights, search, knowledge-graph APIs
│   ├── services/
│   │   ├── storage/               # TaskStore/DocumentStore/KnowledgeStore + JSON/SQLite backends
│   │   │                          #   + interaction_store for chat/notes/highlights
│   │   │                          #   + migration.py + backfill.py
│   │   ├── knowledge_ingest_service.py  # shadow writer (task output → knowledge layer)
│   │   ├── knowledge_read_service.py    # read adapter (knowledge → legacy response shape)
│   │   ├── document_features_service.py # document-scoped business services
│   │   ├── transcriber.py         # faster-whisper (chunked)
│   │   ├── ai_provider.py         # provider registry, profiles, JSON parsing
│   │   ├── google_provider.py / openrouter_provider.py
│   │   ├── transcript_enrichment_service.py  # batched translation
│   │   ├── input_sources/         # file / YouTube input strategies
│   │   ├── task_manager.py        # job registry (cache + lock discipline)
│   │   └── file_handler.py / cleanup_service.py / downloader.py
│   ├── config/                    # settings, AI token limits
│   ├── schemas/video.py           # API models
│   └── app.py
├── frontend/index.html            # built-in web UI
├── docs/                          # domain model, storage architecture, operations, ADRs
├── data/                          # tasks, videobrain.db, transcripts, summaries, logs
├── test_*.py                      # 8 test suites (see below)
└── requirements.txt
```

## 🔧 Development

### Test Suites

| Suite | Covers |
|---|---|
| `test_refactoring.py` | imports, input-source factory, routes registered |
| `test_task_store.py` | TaskStore contract, atomic JSON writes, legacy file compat |
| `test_sqlite_task_store.py` | SQLite backend, migration import, backend selection |
| `test_knowledge_stores.py` | Document/chunk/enrichment stores, cascade rules, schema v2 |
| `test_security_fixes.py` | task_id validation, upload limits, CORS, health endpoint |
| `test_shadow_ingest.py` | dual-write, idempotency, failure isolation, translation shadow |
| `test_backfill.py` | backfill eligibility, repair, dry-run, per-task isolation |
| `test_read_flip.py` | read adapter equivalence, fallbacks, kill switch |

Run any suite: `python test_<name>.py` (on Windows consoles, prefix `PYTHONIOENCODING=utf-8`).

### Design Documents & ADRs

- [docs/domain-model.md](docs/domain-model.md) — the frozen domain model
- [docs/storage-architecture.md](docs/storage-architecture.md) — storage patterns and extension path
- [docs/operations.md](docs/operations.md) — operator reference
- [docs/adr/](docs/adr/) — architectural decision records (index: [docs/README.md](docs/README.md))

Historical MVP-era docs (`REFACTORING_GUIDE.md`, `REFACTORING_COMPLETE.md`, `REPORT.md`) are kept for reference but superseded by the above.

## 📋 Supported Formats

**Audio**: MP3, WAV, M4A, FLAC, OGG, WMA
**Video**: MP4, MKV, AVI, MOV, FLV, WEBM, M4V

## 📚 Notes

- If `GOOGLE_API_KEY` is missing, Gemini profiles are unavailable (422 with a clear message); use OpenRouter or add the key.
- For YouTube URLs, an optional `cookies.txt` in the project root supports authenticated downloads.
- ffmpeg must be on PATH (Windows: `winget install ffmpeg`).
