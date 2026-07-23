from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from pathlib import Path
import urllib.request
import urllib.error
import json
import time

from ..services.file_handler import save_uploaded_file
from ..services.input_processor import get_input_source, InputSourceType
from ..services.transcriber import Transcriber
from ..services.ai_provider import get_default_ai_provider
from ..services.cleanup_service import cleanup_service
from ..services.task_manager import task_manager
from ..utils.file_utils import save_transcript, save_summary
from ..config.settings import settings
from ..schemas.video import TranscriptSegment, Chapter


router = APIRouter()


class VideoRequest(BaseModel):
    """Request to process YouTube URL (legacy)."""
    url: str
    model_size: Optional[str] = "small"


class VideoResponse(BaseModel):
    transcript: str
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    summary: str
    language: Optional[str] = None
    timings: dict[str, float] = Field(default_factory=dict)


class ProcessMediaResponse(BaseModel):
    task_id: str
    status: str
    progress: str
    source_type: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: str
    error: Optional[str] = None
    transcript: Optional[str] = None
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    summary: Optional[str] = None
    language: Optional[str] = None
    source_type: str
    timings: dict[str, float] = Field(default_factory=dict)


class TranslateRequest(BaseModel):
    text: str
    target_language: str = "Russian"


class TranslateResponse(BaseModel):
    translated_text: str


def _process_file_with_gemini(task_id: str, uploaded_path: str, model_size: str) -> None:
    """Background task: extract audio and let Gemini return transcript+summary in one pass."""
    audio_path: str | None = None
    transcript_path: str | None = None
    summary_path: str | None = None
    try:
        task_manager.set_status(task_id, "processing", "Extracting audio from media")
        file_source = get_input_source(InputSourceType.FILE)
        audio_path = file_source.extract_audio(uploaded_path, task_id, settings.audio_dir)

        task_manager.set_status(task_id, "processing", "Building transcript with Whisper segments")
        transcribe_started = time.perf_counter()
        transcriber = Transcriber(model_size=model_size)
        transcript, transcript_segments = transcriber.transcribe_with_segments(audio_path)
        transcribe_seconds = round(time.perf_counter() - transcribe_started, 3)
        task = task_manager.get(task_id)
        if task:
            task.timings = task.timings or {}
            task.timings["transcription_seconds"] = transcribe_seconds
            task_manager._save(task)

        task_manager.set_status(task_id, "processing", "Generating summary and chapters with Gemini")
        gemini_started = time.perf_counter()
        provider = get_default_ai_provider()
        if not hasattr(provider, "summarize_with_chapters"):
            raise RuntimeError("Google Gemini is not configured. Set GOOGLE_API_KEY in .env")

        result = provider.summarize_with_chapters(transcript_segments)
        gemini_seconds = round(time.perf_counter() - gemini_started, 3)
        task = task_manager.get(task_id)
        if task:
            task.timings = task.timings or {}
            task.timings["gemini_seconds"] = gemini_seconds
            task.timings["total_seconds"] = round(time.perf_counter() - (task.started_at or gemini_started), 3)
            task_manager._save(task)
        summary = result["summary"]
        chapters = result["chapters"]
        language = result.get("language")

        task_manager.set_status(task_id, "processing", "Saving transcript and summary")
        transcript_path = str(Path(settings.transcripts_dir) / f"{task_id}.txt")
        summary_path = str(Path(settings.summaries_dir) / f"{task_id}.txt")
        save_transcript(transcript_path, transcript)
        save_summary(summary_path, summary)

        task_manager.set_result(
            task_id=task_id,
            transcript=transcript,
            transcript_segments=transcript_segments,
            chapters=chapters,
            summary=summary,
            language=language,
            transcript_path=str(transcript_path),
            summary_path=str(summary_path),
        )

    except Exception as e:
        import traceback

        task_manager.set_error(task_id, str(e))
        print(f"❌ Task {task_id} failed: {e}")
        print(traceback.format_exc())
    finally:
        cleanup_service.cleanup(uploaded_path, audio_path, transcript_path, summary_path)
        cleanup_service.cleanup_prefixed_files(settings.audio_dir, task_id)


