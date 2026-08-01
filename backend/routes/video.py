from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from pathlib import Path
import mimetypes
import urllib.request
import urllib.error
import json
import time

from ..services.file_handler import save_uploaded_file, UploadValidationError
from ..services.input_processor import get_input_source, InputSourceType
from ..services.knowledge_ingest_service import KnowledgeIngestService
from ..services.knowledge_read_service import KnowledgeReadService
from ..services.storage import default_document_store, default_knowledge_store
from ..services.transcriber import Transcriber
from ..services.ai_provider import (
    AIProviderConfigurationError,
    get_ai_provider,
    get_ai_profiles_payload,
    to_user_facing_ai_error,
)
from ..services.transcript_enrichment_service import TranscriptEnrichmentService
from ..services.cleanup_service import cleanup_service
from ..services.task_manager import task_manager
from ..utils.file_utils import save_transcript, save_summary
from ..config.settings import settings
from ..config.ai_token_limits import get_limits
from ..schemas.video import TranscriptSegment, Chapter


router = APIRouter()

# Lazy singleton: knowledge-layer shadow writer (ADR-0006). Instantiated on
# first use so importing routes has no storage side effects; tests may
# monkeypatch this directly.
_knowledge_ingest: KnowledgeIngestService | None = None


def _get_knowledge_ingest() -> KnowledgeIngestService:
    global _knowledge_ingest
    if _knowledge_ingest is None:
        _knowledge_ingest = KnowledgeIngestService(
            default_document_store(), default_knowledge_store()
        )
    return _knowledge_ingest


# Lazy singleton: knowledge-layer read adapter (ADR-0008). Tests may
# monkeypatch this directly.
_knowledge_reader: KnowledgeReadService | None = None


def _get_knowledge_reader() -> KnowledgeReadService:
    global _knowledge_reader
    if _knowledge_reader is None:
        _knowledge_reader = KnowledgeReadService(
            default_document_store(), default_knowledge_store()
        )
    return _knowledge_reader

SUPPORTED_TRANSLATION_LANGUAGES: dict[str, str] = {
    "ru": "Russian",
    "en": "English",
}

TRANSLATION_LANGUAGE_ALIASES: dict[str, str] = {
    "ru": "Russian",
    "russian": "Russian",
    "русский": "Russian",
    "en": "English",
    "english": "English",
    "английский": "English",
}


