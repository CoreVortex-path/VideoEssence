# API Usage Examples

## Starting the Server

```bash
cd VideoEssense
uvicorn backend.app:app --reload --port 8000
```

Server will be available at: `http://localhost:8000`

## Web UI

Simply open `http://localhost:8000` in your browser.

The UI has two tabs:
1. **📁 Local File** (Primary) - Upload and process audio/video files
2. **▶️ YouTube URL** (Optional) - Process YouTube videos

## API Examples

### 1. Upload Local File

#### Using cURL
```bash
# MP3 file
curl -X POST "http://localhost:8000/videos/process-file" \
  -F "file=@~/Downloads/audio.mp3" \
  -F "model_size=small"

# Video file
curl -X POST "http://localhost:8000/videos/process-file" \
  -F "file=@~/Videos/recording.mp4" \
  -F "model_size=small"
```

#### Using Python (requests)
```python
import requests

files = {'file': open('audio.mp3', 'rb')}
data = {'model_size': 'small'}

response = requests.post(
    'http://localhost:8000/videos/process-file',
    files=files,
    data=data
)

result = response.json()
print("Transcript:")
print(result['transcript'])
print("\nSummary:")
print(result['summary'])
```

#### Using Python (requests with context manager)
```python
import requests

with open('audio.mp3', 'rb') as f:
    files = {'file': f}
    data = {'model_size': 'small'}
    response = requests.post(
        'http://localhost:8000/videos/process-file',
        files=files,
        data=data
    )
    
result = response.json()
print(result)
```

#### Using JavaScript/Fetch
```javascript
const fileInput = document.getElementById('fileInput');
const file = fileInput.files[0];

const formData = new FormData();
formData.append('file', file);
formData.append('model_size', 'small');

fetch('http://localhost:8000/videos/process-file', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('Transcript:', data.transcript);
  console.log('Summary:', data.summary);
});
```

#### Using Postman
1. Create a new POST request
2. URL: `http://localhost:8000/videos/process-file`
3. Go to **Body** tab
4. Select **form-data**
5. Key: `file`, Type: **File**, Value: [Select your audio/video file]
6. Key: `model_size`, Type: **Text**, Value: `small`
7. Click **Send**

#### Response
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "transcript": "This is the transcribed text from the audio file...",
  "summary": "This is the summary of the content...",
  "source_type": "file"
}
```

### 2. YouTube URL (Legacy/Optional)

#### Using cURL
```bash
curl -X POST "http://localhost:8000/videos/process" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/spUNpyF58BY", "model_size": "small"}'
```

#### Using Python
```python
import requests
import json

data = {
    "url": "https://youtu.be/spUNpyF58BY",
    "model_size": "small"
}

response = requests.post(
    'http://localhost:8000/videos/process',
    json=data
)

result = response.json()
print("Transcript:")
print(result['transcript'])
print("\nSummary:")
print(result['summary'])
```

#### Using JavaScript/Fetch
```javascript
fetch('http://localhost:8000/videos/process', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://youtu.be/spUNpyF58BY',
    model_size: 'small'
  })
})
.then(response => response.json())
.then(data => {
  console.log('Transcript:', data.transcript);
  console.log('Summary:', data.summary);
});
```

#### Response
```json
{
  "transcript": "This is the transcribed text from the YouTube video...",
  "summary": "This is the summary of the content...",
  "language": null
}
```

## Parameters

### File Upload Endpoint
- **file** (required): The audio or video file
- **model_size** (optional): Whisper model size
  - `tiny` - Fastest, least accurate
  - `small` - Good balance (default)
  - `medium` - Better accuracy
  - `large` - Best accuracy, slowest

### YouTube Endpoint
- **url** (required): YouTube URL
- **model_size** (optional): Same as above

## Supported File Formats

### Audio
- `.mp3` - MPEG Audio
- `.wav` - WAV Audio
- `.m4a` - MPEG-4 Audio
- `.flac` - Free Lossless Audio
- `.ogg` - OGG Vorbis
- `.wma` - Windows Media Audio

### Video
- `.mp4` - MPEG-4 Video
- `.mkv` - Matroska Video
- `.avi` - Audio Video Interleave
- `.mov` - QuickTime Video
- `.flv` - Flash Video
- `.webm` - WebM Video
- `.m4v` - iTunes Video

## Error Handling

### File Not Found
```json
{
  "detail": "Input file not found: /path/to/file.mp3"
}
```

### Unsupported Format
```json
{
  "detail": "Unsupported file format: .xyz. Supported: {'.mp3', '.wav', ...}"
}
```

### Processing Error
```json
{
  "detail": "Failed to extract audio from video: ..."
}
```

## Tips & Tricks

### 1. Get Faster Results
Use `model_size: "tiny"` for quick processing:
```bash
curl -X POST "http://localhost:8000/videos/process-file" \
  -F "file=@audio.mp3" \
  -F "model_size=tiny"
```

### 2. Better Accuracy
Use `model_size: "large"` for best accuracy (slower):
```bash
curl -X POST "http://localhost:8000/videos/process-file" \
  -F "file=@audio.mp3" \
  -F "model_size=large"
```

### 3. Process Multiple Files Sequentially
```python
import requests
import os

files = [f for f in os.listdir('.') if f.endswith('.mp3')]

for filename in files:
    with open(filename, 'rb') as f:
        files_data = {'file': f}
        data = {'model_size': 'small'}
        response = requests.post(
            'http://localhost:8000/videos/process-file',
            files=files_data,
            data=data
        )
        result = response.json()
        print(f"{filename}: {result['summary'][:100]}...")
```

### 4. Check API Documentation
Visit `http://localhost:8000/docs` for interactive Swagger UI
Visit `http://localhost:8000/redoc` for ReDoc documentation

## Troubleshooting

### "Connection refused"
- Make sure server is running: `uvicorn backend.app:app --reload`
- Check port 8000 is not in use

### "File too large"
- FastAPI has a default size limit
- For large files, restart server or modify middleware

### "Unsupported format"
- Convert file to MP3 or WAV first
- Use ffmpeg: `ffmpeg -i video.mp4 audio.mp3`

### YouTube "Sign in to confirm you're not a bot"
- Export cookies from your YouTube session
- Save to `cookies.txt` in project root
- See: https://github.com/yt-dlp/yt-dlp/wiki/FAQ

## Performance Notes

| Model | Speed | Accuracy | RAM |
|-------|-------|----------|-----|
| tiny | ⚡ Very fast | Low | ~400MB |
| small | ⚡ Fast | Good | ~1GB |
| medium | 🟡 Moderate | Better | ~2GB |
| large | 🐢 Slow | Best | ~3GB |

For MVP: `small` is recommended (default)
