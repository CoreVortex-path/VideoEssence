# Architecture Overview — VideoEssence Backend

> **Scope:** MVP Feature Complete state.  
> **Last updated:** 2026-08-01

---

## 1. Project tree

```
VideoEssence/
├── backend/
│   ├── app.py                              # FastAPI entry point, CORS, router wiring
│   ├── config/
│   │   ├── ai_token_limits.py              # Per-model max-token caps
│   │   └── settings.py                     # Paths, env vars (Settings dataclass)
│   ├── routes/
│   │   ├── video.py                        # /videos/* — upload, status, translate
│   │   └── document_features.py            # /documents/* — chat, notes, highlights, search, graph
│   ├── schemas/
│   │   ├── video.py                        # TranscriptSegment, Chapter (Pydantic)
│   │   └── document_features.py            # All request/response DTOs for document features
│   ├── services/
│   │   ├── ai_provider.py                  # BaseAIProvider ABC + get_ai_provider factory
│   │   ├── ai_text_generator.py            # AITextGenerator port (ABC — the only interface ChatService needs)
│   │   ├── cleanup_service.py              # Deletes orphaned audio / transcript files
│   │   ├── document_features_service.py    # ChatService, NotesService, HighlightsService, SearchService, KnowledgeGraphService
│   │   ├── downloader.py                   # yt-dlp wrapper
│   │   ├── file_handler.py                 # Upload validation and save
│   │   ├── google_provider.py              # Gemini Flash / Pro implementation
│   │   ├── input_processor.py              # InputSource factory (file vs YouTube)
│   │   ├── input_sources/
│   │   │   ├── base.py                     # InputSource ABC
│   │   │   ├── file_source.py              # Local file audio extraction
│   │   │   └── youtube_source.py           # YouTube download + extraction
│   │   ├── knowledge_ingest_service.py     # Shadow-writes Task output → Knowledge Layer (ADR-0006)
│   │   ├── knowledge_read_service.py       # Reads Knowledge Layer → legacy status payload (ADR-0008)
│   │   ├── openrouter_provider.py          # OpenRouter multi-model implementation
│   │   ├── storage/
│   │   │   ├── __init__.py                 # Composition roots (default_*_store), public re-exports
│   │   │   ├── backfill.py                 # One-time migration: tasks → knowledge layer (ADR-0007)
│   │   │   ├── base.py                     # TaskStore ABC
│   │   │   ├── document_models.py          # Document dataclass + serde
│   │   │   ├── document_store.py           # DocumentStore ABC + SqliteDocumentStore
│   │   │   ├── interaction_models.py       # ChatConversation, ChatMessage, Note, Highlight dataclasses + serde
│   │   │   ├── interaction_store.py        # ChatStore / NoteStore / HighlightStore ABCs + SqliteInteractionStore
│   │   │   ├── json_store.py               # JsonTaskStore (legacy, kept for ADR-0001)
│   │   │   ├── knowledge_models.py         # KnowledgeChunk, Enrichment dataclasses + serde
│   │   │   ├── knowledge_store.py          # KnowledgeStore ABC + SqliteKnowledgeStore
│   │   │   ├── migration.py                # DB file rename shim (tasks.db → videobrain.db)
│   │   │   ├── models.py                   # Task dataclass, is_valid_task_id, serde
│   │   │   └── sqlite_store.py             # SqliteTaskStore + ensure_db_path helper
│   │   ├── task_manager.py                 # In-memory task registry (singleton)
│   │   ├── transcriber.py                  # faster-whisper wrapper
│   │   └── transcript_enrichment_service.py # Translation enrichment pipeline
│   └── utils/
│       └── file_utils.py                   # Save transcript / summary to disk
├── docs/
│   ├── adr/                                # Architecture Decision Records (0001–0008)
│   ├── domain-model.md
│   ├── storage-architecture.md
│   └── architecture-overview.md            # ← this file
├── frontend/
│   └── index.html                          # Single-page frontend (served statically)
├── requirements.txt
└── test_*.py                               # 8 test suites (unit + integration)
```

---

## 2. Services

### 2.1 Processing pipeline services

