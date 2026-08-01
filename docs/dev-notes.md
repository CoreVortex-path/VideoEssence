# Dev Notes (рабочие заметки для навигации по коду)

Краткая шпаргалка по текущему состоянию. Обновлять при каждом изменении.
Официальная документация: `README.md`, `docs/` (domain-model, storage-architecture, operations), `docs/adr/0001-0008`.

## Архитектура (заморожена, ADR-0001–0008)

- Хранилища: `backend/services/storage/` — `TaskStore` (json/sqlite, флаг `TASK_STORE_BACKEND`), `DocumentStore`, `KnowledgeStore` (всегда SQLite `data/videobrain.db`).
- Knowledge layer: Document / KnowledgeChunk / Enrichment; Task — job record + rollback-слой.
- Pipeline: upload → `routes/video.py` → transcribe → summarize_with_chapters → `set_result` → shadow-write (`knowledge_ingest_service.py`). Чтение: `knowledge_read_service.py` с fallback, kill-switch `KNOWLEDGE_READ_ENABLED`.
- Операции: `python -m backend.services.storage.migration` / `.backfill [--dry-run]`.

## AI-провайдеры и токен-бюджеты

- `backend/config/ai_token_limits.py` — бюджеты; DEFAULT: SUMMARY_WITH_CHAPTERS=8192, ENRICHMENT_MIN/MAX=2048/8192.
- Gemini 2.5 thinking-токены расходуют тот же `max_output_tokens` → большие бюджеты обязательны.
- `transcript_enrichment_service.py`: MAX_BATCH_SIZE=20, оценка = (chars + n*600)/4 * 1.2 + 2048 (thinking headroom).
- `google_provider.py`: retry при 429 — до 2 попыток, если retryDelay ≤ 60с (дневная квота — fail fast).

## Frontend (`frontend/index.html`, одностраничник)

- Центральная колонка: видеоплеер (native `<video>` для файлов; YouTube iframe `embed/{id}?enablejsapi=1`, seek через postMessage) → Segments (кликабельные таймстемпы, per-segment expand-переводы, автопрокрутка за воспроизведением через `updatePlaybackHighlight` + `lastActiveSegmentIndex`).
- Левая slide-панель (📑): Chapters. Класс `body.chapters-open`, push-layout `margin-left:450px`, <768px — overlay.
- Правая slide-панель (🌐): Transcript Original|Translation. Класс `body.panel-open`, push `margin-right:450px`. Полный исходный текст (`fullTranscriptState`) и полный перевод (`translatedFullTextState`) живут только здесь.
- Закрытие панелей: toggle, X, Escape, backdrop (backdrop виден только на мобильных).
- Перевод: кнопка Translate в правой панели → `POST /videos/status/{id}/translate` → join сегментов в сплошной текст. Бейдж "Translation ready" на toggle, если панель закрыта.
- YouTube flow: `POST /videos/process` (deprecated, синхронный) — регистрирует задачу в TaskManager, возвращает `task_id` → перевод работает. Живой highlight сегментов — только для native-плеера.

## История изменений (после миграции)

1. Docs sync (domain-model, storage-architecture, баннеры на MVP-доках).
2. Фиксы усечения AI-ответов: бюджеты токенов (см. выше), batch 60→20.
3. PR `knowledge-layer-migration` (2 коммита) — запушен, PR оформляется в браузере.
4. UI-переделка: удалён summary, slide-панели Translation/Chapters, YouTube iframe, регистрация YouTube-задач на бэкенде.
5. Верхний блок Transcript удалён; полный текст — только в правой панели; retry 429.

## Тесты

`PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe test_<name>.py` — 8 suites: refactoring, task_store, sqlite_task_store, knowledge_stores, security_fixes, shadow_ingest, backfill, read_flip.