def resolve_target_language(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    resolved = TRANSLATION_LANGUAGE_ALIASES.get(normalized)
    if not resolved:
        supported = ", ".join(SUPPORTED_TRANSLATION_LANGUAGES.keys())
        raise ValueError(f"Unsupported target_language '{value}'. Supported values: {supported}")
    return resolved


def validate_task_id(task_id: str) -> str:
    """Boundary validation for task ids arriving via URL paths.

    Only canonical UUIDs (the format this app generates) are accepted.
    Prevents path traversal into the task storage directory.
    """
    try:
        return str(uuid.UUID(task_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid task_id format")


class VideoRequest(BaseModel):
    """Request to process YouTube URL (legacy)."""
    url: str
    model_size: Optional[str] = "small"
    ai_profile: Optional[str] = "gemini_flash"


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
    ai_profile_id: Optional[str] = None
    ai_profile_name: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    transcript_language: Optional[str] = None
    timings: dict[str, float] = Field(default_factory=dict)
    document_id: Optional[str] = None
    translation_results: dict[str, dict] = Field(default_factory=dict)


class DocumentListItemResponse(BaseModel):
    document_id: str
    task_id: str
    status: str
    progress: str
    source_type: str
    language: Optional[str] = None
    transcript_language: Optional[str] = None
    ai_profile_id: Optional[str] = None
    ai_profile_name: Optional[str] = None


class TranslateTranscriptRequest(BaseModel):
    target_language: str = "ru"
    ai_profile: Optional[str] = None


class TranslateTranscriptResponse(BaseModel):
    task_id: str
    target_language: str
    ai_profile_id: str
    ai_profile_name: str
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)


def _process_file_with_ai_profile(
    task_id: str,
    uploaded_path: str,
    model_size: str,
    ai_profile_id: str,
    content_hash: str | None = None,
    origin_filename: str | None = None,
) -> None:
    """Background task: extract audio and process with selected AI profile."""
    audio_path: str | None = None
    transcript_path: str | None = None
    summary_path: str | None = None
    selected_profile = None
    try:
        task_manager.set_status(task_id, "processing", "Extracting audio from media")
        file_source = get_input_source(InputSourceType.FILE)
        audio_path = file_source.extract_audio(uploaded_path, task_id, settings.audio_dir)

        task_manager.set_status(task_id, "processing", "Building transcript with Whisper segments")
        transcribe_started = time.perf_counter()
        transcriber = Transcriber(model_size=model_size)
        transcript, transcript_segments, transcript_language = transcriber.transcribe_with_segments(audio_path)
        transcribe_seconds = round(time.perf_counter() - transcribe_started, 3)
        task_manager.update(task_id, timings={"transcription_seconds": transcribe_seconds})

        selected_profile, provider = get_ai_provider(ai_profile_id)
        task_manager.update(
            task_id,
            ai_profile_id=selected_profile.id,
            ai_profile_name=selected_profile.display_name,
            ai_provider=selected_profile.provider,
            ai_model=selected_profile.model,
        )

        task_manager.set_status(task_id, "processing", f"Generating summary and chapters with {selected_profile.display_name}")
        ai_started = time.perf_counter()
        if not hasattr(provider, "summarize_with_chapters"):
            raise RuntimeError(f"AI provider does not support summarize_with_chapters: {selected_profile.display_name}")

        result = provider.summarize_with_chapters(
            transcript_segments,
            source_language=transcript_language,
        )
        ai_seconds = round(time.perf_counter() - ai_started, 3)
        task = task_manager.get(task_id)
        started_at = task.started_at if task else None
        task_manager.update(
            task_id,
            timings={
                "ai_seconds": ai_seconds,
                "total_seconds": round(time.perf_counter() - (started_at or ai_started), 3),
            },
        )
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
            transcript_language=transcript_language,
            transcript_path=str(transcript_path),
            summary_path=str(summary_path),
            ai_profile_id=selected_profile.id,
            ai_profile_name=selected_profile.display_name,
            ai_provider=selected_profile.provider,
            ai_model=selected_profile.model,
        )

        # Best-effort shadow write into the knowledge layer (ADR-0006).
        # Runs after set_result, so failures cannot affect the task outcome.
        try:
            document_id = _get_knowledge_ingest().shadow_write_task(
                task_manager.get(task_id), content_hash, origin_filename
            )
            if document_id:
                task_manager.update(task_id, document_id=document_id)
        except Exception as shadow_exc:
            print(f"⚠️ Shadow write failed for task {task_id}: {shadow_exc}")

    except AIProviderConfigurationError as e:
        task_manager.set_error(task_id, str(e))
        print(f"❌ Task {task_id} failed: {e}")
    except Exception as e:
        import traceback

        error_message = to_user_facing_ai_error(selected_profile, e) if selected_profile else str(e)
        task_manager.set_error(task_id, error_message)
        print(f"❌ Task {task_id} failed: {e}")
        print(traceback.format_exc())
    finally:
        # Keep transcript/summary artifacts: they are persistent results
        # referenced by the task record (see ADR-0002, C5).
        # Preserve the uploaded source so the UI can later playback the media.
        cleanup_service.cleanup(audio_path)
        cleanup_service.cleanup_prefixed_files(settings.audio_dir, task_id)


@router.post("/process-file", response_model=ProcessMediaResponse, status_code=202)
async def process_media_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio or video file to process"),
    model_size: str = Form("tiny", description="Whisper model size"),
    ai_profile: str = Form("gemini_flash", description="AI profile id"),
):
    """Queue uploaded audio/video file for AI profile processing.
    
    Returns immediately with task_id and process status.
    """
    try:
        resolved_profile, _provider = get_ai_provider(ai_profile)
    except AIProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    task_id = str(uuid.uuid4())
    task_manager.create(task_id, source="file")
    task_manager.update(
        task_id,
        ai_profile_id=resolved_profile.id,
        ai_profile_name=resolved_profile.display_name,
        ai_provider=resolved_profile.provider,
        ai_model=resolved_profile.model,
    )
    task_manager.set_status(task_id, "processing", "Uploading file to backend")

    try:
        uploaded_path, content_hash = await save_uploaded_file(file, settings.audio_dir)
        task_manager.set_status(task_id, "processing", "File uploaded. Task started")
        task_manager.update(task_id, media_path=uploaded_path)

        background_tasks.add_task(
            _process_file_with_ai_profile,
            task_id,
            uploaded_path,
            model_size,
            resolved_profile.id,
            content_hash,
            file.filename,
        )

        return JSONResponse(status_code=202, content=ProcessMediaResponse(
            task_id=task_id,
            status="processing",
            progress=f"Task accepted. Processing with {resolved_profile.display_name}",
            source_type="file",
        ).model_dump())

    except UploadValidationError as e:
        task_manager.set_error(task_id, str(e))
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        task_manager.set_error(task_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    task_id = validate_task_id(task_id)
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Read-flip (ADR-0008): serve content from the knowledge layer when the
    # switch is on and the shadow is complete; otherwise the task record.
    if settings.knowledge_read_enabled and task.document_id:
        payload = _get_knowledge_reader().assemble_status(task)
        if payload is not None:
            return TaskStatusResponse(**payload)

    return TaskStatusResponse(**task_manager.to_dict(task_id))


@router.get("/documents", response_model=list[DocumentListItemResponse])
def list_documents():
    seen: set[str] = set()
    items: list[DocumentListItemResponse] = []
    for task in task_manager.list_tasks():
        if not task.document_id:
            continue
        if task.document_id in seen:
            continue
        seen.add(task.document_id)
        items.append(
            DocumentListItemResponse(
                document_id=task.document_id,
                task_id=task.id,
                status=task.status,
                progress=task.progress,
                source_type=task.source,
                language=task.language,
                transcript_language=task.transcript_language,
                ai_profile_id=task.ai_profile_id,
                ai_profile_name=task.ai_profile_name,
            )
        )
    return items


@router.get("/documents/{document_id}/media")
def get_document_media(document_id: str):
    try:
        document_id = str(uuid.UUID(document_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid document_id")

    for task in task_manager.list_tasks():
        if task.document_id != document_id:
            continue
        if not task.media_path:
            raise HTTPException(status_code=404, detail="Media not found for this document")

        media_file = Path(task.media_path)
        if not media_file.exists():
            raise HTTPException(status_code=404, detail="Media file not found")

        media_type, _ = mimetypes.guess_type(media_file.name)
        return FileResponse(
            media_file,
            media_type=media_type or "application/octet-stream",
        )

    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/documents/{document_id}", response_model=TaskStatusResponse)
def get_document_snapshot(document_id: str):
    try:
        document_id = str(uuid.UUID(document_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid document_id")
    for task in task_manager.list_tasks():
        if task.document_id != document_id:
            continue
        payload = task_manager.to_dict(task.id)
        if payload is None:
            break
        return TaskStatusResponse(**payload)
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/ai-profiles")
def get_ai_profiles():
    return get_ai_profiles_payload()


@router.post("/status/{task_id}/translate", response_model=TranslateTranscriptResponse)
def translate_task_transcript(task_id: str, req: TranslateTranscriptRequest):
    task_id = validate_task_id(task_id)
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="Task is not completed yet")
    if not task.transcript_segments:
        raise HTTPException(status_code=422, detail="Transcript segments are missing for this task")

    try:
        resolved_target_language = resolve_target_language(req.target_language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    profile_id = req.ai_profile or task.ai_profile_id or "gemini_flash"
    try:
        selected_profile, provider = get_ai_provider(profile_id)
    except AIProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    cache_key = f"{selected_profile.id}:{resolved_target_language.lower()}"
    translation_results = task.translation_results or {}
    cached_result = translation_results.get(cache_key)
    if isinstance(cached_result, dict):
        cached_segments = cached_result.get("transcript_segments")
        cache_has_status = False
        if isinstance(cached_segments, list) and cached_segments:
            for seg in cached_segments:
                enrichment = seg.get("enrichment") if isinstance(seg, dict) else None
                if isinstance(enrichment, dict) and enrichment.get("translation_status") in {"ready", "failed", "not_generated"}:
                    cache_has_status = True
                    break
        if isinstance(cached_segments, list) and cached_segments and cache_has_status:
            return TranslateTranscriptResponse(
                task_id=task.id,
                target_language=resolved_target_language,
                ai_profile_id=selected_profile.id,
                ai_profile_name=selected_profile.display_name,
                transcript_segments=cached_segments,
            )

    try:
        enrichment_service = TranscriptEnrichmentService(
            provider,
            token_limits=get_limits(selected_profile.id),
        )
        translated_segments = enrichment_service.enrich_segments(
            transcript_segments=task.transcript_segments,
            source_language=task.transcript_language or task.language,
            target_language=resolved_target_language,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=to_user_facing_ai_error(selected_profile, exc),
        )

    translation_results[cache_key] = {
        "target_language": resolved_target_language,
        "ai_profile_id": selected_profile.id,
        "ai_profile_name": selected_profile.display_name,
        "ai_provider": selected_profile.provider,
        "ai_model": selected_profile.model,
        "transcript_segments": translated_segments,
    }
    task_manager.update(task_id, translation_results=translation_results)

    # Best-effort shadow of translations into chunk-scoped enrichments.
    try:
        _get_knowledge_ingest().shadow_write_translations(task_manager.get(task_id))
    except Exception as shadow_exc:
        print(f"⚠️ Translation shadow write failed for task {task_id}: {shadow_exc}")

    return TranslateTranscriptResponse(
        task_id=task.id,
        target_language=resolved_target_language,
        ai_profile_id=selected_profile.id,
        ai_profile_name=selected_profile.display_name,
        transcript_segments=translated_segments,
    )

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
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "reason": f"Connectivity check failed: {e}",
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
    selected_profile = None

    try:
        selected_profile, provider = get_ai_provider(req.ai_profile)
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
        transcript, transcript_segments, transcript_language = transcriber.transcribe_with_segments(audio_path)
        timings["transcription_seconds"] = round(time.perf_counter() - transcribe_started, 3)

        print("STEP 3: Summarizing + chapters")
        ai_started = time.perf_counter()
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
            chapter_result = provider.summarize_with_chapters(
                transcript_segments,
                source_language=transcript_language,
            )
            summary = chapter_result["summary"]
            chapters = chapter_result["chapters"]

        timings["ai_seconds"] = round(time.perf_counter() - ai_started, 3)
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

    except AIProviderConfigurationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        import traceback
        print(f"❌ Task {task_id} failed: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=to_user_facing_ai_error(selected_profile, e) if selected_profile else str(e),
        )
    finally:
        # Keep transcript/summary artifacts: they are persistent results
        # referenced by the task record (see ADR-0002, C5).
        cleanup_service.cleanup(uploaded_path, audio_path)
        cleanup_service.cleanup_prefixed_files(settings.audio_dir, task_id)