| Service | File | Responsibility |
|---|---|---|
| `TaskManager` | `task_manager.py` | In-memory registry of all processing jobs. Singleton. Source of truth for job state (pending / processing / completed / failed). |
| `Transcriber` | `transcriber.py` | Wraps `faster-whisper`. Returns `(transcript, segments, language)`. |
| `TranscriptEnrichmentService` | `transcript_enrichment_service.py` | Calls AI provider to translate each segment; persists result as Enrichments. |
| `KnowledgeIngestService` | `knowledge_ingest_service.py` | Shadow-writes completed task output to the Knowledge Layer: creates `Document`, `KnowledgeChunk`s, and `Enrichment`s (summary, chapters, translations). Never raises — keeps the pipeline safe. |
| `KnowledgeReadService` | `knowledge_read_service.py` | Reads the Knowledge Layer and assembles either the legacy status payload (`assemble_status`) or the chat context (`get_document_context`). Never raises. |

### 2.2 AI provider layer

| Component | File | Responsibility |
|---|---|---|
| `AITextGenerator` | `ai_text_generator.py` | **Port interface (ABC).** Single method: `generate_text(prompt, max_tokens)`. The only AI capability `ChatService` depends on. |
| `BaseAIProvider` | `ai_provider.py` | Extends `AITextGenerator`. Adds `summarize`, `summarize_with_chapters`, `translate_segments`, `parse_ai_json`. Concrete providers inherit this. |
| `GoogleProvider` | `google_provider.py` | Gemini Flash and Gemini Pro via Google AI SDK. |
| `OpenRouterProvider` | `openrouter_provider.py` | Any model available on OpenRouter (Claude, GPT-4o, Mixtral, …). |
| `get_ai_provider(profile_id)` | `ai_provider.py` | Factory. Returns `(AIProfile, BaseAIProvider)` for a given profile key. Used by the pipeline routes; injected as a `ProviderFactory` callable into `ChatService`. |

### 2.3 Document-feature services

All five services live in `document_features_service.py` and depend only on store interfaces and `KnowledgeReadService`.

| Service | Store interfaces consumed | Responsibility |
|---|---|---|
| `ChatService` | `DocumentStore`, `ChatStore`, `KnowledgeReadService`, `ProviderFactory` | Create conversations, persist messages, build prompt from Knowledge Layer, call AI, return (user, assistant) message pair. |
| `NotesService` | `DocumentStore`, `NoteStore`, `KnowledgeStore` | Full CRUD for user notes. Validates `chunk_id` belongs to the document when provided. |
| `HighlightsService` | `DocumentStore`, `HighlightStore`, `KnowledgeStore` | Full CRUD for text highlights. Always validates `chunk_id`. |
| `SearchService` | `DocumentStore`, `KnowledgeStore`, `NoteStore` | Keyword search across transcript chunks, translation enrichments, and notes. Returns ranked `SearchHit` list. |
| `KnowledgeGraphService` | — | **Stub.** Returns mock entities and relations. Architecture is ready for a real NLP implementation. |

### 2.4 Storage layer

One SQLite database (`data/videobrain.db`). Four store pairs (ABC + implementation):

| ABC | SQLite impl | Tables |
|---|---|---|
| `TaskStore` | `SqliteTaskStore` | `tasks` |
| `DocumentStore` | `SqliteDocumentStore` | `documents` |
| `KnowledgeStore` | `SqliteKnowledgeStore` | `knowledge_chunks`, `enrichments` |
| `ChatStore` + `NoteStore` + `HighlightStore` (combined as `InteractionStore`) | `SqliteInteractionStore` | `chat_conversations`, `chat_messages`, `notes`, `highlights` |

Composition roots (`default_*_store()`) in `storage/__init__.py` are the only place that knows the DB path.

---

## 3. All API endpoints

### Video pipeline — prefix `/videos`

| Method | Path | Description |
|---|---|---|
| `POST` | `/videos/process` | Upload a file (`multipart/form-data`) or submit a YouTube URL. Creates a `Task`, starts background processing. Returns `task_id`. |
| `GET` | `/videos/{task_id}/status` | Poll task status. When the Knowledge Layer has a shadow copy, returns enriched payload including `document_id`, `transcript`, `summary`, `chapters`, `language`. Falls back to raw task record. |
| `POST` | `/videos/{task_id}/translate` | Translate transcript to a target language using an AI profile. Persists per-chunk translation Enrichments. |
| `GET` | `/videos/tasks` | List all tasks (most recent first). |
| `GET` | `/videos/ai-profiles` | List all configured AI profiles and their capabilities. |
| `DELETE` | `/videos/{task_id}` | Delete a task and its associated files. |

