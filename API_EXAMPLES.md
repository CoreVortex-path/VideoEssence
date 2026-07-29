# API Usage Examples

## Starting the Server

```bash
cd VideoEssense
uvicorn backend.app:app --reload --port 8000
```

Server: `http://localhost:8000` · Web UI: `http://localhost:8000` · Interactive docs: `http://localhost:8000/docs`

## Processing Flow (async)

Processing is **asynchronous**: submitting a file returns `202 Accepted` with a `task_id`; results are fetched by polling the status endpoint.

```
POST /videos/process-file          → 202 { task_id }
GET  /videos/status/{task_id}      → poll until status = "completed" | "failed"
POST /videos/status/{task_id}/translate  → on-demand translation (cached)
GET  /videos/ai-profiles           → available AI profiles
GET  /videos/health/gemini         → Gemini connectivity check
```

## 1. Upload and Process a File

### Submit (cURL)

```bash
curl -X POST "http://localhost:8000/videos/process-file" \
  -F "file=@~/Downloads/audio.mp3" \
  -F "model_size=small" \
  -F "ai_profile=gemini_flash"
```

**Response — 202 Accepted:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": "Task accepted. Processing with Gemini Flash",
  "source_type": "file"
}
```

### Poll for the result (cURL)

```bash
curl "http://localhost:8000/videos/status/550e8400-e29b-41d4-a716-446655440000"
```

**Response — 200 (completed):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": "Task completed",
  "error": null,
  "transcript": "Full transcript text...",
  "transcript_segments": [
    {"start": 0.0, "end": 4.2, "text": "first segment", "enrichment": null}
  ],
  "chapters": [
    {"title": "Introduction", "summary": "opening remarks", "start": 0.0}
  ],
  "summary": "Summary text...",
  "language": "russian",
  "source_type": "file",
  "ai_profile_id": "gemini_flash",
  "ai_profile_name": "Gemini Flash",
  "ai_provider": "gemini",
  "ai_model": "gemini-2.5-flash",
  "transcript_language": "ru",
  "timings": {"transcription_seconds": 12.3, "ai_seconds": 4.5, "total_seconds": 18.1}
}
```

While processing, `status` is `"processing"` and `progress` describes the current step. On failure, `status` is `"failed"` and `error` holds the reason.

### Full example (Python, submit + poll)

```python
import time
import requests

BASE = "http://localhost:8000"

with open("audio.mp3", "rb") as f:
    r = requests.post(
        f"{BASE}/videos/process-file",
        files={"file": f},
        data={"model_size": "small", "ai_profile": "gemini_flash"},
    )
r.raise_for_status()
task_id = r.json()["task_id"]

while True:
    time.sleep(2)
    status = requests.get(f"{BASE}/videos/status/{task_id}").json()
    print(status["progress"])
    if status["status"] == "completed":
        print(status["summary"])
        break
    if status["status"] == "failed":
        raise RuntimeError(status["error"])
```

### Full example (JavaScript, submit + poll)

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('model_size', 'small');
formData.append('ai_profile', 'gemini_flash');

const submit = await fetch('http://localhost:8000/videos/process-file', {
  method: 'POST',
  body: formData,
});
const { task_id } = await submit.json();

const poll = setInterval(async () => {
  const r = await fetch(`http://localhost:8000/videos/status/${task_id}`);
  const data = await r.json();
  if (data.status === 'completed') {
    clearInterval(poll);
    console.log('Summary:', data.summary);
  } else if (data.status === 'failed') {
    clearInterval(poll);
    console.error('Failed:', data.error);
  }
}, 2000);
```

### Postman

1. POST `http://localhost:8000/videos/process-file`
2. Body → **form-data**: `file` (File), `model_size` = `small`, `ai_profile` = `gemini_flash`
3. Send → copy `task_id` from the 202 response
4. GET `http://localhost:8000/videos/status/{task_id}` → repeat until `completed`

## 2. Translate a Completed Transcript

Translation reuses stored segments — no re-transcription, no re-summary. Results are cached per `(ai_profile, target_language)`.

```bash
curl -X POST "http://localhost:8000/videos/status/<task_id>/translate" \
  -H "Content-Type: application/json" \
  -d '{"target_language":"ru","ai_profile":"gemini_flash"}'
```

