# API Contract (VideoEssence MVP)

## База
- Backend: http://localhost:8000
- OpenAPI: http://localhost:8000/openapi.json
- Генерация типов: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/v1.d.ts`

## Ключевые эндпоинты

### Pipeline
- `POST /videos/process` → {task_id} (multipart: file ИЛИ json: {youtube_url})
- `GET /videos/{task_id}/status` → TaskStatusResponse
- `POST /videos/{task_id}/translate` → {target_language, ai_profile_id}
- `GET /videos/ai-profiles` → список

### Chat
- `POST /documents/{id}/chat/conversations` → {conversation_id}
- `GET /documents/{id}/chat/conversations` → список
- `GET /documents/{id}/chat/conversations/{cid}/messages` → список
- `POST /documents/{id}/chat/conversations/{cid}/messages` → {content} → (user_msg, assistant_msg)

### Notes
- `POST /documents/{id}/notes` → {text, chunk_id?, selected_text?}
- `GET /documents/{id}/notes` → список
- `PUT /documents/{id}/notes/{nid}` → update
- `DELETE /documents/{id}/notes/{nid}`

### Highlights
- Аналогично Notes под `/documents/{id}/highlights`

### Search
- `GET /documents/{id}/search?q=...&transcript=true&translation=true&notes=true`

### Knowledge Graph
- `GET /documents/{id}/knowledge-graph` → mock (заглушка)

## Ключевые DTO (упрощённо)

TaskStatusResponse:
  task_id, status, progress, error?,
  document_id?, title?,
  transcript: {segments: [{start, end, text}]},
  summary?: string,
  chapters?: [{title, start}],
  translation_results?: Record&lt;lang, {segments: []}&gt;

ChatMessage:
  id, conversation_id, role: 'user'|'assistant', content, created_at

Note:
  id, document_id, text, chunk_id?, selected_text?, created_at