### Document features — no prefix

#### Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/documents/{document_id}/chat/conversations` | Create a new conversation scoped to this document. |
| `GET` | `/documents/{document_id}/chat/conversations` | List all conversations for the document. |
| `GET` | `/documents/{document_id}/chat/conversations/{conversation_id}/messages` | Retrieve message history. |
| `POST` | `/documents/{document_id}/chat/conversations/{conversation_id}/messages` | Send a user message; returns `(user_message, assistant_message)`. Uses Knowledge Layer context, not raw transcript. |

#### Notes

| Method | Path | Description |
|---|---|---|
| `POST` | `/documents/{document_id}/notes` | Create a note. Optional: `chunk_id`, `selected_text`. |
| `GET` | `/documents/{document_id}/notes` | List all notes for the document. |
| `GET` | `/documents/{document_id}/notes/{note_id}` | Get a single note. |
| `PUT` | `/documents/{document_id}/notes/{note_id}` | Update text, chunk_id, selected_text. |
| `DELETE` | `/documents/{document_id}/notes/{note_id}` | Delete a note. |

#### Highlights

| Method | Path | Description |
|---|---|---|
| `POST` | `/documents/{document_id}/highlights` | Create a highlight. Requires `chunk_id` (validated), `start_offset`, `end_offset`, `text`, `color`. |
| `GET` | `/documents/{document_id}/highlights` | List all highlights for the document. |
| `GET` | `/documents/{document_id}/highlights/{highlight_id}` | Get a single highlight. |
| `PUT` | `/documents/{document_id}/highlights/{highlight_id}` | Update all highlight fields. |
| `DELETE` | `/documents/{document_id}/highlights/{highlight_id}` | Delete a highlight. |

#### Search

| Method | Path | Description |
|---|---|---|
| `GET` | `/documents/{document_id}/search` | Query params: `q` (required), `transcript=true`, `translation=true`, `notes=true`. Returns list of `{ source, chunk_id, matched_text, position }`. |

#### Knowledge Graph (stub)

| Method | Path | Description |
|---|---|---|
| `GET` | `/documents/{document_id}/knowledge-graph` | Returns mock entities, relations, and stats. Ready for real NLP implementation. |

---

## 4. Dependencies between components

```
HTTP Request
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Routes  (video.py / document_features.py)              │
│  • _handle_feature_errors() context manager             │
│  • Lazy singleton service factories                     │
└─────────────────────┬───────────────────────────────────┘
                      │ calls
        ┌─────────────┼──────────────────────────────────┐
        ▼             ▼                                  ▼
┌─────────────┐ ┌───────────────────┐ ┌────────────────────────┐
│ TaskManager │ │ KnowledgeIngest   │ │ Document-feature       │
│ (in-memory) │ │ Service           │ │ Services               │
└─────────────┘ └────────┬──────────┘ │ (Chat / Notes /        │
                         │            │  Highlights / Search /  │
                         │            │  KnowledgeGraph)        │
                         │            └────────────┬───────────┘
                         │                         │
                         ▼                         ▼
                ┌─────────────────────────────────────────┐
                │         Storage Interfaces (ABCs)        │
                │  DocumentStore  KnowledgeStore           │
                │  ChatStore  NoteStore  HighlightStore    │
                └─────────────────────┬───────────────────┘
                                      │ implemented by
                                      ▼
                          ┌────────────────────────┐
                          │  SQLite (videobrain.db) │
                          └────────────────────────┘

                ┌─────────────────────────────────────────┐
                │         AI Provider Layer                │
                │  AITextGenerator (port ABC)              │
                │    ▲                                     │
                │  BaseAIProvider (ABC)                    │
                │    ├── GoogleProvider                    │
                │    └── OpenRouterProvider                │
                └─────────────────────────────────────────┘
                    ▲ injected via ProviderFactory
                    │
                ChatService
```

**Dependency rules (Clean Architecture):**