**Response — 200:**
```json
{
  "task_id": "<task_id>",
  "target_language": "Russian",
  "ai_profile_id": "gemini_flash",
  "ai_profile_name": "Gemini Flash",
  "transcript_segments": [
    {
      "start": 0.0,
      "end": 4.2,
      "text": "original text",
      "enrichment": {
        "translation": "перевод",
        "translation_status": "ready",
        "translation_error": null,
        "key_concepts": [],
        "entities": [],
        "tags": [],
        "extra": {}
      }
    }
  ]
}
```

`target_language`: `ru` or `en` (aliases like `russian`/`english` also accepted). Per-segment `translation_status` is `ready`, `failed`, or `not_generated`.

## 3. List AI Profiles

```bash
curl "http://localhost:8000/videos/ai-profiles"
```

```json
{
  "default_profile": "gemini_flash",
  "profiles": [
    {"id": "gemini_flash", "display_name": "Gemini Flash", "provider": "gemini", "model": "gemini-2.5-flash"},
    {"id": "gemini_pro", "display_name": "Gemini Pro", "provider": "gemini", "model": "gemini-2.5-pro"},
    {"id": "openrouter_default", "display_name": "OpenRouter", "provider": "openrouter", "model": "openai/gpt-4o-mini"}
  ]
}
```

## 4. Gemini Health Check

```bash
curl "http://localhost:8000/videos/health/gemini"
```

Returns `{"ok": true, ...}` when the configured key reaches the Gemini API, or an error with `ok: false` (503/502/500). No key details are exposed.

## 5. YouTube URL (Legacy)

> Deprecated, synchronous (blocks until done), kept for backward compatibility. Prefer `/videos/process-file`.

```bash
curl -X POST "http://localhost:8000/videos/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/spUNpyF58BY", "model_size": "small", "ai_profile": "gemini_flash"}'
```

Returns the full result (`transcript`, `transcript_segments`, `chapters`, `summary`, `timings`) in one response. For "Sign in to confirm you're not a bot" errors, export browser cookies to `cookies.txt` in the project root.

## Parameters

### `/videos/process-file`
- **file** (required): audio or video file
- **model_size** (optional, default `tiny`): Whisper model — `tiny`, `small`, `medium`, `large`
- **ai_profile** (optional, default `gemini_flash`): `gemini_flash`, `gemini_pro`, `openrouter_default`

Note: the built-in web UI always submits `model_size=tiny`.

### `/videos/status/{task_id}/translate`
- **target_language** (default `ru`): `ru` or `en`
- **ai_profile** (optional): defaults to the profile used for processing

## Error Handling

| Code | When |
|---|---|
| 400 | Invalid `task_id` format (must be a UUID) |
| 404 | Unknown task id |
| 409 | Translate requested before the task is `completed` |
| 413 | Upload exceeds `MAX_UPLOAD_SIZE_MB` (default 2048 MB) |
| 422 | Unsupported file format, unknown `ai_profile`/`target_language`, or missing transcript segments |
| 500 | Processing failure (detail contains the reason) |

**Example — unsupported format (422):**
```json
{"detail": "Unsupported file format: .xyz. Supported: ['.avi', '.flac', ...]"}
```

**Example — quota exhaustion (task fails, surfaced via status):**
```json
{"status": "failed", "error": "Квота Gemini исчерпана. Выберите OpenRouter или повторите попытку позже."}
```

## Supported File Formats

**Audio**: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.wma`
**Video**: `.mp4`, `.mkv`, `.avi`, `.mov`, `.flv`, `.webm`, `.m4v`

## Tips & Performance

| Model | Speed | Accuracy | RAM |
|-------|-------|----------|-----|
| tiny | ⚡ Very fast | Low | ~400MB |
| small | ⚡ Fast | Good | ~1GB |
| medium | 🟡 Moderate | Better | ~2GB |
| large | 🐢 Slow | Best | ~3GB |

- Files longer than 15 minutes are transcribed in 10-minute chunks automatically — no client changes needed.
- Re-uploading the *same file bytes* maps to the same knowledge-layer Document (content-addressed identity) — processing still runs, but storage deduplicates.
- Status responses are served from the persistent knowledge layer when available, with automatic fallback; see `KNOWLEDGE_READ_ENABLED` in the [README](README.md#️-configuration).
