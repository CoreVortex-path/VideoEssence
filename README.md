# VideoBrain (MVP)

An AI-powered media processor that converts audio and video files into transcriptions and summaries using Whisper and Gemini APIs.

## 🎯 Features

- **Primary Input**: Upload local audio/video files (MP3, WAV, M4A, MP4, MKV, AVI, etc.)
- **Optional Input**: YouTube URLs (for backward compatibility)
- **Transcription**: Fast and accurate using Whisper (faster-whisper)
- **Summarization**: Intelligent summaries using Google Gemini AI
- **Extensible Architecture**: Easy to add new input sources without changing pipeline

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- ffmpeg (optional, for video processing)
- Google Gemini API key (for summarization)

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

3. **Create `.env` file** with your API key:
   ```
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

4. **Start the server**:
   ```bash
   uvicorn backend.app:app --reload --port 8000
   ```

5. **Open in browser**:
   Visit `http://localhost:8000`

## 📖 Documentation

- [**API Examples**](API_EXAMPLES.md) - cURL, Python, JavaScript examples
- [**Refactoring Guide**](REFACTORING_GUIDE.md) - Architecture details and extending
- [**Completion Summary**](REFACTORING_COMPLETE.md) - What changed and why

## 🎬 Usage

### Web UI (Recommended)
1. Open http://localhost:8000
2. Select input method:
   - **📁 Local File** (Primary): Upload MP3, MP4, etc.
   - **▶️ YouTube URL** (Optional): Paste YouTube link
3. Click "Process" and wait for results

### API Endpoints

**File Upload (Primary)**:
```bash
POST /videos/process-file
- file: Audio or video file
- model_size: "small" (default), "tiny", "medium", "large"
```

**YouTube (Legacy)**:
```bash
POST /videos/process
- url: YouTube URL
- model_size: "small" (default)
```

See [API_EXAMPLES.md](API_EXAMPLES.md) for full examples.

## 📁 Project Structure

```
VideoEssense/
├── backend/
│   ├── services/
│   │   ├── input_sources/      # Pluggable input handlers
│   │   ├── transcriber.py      # Whisper integration
│   │   ├── ai_provider.py      # Gemini integration
│   │   └── ...
│   ├── routes/
│   │   └── video.py            # API endpoints
│   ├── config/
│   │   └── settings.py         # Configuration
│   └── app.py                  # FastAPI app
├── frontend/
│   └── index.html              # Web UI
├── data/
│   ├── audio/                  # Uploaded/processed audio
│   ├── transcripts/            # Saved transcripts
│   └── summaries/              # Saved summaries
└── requirements.txt            # Dependencies
```

## 🏗️ Architecture Highlights

### Input Source Abstraction
```python
# Easy to add new input sources:
from backend.services.input_sources.base import InputSource

class MyCloudStorageSource(InputSource):
    def extract_audio(self, input_data, task_id, output_dir):
        # Download from cloud, extract, save locally
        pass
```

### Processing Pipeline
The transcription and summarization pipeline is input-agnostic:
1. Extract audio → 2. Transcribe → 3. Summarize

Works with any audio source!

## 🔧 Development

### Running Tests
```bash
python test_refactoring.py
```

### Interactive API Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Extending with New Sources
See [REFACTORING_GUIDE.md](REFACTORING_GUIDE.md) for detailed instructions.

## 📋 Supported Formats

**Audio**: MP3, WAV, M4A, FLAC, OGG, WMA
**Video**: MP4, MKV, AVI, MOV, FLV, WEBM, M4V

## ⚙️ Configuration

Environment variables in `.env`:
- `GOOGLE_API_KEY` - Gemini API key (optional, falls back to dummy summarizer)
- Default paths can be modified in `backend/config/settings.py`

## 📚 Notes

- This project emphasizes clean architecture and replaceable AI providers
- If `GOOGLE_API_KEY` is missing, the app uses a simple truncation-based summarizer
- The frontend is built-in at `http://localhost:8000`
- For YouTube URLs, optional `cookies.txt` file supports authentication
- Install ffmpeg for better video processing (automatic fallback if not available)

## 🔄 Recent Changes (MVP Refactoring)

✅ **File uploads** are now the primary input method  
✅ **Extensible architecture** - add new input sources easily  
✅ **Backward compatible** - YouTube still works  
✅ **Pipeline unchanged** - transcription/summarization works as before  
✅ **Better UI** - tab-based input selection  

See [REFACTORING_COMPLETE.md](REFACTORING_COMPLETE.md) for details.