- Routes depend on service classes and store ABCs — never on SQLite directly.
- Services depend on store ABCs — never on `SqliteXxx` implementations.
- `SqliteInteractionStore` has no knowledge of any AI provider.
- `ChatService` depends on `AITextGenerator` (port) — not on `GoogleProvider` or `get_ai_provider` (injected as `ProviderFactory`).
- The video pipeline (`routes/video.py`) and the document-feature pipeline (`routes/document_features.py`) are **fully independent**; they share stores but never call each other.

---

## 5. Data flow: from video upload to AI Chat

```
1. Upload
   POST /videos/process  (file or YouTube URL)
        │
        ├─► TaskManager.create(task_id)           [in-memory]
        └─► BackgroundTasks.add(_process_file_with_ai_profile)

2. Processing (background thread)
   ├─► InputSource.extract_audio(...)
   ├─► Transcriber.transcribe_with_segments(audio)
   │       └─► segments: [{start, end, text}, …]
   ├─► get_ai_provider(ai_profile_id)
   ├─► provider.summarize_with_chapters(segments)
   │       └─► {summary, chapters, language}
   ├─► TaskManager.update(task_id, transcript, summary, …)
   └─► KnowledgeIngestService.shadow_write_task(task)
           ├─► SqliteDocumentStore.upsert(Document)
           ├─► SqliteKnowledgeStore.replace_chunks([KnowledgeChunk, …])
           └─► SqliteKnowledgeStore.upsert_enrichments([summary_enr, chapters_enr])

3. Status poll
   GET /videos/{task_id}/status
        │
        └─► KnowledgeReadService.assemble_status(task)
                ├─► SqliteDocumentStore.load(document_id)
                ├─► SqliteKnowledgeStore.load_chunks(document_id)
                ├─► SqliteKnowledgeStore.load_enrichments(type="summary")
                └─► returns full payload including document_id

4. Translation (optional)
   POST /videos/{task_id}/translate
        │
        └─► TranscriptEnrichmentService.translate(task, target_language)
                ├─► provider.translate_segments(chunks)
                └─► SqliteKnowledgeStore.upsert_enrichments([translation_enr per chunk])

5. Start Chat
   POST /documents/{document_id}/chat/conversations
        └─► ChatService.create_conversation(document_id)
                ├─► SqliteDocumentStore.load(document_id)   [verify existence]
                └─► SqliteInteractionStore.save_conversation(ChatConversation)

6. Send message
   POST /documents/{document_id}/chat/conversations/{id}/messages
        └─► ChatService.answer(document_id, conversation_id, message)
                ├─► SqliteInteractionStore.save_message(user_message)
                ├─► KnowledgeReadService.get_document_context(document_id)
                │       ├─► load Document (title, language)
                │       ├─► load KnowledgeChunks (ordered, text + timestamps)
                │       └─► load summary Enrichment
                ├─► _select_relevant_chunks(question, chunks)   [keyword overlap]
                ├─► _build_prompt(context, chunks, history)
                ├─► ProviderFactory(ai_profile) → AITextGenerator
                ├─► provider.generate_text(prompt)
                └─► SqliteInteractionStore.save_message(assistant_message)
```

**Key invariant:** `ChatService` never touches the raw transcript from `TaskManager`. It reads exclusively from the Knowledge Layer via `KnowledgeReadService`.

---

## 6. Extension points

### 6.1 Real RAG (Retrieval-Augmented Generation)

**What exists now:** `ChatService._select_relevant_chunks()` uses keyword overlap (TF-IDF-style word matching).

**Where to change:** Replace only this private method. The public API, the prompt builder, and all storage calls remain untouched.

**What to add:**
- An embedding store (e.g., `SqliteVecStore` with `sqlite-vec` or a separate Chroma/Qdrant instance).
- A new `EmbeddingStore` ABC alongside the existing store interfaces.
- `KnowledgeIngestService.shadow_write_embeddings()` that runs after `shadow_write_task()`.
- `ChatService.__init__` gains an optional `embedding_store: EmbeddingStore | None = None`; if present, it uses semantic search instead of keyword overlap.

The `AITextGenerator` port is already in place — no API change needed.

---

### 6.2 Real Knowledge Graph