@router.post("/process-file", response_model=ProcessMediaResponse, status_code=202)
async def process_media_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio or video file to process"),
    model_size: str = Form("tiny", description="Whisper model size")
):
    """Queue uploaded audio/video file for Gemini server-side processing.
    
    Returns immediately with task_id and process status.
    """
    task_id = str(uuid.uuid4())
    task_manager.create(task_id, source="file")
    task_manager.set_status(task_id, "processing", "Uploading file to backend")

    try:
        uploaded_path = await save_uploaded_file(file, settings.audio_dir)
        task_manager.set_status(task_id, "processing", "File uploaded. Task started")

        background_tasks.add_task(_process_file_with_gemini, task_id, uploaded_path, model_size)

        return JSONResponse(status_code=202, content=ProcessMediaResponse(
            task_id=task_id,
            status="processing",
            progress="Task accepted. Processing on Gemini servers",
            source_type="file",
        ).model_dump())

    except Exception as e:
        task_manager.set_error(task_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translate", response_model=TranslateResponse)
def translate_text(req: TranslateRequest):
    provider = get_default_ai_provider()
    if not hasattr(provider, "translate_text"):
        raise HTTPException(status_code=503, detail="Google Gemini is not configured")

    translated_text = provider.translate_text(req.text, req.target_language)
    return TranslateResponse(translated_text=translated_text)


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    task = task_manager.to_dict(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(**task)

@router.get("/health/gemini")
def gemini_health_check():
    """Check Gemini API reachability with the key currently loaded by this backend process."""
    key = (settings.google_api_key or "").strip()
    if not key:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "reason": "GOOGLE_API_KEY is empty in backend settings",
            },
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    req = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(body)
            models = payload.get("models", [])
            return {
                "ok": True,
                "status_code": response.status,
                "model_count": len(models),
                "key_prefix": key[:4],
                "key_length": len(key),
            }
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "status_code": e.code,
                "reason": "Gemini API returned an error",
                "response": raw[:500],
                "key_prefix": key[:4],
                "key_length": len(key),
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "reason": f"Connectivity check failed: {e}",
                "key_prefix": key[:4],
                "key_length": len(key),
            },
        )


@router.post("/process", response_model=VideoResponse)
def process_video(req: VideoRequest):
    """DEPRECATED: YouTube URL endpoint. Use /process-file instead.
    
    This endpoint is kept for backward compatibility.
    New implementations should use file uploads via /process-file.
    """
    task_id = str(uuid.uuid4())

    uploaded_path: str | None = None
    audio_path: str | None = None
    transcript_path: str | None = None
    summary_path: str | None = None
    timings: dict[str, float] = {}

    try:
        print(f"\n{'='*60}")
        print(f"TASK {task_id}: Processing YouTube URL (DEPRECATED)")
        print(f"URL: {req.url}")
        print(f"{'='*60}")
        
        print("STEP 1: Downloading audio from YouTube")
        youtube_source = get_input_source(InputSourceType.YOUTUBE)
        audio_path = youtube_source.extract_audio(req.url, task_id, settings.audio_dir)

        print("STEP 2: Transcribing")
        transcribe_started = time.perf_counter()
        transcriber = Transcriber(model_size=req.model_size or "small")
        transcript, transcript_segments = transcriber.transcribe_with_segments(audio_path)
        timings["transcription_seconds"] = round(time.perf_counter() - transcribe_started, 3)

        print("STEP 3: Summarizing + chapters")
        gemini_started = time.perf_counter()
        provider = get_default_ai_provider()
        if not hasattr(provider, "summarize_with_chapters"):
            summary = provider.summarize(transcript)
            chapters = [
                {
                    "title": "Full Video",
                    "summary": summary,
                    "start": transcript_segments[0]["start"] if transcript_segments else 0.0,
                }
            ]
        else:
            chapter_result = provider.summarize_with_chapters(transcript_segments)
            summary = chapter_result["summary"]
            chapters = chapter_result["chapters"]
        timings["gemini_seconds"] = round(time.perf_counter() - gemini_started, 3)
        timings["total_seconds"] = round(time.perf_counter() - transcribe_started, 3)

        transcript_path = f"data/transcripts/{task_id}.txt"
        summary_path = f"data/summaries/{task_id}.txt"
        save_transcript(transcript_path, transcript)
        save_summary(summary_path, summary)

        print(f"✅ Task {task_id} completed successfully")
        print(f"{'='*60}\n")

        return VideoResponse(
            transcript=transcript,
            transcript_segments=transcript_segments,
            chapters=chapters,
            summary=summary,
            timings=timings,
        )

    except Exception as e:
        import traceback
        print(f"❌ Task {task_id} failed: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_service.cleanup(uploaded_path, audio_path, transcript_path, summary_path)
        cleanup_service.cleanup_prefixed_files(settings.audio_dir, task_id)
