# VideoBrain MVP Refactoring Guide

> **Superseded.** Historical MVP-era document, kept for reference only. It
> describes the pre-migration architecture. The current system is documented
> in [README.md](README.md) and [docs/](docs/README.md) (domain model,
> storage architecture, operations, ADR-0001–0008).

## Overview

The MVP has been refactored to support **local file uploads as the primary input** while maintaining extensibility for future sources like YouTube. The transcription and summarization pipeline remains unchanged.

## Architecture

### Input Source System

The refactoring introduces an **Input Source Abstraction Layer** that decouples input extraction from the processing pipeline:

```
┌─────────────────────────────────┐
│   User Input                    │
│   ├─ Local File Upload (NEW)   │
│   └─ YouTube URL (Optional)     │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│   Input Source Layer            │
│   ├─ FileInputSource            │
│   ├─ YouTubeInputSource         │
│   └─ [Future Sources]           │
└──────────────┬──────────────────┘
               │
               ▼
        [Extract Audio]
               │
               ▼
┌─────────────────────────────────┐
│   Processing Pipeline           │
│   ├─ Transcription              │
│   └─ Summarization              │
└─────────────────────────────────┘
```

### File Structure

```
backend/services/
├── input_sources/
│   ├── __init__.py
│   ├── base.py                 # Abstract InputSource class
│   ├── file_source.py          # Local file uploads
│   └── youtube_source.py       # YouTube URLs (optional)
├── input_processor.py          # Factory pattern
├── file_handler.py             # Upload handling
├── transcriber.py              # Unchanged
├── ai_provider.py              # Unchanged
├── downloader.py               # Deprecated (replaced by input_sources)
└── ...
```

## API Endpoints

### New Primary Endpoint: File Upload

```http
POST /videos/process-file
Content-Type: multipart/form-data

file: <binary audio/video file>
model_size: "small" | "medium" | "large"

Response:
{
  "task_id": "uuid",
  "transcript": "...",
  "summary": "...",
  "source_type": "file"
}
```

**Supported Formats:**
- **Audio**: MP3, WAV, M4A, FLAC, OGG, WMA
- **Video**: MP4, MKV, AVI, MOV, FLV, WEBM, M4V

### Legacy Endpoint: YouTube (Deprecated but Supported)

```http
POST /videos/process
Content-Type: application/json

{
  "url": "https://youtu.be/...",
  "model_size": "small"
}

Response:
{
  "transcript": "...",
  "summary": "...",
  "language": null
}
```

## How to Use

### 1. Start the Server

```bash
uvicorn backend.app:app --reload --port 8000
```

### 2. Upload a Local File

#### Using the Web UI
1. Open `http://localhost:8000` in your browser
2. Click "📁 Local File" tab (default)
3. Click "Choose File" and select an audio or video file
4. Click "Process File"
5. Wait for transcription and summary

#### Using cURL
```bash
curl -X POST "http://localhost:8000/videos/process-file" \
  -F "file=@/path/to/audio.mp3" \
  -F "model_size=small"
```

#### Using Python
```python
import requests

files = {'file': open('audio.mp3', 'rb')}
data = {'model_size': 'small'}
response = requests.post('http://localhost:8000/videos/process-file', 
                        files=files, data=data)
print(response.json())
```

### 3. YouTube Support (Optional)

To use YouTube URLs:
1. Click "▶️ YouTube URL" tab in the web UI
2. Paste a YouTube URL
3. Click "Process URL"

**Prerequisites for YouTube:**
- `cookies.txt` file in project root (for authentication)
- See [yt-dlp docs](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) to export cookies

## Adding New Input Sources

### Step 1: Create a New Source Class

Create `backend/services/input_sources/my_source.py`:

```python
from .base import InputSource
from pathlib import Path

class MyInputSource(InputSource):
    def extract_audio(self, input_data, task_id, output_dir):
        """Extract audio from your source."""
        # 1. Get the audio from your source
        # 2. Convert to WAV if needed
        # 3. Save to output_dir / f"{task_id}.wav"
        
        output_file = output_dir / f"{task_id}.wav"
        # ... your extraction logic ...
        return str(output_file)
```

### Step 2: Register the Source

Edit `backend/services/input_processor.py`:

```python
from .input_sources.my_source import MyInputSource

class InputSourceType(str, Enum):
    FILE = "file"
    YOUTUBE = "youtube"
    MY_SOURCE = "my_source"  # Add this

def get_input_source(source_type):
    sources = {
        InputSourceType.FILE: FileInputSource,
        InputSourceType.YOUTUBE: YouTubeInputSource,
        InputSourceType.MY_SOURCE: MyInputSource,  # Add this
    }
    # ...
```

### Step 3: Add Route (Optional)

Create an endpoint in `backend/routes/video.py`:

```python
@router.post("/process-my-source")
def process_my_source(input_data: MySourceRequest):
    task_id = str(uuid.uuid4())
    my_source = get_input_source(InputSourceType.MY_SOURCE)
    audio_path = my_source.extract_audio(input_data.url, task_id, settings.audio_dir)
    # ... process as usual ...
```

## Key Design Principles

1. **Separation of Concerns**: Input extraction → Processing pipeline
2. **Extensibility**: New sources don't require pipeline changes
3. **Type Safety**: Abstract base class defines the contract
4. **Backward Compatibility**: YouTube still works via legacy endpoint
5. **Error Handling**: Clear error messages for unsupported formats

## Dependencies

New dependency for file uploads:
```bash
pip install python-multipart
```

Added to `requirements.txt` automatically.

## Frontend Updates

The web UI now features:
- ✅ Tab-based input selection (File / YouTube)
- ✅ File upload with progress
- ✅ File size display
- ✅ Better status messages
- ✅ Responsive design

## Troubleshooting

### "Unsupported file format"
- Check file extension is in supported list
- For custom formats, consider using ffmpeg to convert first

### "ffmpeg not found"
- For video files, install ffmpeg
- Or place ffmpeg at `C:\ffmpeg\bin\ffmpeg.exe` (Windows)
- For audio-only files, ffmpeg is optional

### "Sign in to confirm you're not a bot" (YouTube)
- Export cookies from your YouTube session
- See [yt-dlp docs](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)

## Migration Path

### From YouTube-Only to File Upload
1. ✅ Done! File upload is now primary
2. YouTube still works for backward compatibility
3. Gradually migrate users to file uploads

### Future Enhancements
- Cloud storage integration (S3, Azure Blob)
- Direct API input (POST raw audio)
- Podcast/streaming URLs
- Real-time transcription
- Batch processing