**What exists now:** `KnowledgeGraphService.get_document_graph()` returns hard-coded mock data.

**Where to change:** Replace the method body with an NLP pipeline (spaCy, or an AI-extracted entity/relation list stored as Enrichments with `type="kg_entities"` / `type="kg_relations"`).

**Enrichment storage is already ready:** `KnowledgeStore.upsert_enrichments()` accepts any `type` string and `payload` dict — no schema change needed.

---

### 6.3 Flashcards

**What to add:**
1. `Flashcard` dataclass in `storage/interaction_models.py` (fields: `id`, `document_id`, `chunk_id`, `front`, `back`, `created_at`).
2. `FlashcardStore` ABC (4 methods: `save`, `load`, `list`, `delete`) in `interaction_store.py`.
3. Add the table to `SqliteInteractionStore._SCHEMA` and implement the 4 methods.
4. `FlashcardsService` in `document_features_service.py` — optionally auto-generates card pairs from chunk text via `AITextGenerator`.
5. 5 new routes in `document_features.py` under `/documents/{document_id}/flashcards`.

No existing files need structural changes.

---

### 6.4 Vocabulary

**What to add:** Same pattern as Flashcards — `VocabularyEntry` model, `VocabularyStore` ABC, SQLite table, `VocabularyService`, 5 routes. Vocabulary entries naturally reference `chunk_id` (the source sentence).

---

### 6.5 Semantic / Vector Search

**What to add:**
- Replace `SearchService._search_transcript()` with a vector similarity call when an `EmbeddingStore` is available (same optional-dependency injection pattern as RAG).
- The `SearchHit` model and all API contracts stay the same.

---

### 6.6 AI Assistant (multi-document / global)

**What to add:** A new `AssistantService` that is not scoped to a single `document_id`. It would use the same `AITextGenerator` port and a cross-document `EmbeddingStore`. New router prefix `/assistant`.

**What does not change:** All document-scoped services, Knowledge Layer, storage contracts.

---

## 7. Error handling

All domain exceptions are translated to HTTP responses by `_handle_feature_errors()` in `document_features.py`:

| Exception | HTTP status | Raised by |
|---|---|---|
| `FeatureNotFoundError` | 404 | Any service when document / note / highlight is missing |
| `FeatureValidationError` | 422 | Any service on bad input (empty text, bad offsets, wrong chunk_id) |
| `AIProviderConfigurationError` | 422 | `get_ai_provider` when the API key is missing or profile is unknown |
| `RuntimeError` | 500 | Unexpected AI or storage failures |
| `HTTPException(400)` | 400 | `_validate_id()` when a URL segment is not a valid ID format |

The catch order is intentional: `FeatureNotFoundError` extends `RuntimeError`, so it must be caught first.

---

## 8. Relevant ADRs

| ADR | Title | Impact |
|---|---|---|
| 0001 | Task store abstraction | `TaskStore` ABC decouples task persistence from storage implementation |
| 0003 | SQLite task store | `SqliteTaskStore` replaces JSON; single DB file |
| 0004 | Domain model | Separates Task (job) from Document (content) |
| 0005 | Knowledge schema | `KnowledgeChunk` + `Enrichment` as the canonical content model |
| 0006 | Shadow dual-write | `KnowledgeIngestService` writes to Knowledge Layer without breaking the pipeline |
| 0007 | Backfill orchestration | One-time migration of existing tasks to Knowledge Layer |
| 0008 | Read flip | `KnowledgeReadService` makes the status endpoint serve from Knowledge Layer |

---

## 9. Plan: extract `translation_results` into a separate API resource

Current state: translation data is returned inside `TaskStatusResponse.translation_results`, which makes the status payload heavier than necessary.

Planned migration (backward-compatible):

1. Add new endpoint:
   - `GET /documents/{document_id}/translations`
   - response: a dedicated translation DTO list/object (no task status fields).
2. Keep `translation_results` in `TaskStatusResponse` during transition (compat window).
3. Update frontend translation query to read only from `/documents/{document_id}/translations`.
4. Mark `TaskStatusResponse.translation_results` as deprecated in API docs.
5. Remove the deprecated field only after frontend and external clients are fully migrated.

Constraint: any future backend API change must be agreed before implementation.
