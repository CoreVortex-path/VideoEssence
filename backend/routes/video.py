from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from pathlib import Path
import mimetypes
import urllib.request
import urllib.error
import json
import time
import re

from ..services.file_handler import save_uploaded_file, UploadValidationError
from ..services.extractors import get_document_source_type, get_extractor
from ..services.input_processor import get_input_source, InputSourceType
from ..services.input_sources.youtube_subtitles import fetch_youtube_subtitles
from ..services.input_sources.youtube_source import extract_youtube_video_id, fetch_youtube_title
from ..services.knowledge_ingest_service import KnowledgeIngestService, deterministic_chunk_id
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
    task_id: Optional[str] = None
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
    # Original user-supplied URL (YouTube) so the player survives a reload.
    source_url: Optional[str] = None
    # AI insights from the summary pass: key terms and suggested questions.
    keywords: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    # Display name: uploaded filename or YouTube video title.
    title: Optional[str] = None


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


class ImportTranslationRequest(BaseModel):
    """Manual import of an external (non-LLM) translation as a single text block."""
    target_language: str = "ru"
    text: str = ""


def _split_translation_text(full_text: str, segment_count: int) -> list[str]:
    """Разбивает вставленный перевод на ~segment_count частей.

    Пробует последовательно:
    1. Абзацы (пустые строки)
    2. Одиночные переводы строки
    3. Предложения
    4. Fallback: пропорционально по символам с учётом границ слов
    """
    import re

    text = full_text.strip()
    if not text:
        return [""] * segment_count

    # 1. Абзацы (двойной \n)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) == segment_count:
        return paragraphs

    # 2. Одиночные строки
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) == segment_count:
        return lines

    # 3. Предложения
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    if len(sentences) == segment_count:
        return sentences

    # 4. Fallback: режем примерно поровну, стараясь не резать слова
    avg = len(text) / segment_count
    result: list[str] = []
    start = 0
    for i in range(segment_count):
        if i == segment_count - 1:
            result.append(text[start:].strip())
            break

        target = start + avg
        best_end = int(target)
        min_dist = float("inf")
        window = max(1, int(avg * 0.25))

        # Ищем ближайший пробел/перенос в окне ±25% от target
        for pos in range(max(start + 1, int(target - window)), min(len(text), int(target + window))):
            if text[pos] in " \n":
                dist = abs(pos - target)
                if dist < min_dist:
                    min_dist = dist
                    best_end = pos

        # Если в окне не нашли — ищем первый пробел после target
        if min_dist == float("inf"):
            space_after = text.find(" ", int(target))
            if space_after != -1:
                best_end = space_after

        result.append(text[start:best_end].strip())
        start = best_end

    return result


def _run_ai_pipeline(
    task_id: str,
    audio_path: str,
    model_size: str,
    ai_profile_id: str,
    content_hash: str | None = None,
    origin_label: str | None = None,
) -> None:
    """Transcribe + AI summarise + shadow-write. Called after audio is ready."""
    selected_profile = None
    try:
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
        keywords = result.get("keywords") or []
        suggested_questions = result.get("suggested_questions") or []

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
            keywords=keywords,
            suggested_questions=suggested_questions,
        )

        # Best-effort shadow write into the knowledge layer (ADR-0006).
        try:
            document_id = _get_knowledge_ingest().shadow_write_task(
                task_manager.get(task_id), content_hash, origin_label
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


def _process_file_with_ai_profile(
    task_id: str,
    uploaded_path: str,
    model_size: str,
    ai_profile_id: str,
    content_hash: str | None = None,
    origin_filename: str | None = None,
) -> None:
    """Background task: extract audio from an uploaded file, then run the AI pipeline."""
    audio_path: str | None = None
    try:
        task_manager.set_status(task_id, "processing", "Extracting audio from media")
        file_source = get_input_source(InputSourceType.FILE)
        audio_path = file_source.extract_audio(uploaded_path, task_id, settings.audio_dir)
        _run_ai_pipeline(task_id, audio_path, model_size, ai_profile_id, content_hash, origin_filename)
    except Exception as e:
        import traceback
        task_manager.set_error(task_id, str(e))
        print(f"❌ Task {task_id} failed during audio extraction: {e}")
        print(traceback.format_exc())
    finally:
        # Keep transcript/summary artifacts: they are persistent results
        # referenced by the task record (see ADR-0002, C5).
        # Preserve the uploaded source so the UI can later playback the media.
        cleanup_service.cleanup(audio_path)
        cleanup_service.cleanup_prefixed_files(settings.audio_dir, task_id)


def _process_document_file(
    task_id: str,
    uploaded_path: str,
    content_hash: str | None = None,
    origin_filename: str | None = None,
) -> None:
    """Background task: extract text from an uploaded document (PDF/FB2)
    and ingest it into the knowledge layer. No transcription, no AI.
    The uploaded file is kept as the document's source media.
    """
    try:
        extractor = get_extractor(Path(uploaded_path))
        source_type = get_document_source_type(Path(uploaded_path))
        if extractor is None or source_type is None:
            raise ValueError(f"No document extractor for file: {uploaded_path}")

        task_manager.set_status(task_id, "processing", "Extracting document text")
        extracted = extractor.extract(Path(uploaded_path))

        document_id = _get_knowledge_ingest().ingest_extracted_document(
            extracted,
            source_type=source_type,
            content_hash=content_hash,
            origin_filename=origin_filename,
        )

        # Keep the extracted text on the task so the legacy status payload
        # (TaskStatusResponse.transcript) serves document uploads too.
        task_manager.update(
            task_id,
            transcript="\n\n".join(chunk.text for chunk in extracted.chunks),
            transcript_segments=[],
            language=extracted.language,
            transcript_language=extracted.language,
            document_id=document_id,
            title=extracted.title or origin_filename,
        )
        task_manager.set_status(task_id, "completed", "Document text extracted")
    except Exception as e:
        import traceback
        task_manager.set_error(task_id, str(e))
        print(f"❌ Task {task_id} failed during document extraction: {e}")
        print(traceback.format_exc())


def _find_reusable_completed_task(
    content_hash: str | None = None,
    origin_uri: str | None = None,
):
    """Library reuse: completed task for already-ingested content, else None.

    Matches a knowledge-layer document by content hash (or origin uri as a
    fallback), then looks for a completed task pointing at that document.
    Never raises — a lookup failure means a regular fresh processing run.
    """
    try:
        store = default_document_store()
        document = store.find_by_content_hash(content_hash)
        if document is None:
            document = store.find_by_origin_uri(origin_uri)
        if document is None:
            return None
        for task in task_manager.list_tasks():
            if task.document_id == document.id and task.status == "completed":
                return task
    except Exception as exc:
        print(f"⚠️ Library reuse lookup failed: {exc}")
    return None


def _process_url_with_ai_profile(
    task_id: str,
    url: str,
    model_size: str,
    ai_profile_id: str,
    content_hash: str | None = None,
) -> None:
    """Background task: download audio from a YouTube URL, then run the AI pipeline."""
    try:
        task_manager.set_status(task_id, "processing", "Downloading audio from YouTube")
        # Best-effort display title; falls back to the raw URL as origin label.
        video_title = fetch_youtube_title(url)
        if video_title:
            task_manager.update(task_id, title=video_title)
        youtube_source = get_input_source(InputSourceType.YOUTUBE)
        audio_path = youtube_source.extract_audio(url, task_id, settings.audio_dir)
        task_manager.update(task_id, media_path=audio_path)
        _run_ai_pipeline(
            task_id, audio_path, model_size, ai_profile_id,
            content_hash=content_hash,
            origin_label=video_title or url,
        )
    except Exception as e:
        import traceback
        task_manager.set_error(task_id, str(e))
        print(f"❌ Task {task_id} failed during YouTube download: {e}")
        print(traceback.format_exc())
    # The downloaded audio is intentionally kept: it is the document media
    # served by GET /videos/documents/{id}/media after a library reopen.


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
        uploaded_path, content_hash = await save_uploaded_file(file, settings.audio_dir)
    except UploadValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Library reuse: the same content was already processed — return the
    # existing completed task instead of re-running the pipeline.
    reused = _find_reusable_completed_task(content_hash=content_hash)
    if reused is not None:
        cleanup_service.cleanup(uploaded_path)  # duplicate upload, media already stored
        return JSONResponse(status_code=202, content=ProcessMediaResponse(
            task_id=reused.id,
            status=reused.status,
            progress=reused.progress,
            source_type=reused.source,
        ).model_dump())

    # Document formats (PDF/FB2): text extraction only — no transcription,
    # no AI pipeline, so no AI profile is required for these uploads.
    if get_document_source_type(Path(uploaded_path)) is not None:
        task_id = str(uuid.uuid4())
        task_manager.create(task_id, source="file")
        task_manager.set_status(task_id, "processing", "File uploaded. Task started")
        task_manager.update(task_id, media_path=uploaded_path, title=file.filename)

        background_tasks.add_task(
            _process_document_file,
            task_id,
            uploaded_path,
            content_hash,
            file.filename,
        )

        return JSONResponse(status_code=202, content=ProcessMediaResponse(
            task_id=task_id,
            status="processing",
            progress="Task accepted. Extracting document text",
            source_type="file",
        ).model_dump())

    try:
        resolved_profile, _provider = get_ai_provider(ai_profile)
    except AIProviderConfigurationError as exc:
        cleanup_service.cleanup(uploaded_path)  # never leave an orphan upload
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
    task_manager.set_status(task_id, "processing", "File uploaded. Task started")
    task_manager.update(task_id, media_path=uploaded_path, title=file.filename)

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


class ProcessUrlRequest(BaseModel):
    url: str
    model_size: Optional[str] = "tiny"
    ai_profile: Optional[str] = "gemini_flash"


@router.post("/process-url", response_model=ProcessMediaResponse, status_code=202)
async def process_media_url(
    background_tasks: BackgroundTasks,
    req: ProcessUrlRequest,
):
    """Queue a YouTube URL for async AI processing.

    Same pipeline as /process-file but the audio is downloaded by
    YouTubeInputSource. Returns immediately with task_id.
    """
    try:
        resolved_profile, _provider = get_ai_provider(req.ai_profile or "gemini_flash")
    except AIProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Stable content key makes the document id deterministic for YouTube
    # (ADR-0006), so a re-submitted URL resolves to the existing document.
    video_id = extract_youtube_video_id(req.url)
    content_key = f"youtube:{video_id}" if video_id else None

    # Library reuse: this video was already processed — return the existing
    # completed task instead of downloading and re-running the pipeline.
    reused = _find_reusable_completed_task(content_hash=content_key, origin_uri=req.url)
    if reused is not None:
        return JSONResponse(status_code=202, content=ProcessMediaResponse(
            task_id=reused.id,
            status=reused.status,
            progress=reused.progress,
            source_type=reused.source,
        ).model_dump())

    task_id = str(uuid.uuid4())
    task_manager.create(task_id, source="youtube")
    task_manager.update(
        task_id,
        ai_profile_id=resolved_profile.id,
        ai_profile_name=resolved_profile.display_name,
        ai_provider=resolved_profile.provider,
        ai_model=resolved_profile.model,
        source_url=req.url,
    )
    task_manager.set_status(task_id, "processing", "Queued for YouTube download")

    background_tasks.add_task(
        _process_url_with_ai_profile,
        task_id,
        req.url,
        req.model_size or "tiny",
        resolved_profile.id,
        content_key,
    )

    return JSONResponse(status_code=202, content=ProcessMediaResponse(
        task_id=task_id,
        status="processing",
        progress=f"Task accepted. Processing with {resolved_profile.display_name}",
        source_type="youtube",
    ).model_dump())


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

    return TaskStatusResponse(**_with_chunk_ids(task_manager.to_dict(task_id)))


def _with_chunk_ids(payload: Optional[dict]) -> dict:
    """Attach stable knowledge chunk ids to transcript segments (task path).

    Ids are uuid5("chunk", document_id, ordinal) — the same formula the
    shadow writer uses, so highlights/notes can reference segments even when
    the status is served from the task record.
    """
    if not payload:
        return {}
    document_id = payload.get("document_id")
    segments = payload.get("transcript_segments")
    if document_id and isinstance(segments, list):
        for index, seg in enumerate(segments):
            if isinstance(seg, dict) and seg.get("chunk_id") is None:
                seg["chunk_id"] = deterministic_chunk_id(document_id, index)
    return payload


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
def get_document_media(document_id: str, request: Request):
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
        media_type = media_type or "application/octet-stream"

        # HTTP Range support: <video> needs 206 partial responses to seek.
        range_header = request.headers.get("range")
        if range_header:
            return _range_response(media_file, media_type, range_header)

        return FileResponse(
            media_file,
            media_type=media_type,
            headers={"Accept-Ranges": "bytes"},
        )

    raise HTTPException(status_code=404, detail="Document not found")


def _range_response(media_file: Path, media_type: str, range_header: str):
    """Single-range bytes responder (RFC 7233), enough for media seeking."""
    file_size = media_file.stat().st_size
    try:
        unit, _, rng = range_header.partition("=")
        start_s, _, end_s = rng.partition("-")
        if unit.strip() != "bytes":
            raise ValueError("unsupported unit")
        start = int(start_s) if start_s.strip() else 0
        end = int(end_s) if end_s.strip() else file_size - 1
        end = min(end, file_size - 1)
        if start > end or start >= file_size:
            raise ValueError("out of bounds")
    except ValueError:
        return StreamingResponse(
            iter(()),
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    length = end - start + 1

    def iter_chunks(chunk_size: int = 64 * 1024):
        with open(media_file, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iter_chunks(),
        status_code=206,
        media_type=media_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        },
    )


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
        return TaskStatusResponse(**_with_chunk_ids(payload))
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/ai-profiles")
def get_ai_profiles():
    return get_ai_profiles_payload()


def _pending_translation_indices(task, cached_segments) -> list[int] | None:
    """Индексы кэшированных сегментов, которые нужно до-перевести.

    None — кэша нет или он не совпадает с транскриптом по длине,
    тогда переводим весь транскрипт с нуля.
    """
    if not isinstance(cached_segments, list) or not cached_segments:
        return None
    if len(cached_segments) != len(task.transcript_segments):
        return None
    pending: list[int] = []
    for i, seg in enumerate(cached_segments):
        enrichment = seg.get("enrichment") if isinstance(seg, dict) else None
        status = (
            enrichment.get("translation_status")
            if isinstance(enrichment, dict)
            else None
        )
        if status != TranscriptEnrichmentService.STATUS_READY:
            pending.append(i)
    return pending


# Резервный профиль для одноразового failover failed-сегментов:
# gemini* -> бесплатная модель OpenRouter, openrouter/or_* -> gemini_flash.
_FAILOVER_PROFILE_BY_PROVIDER = {
    "gemini": "or_ling_flash",
    "openrouter": "gemini_flash",
}


def _retry_failed_segments_with_failover(
    translated_segments: list,
    selected_profile,
    source_language: str | None,
    target_language: str,
) -> list:
    """Один раз до-перевести failed-сегменты резервным AI-профилем.

    Best-effort: любые ошибки (включая отсутствие API-ключа у резервного
    профиля) просто оставляют сегменты failed — запрос не падает.
    """
    failed_indices = [
        i
        for i, seg in enumerate(translated_segments)
        if isinstance(seg.get("enrichment"), dict)
        and seg["enrichment"].get("translation_status")
        == TranscriptEnrichmentService.STATUS_FAILED
    ]
    if not failed_indices:
        return translated_segments
    backup_id = _FAILOVER_PROFILE_BY_PROVIDER.get(selected_profile.provider)
    if not backup_id or backup_id == selected_profile.id:
        return translated_segments
    try:
        backup_profile, backup_provider = get_ai_provider(backup_id)
    except AIProviderConfigurationError:
        # Нет ключа для резервного профиля — failover тихо пропускаем.
        return translated_segments
    try:
        failover_service = TranscriptEnrichmentService(
            backup_provider,
            token_limits=get_limits(backup_profile.id),
        )
        subset = [translated_segments[i] for i in failed_indices]
        recovered = failover_service.enrich_segments(
            transcript_segments=subset,
            source_language=source_language,
            target_language=target_language,
        )
    except Exception as exc:
        print(f"[translate] failover to '{backup_id}' failed: {exc}")
        return translated_segments
    for i, seg in zip(failed_indices, recovered):
        translated_segments[i] = seg
    return translated_segments


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
    cached_segments = (
        cached_result.get("transcript_segments")
        if isinstance(cached_result, dict)
        else None
    )
    if isinstance(cached_segments, list) and cached_segments:
        statuses = [
            seg["enrichment"].get("translation_status")
            for seg in cached_segments
            if isinstance(seg, dict) and isinstance(seg.get("enrichment"), dict)
        ]
        # Полностью готовый кэш отдаём как есть; частичный (ready +
        # failed/not_generated) идёт в догрузку неготовых сегментов ниже.
        cache_complete = bool(statuses) and all(
            status == TranscriptEnrichmentService.STATUS_READY for status in statuses
        )
        if cache_complete:
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
        source_language = task.transcript_language or task.language
        pending_indices = _pending_translation_indices(task, cached_segments)
        if pending_indices is None:
            translated_segments = enrichment_service.enrich_segments(
                transcript_segments=task.transcript_segments,
                source_language=source_language,
                target_language=resolved_target_language,
            )
        else:
            # Частичный кэш: готовые сегменты сохраняем, переводим только
            # failed/not_generated и сливаем результат обратно.
            translated_segments = [dict(seg) for seg in cached_segments]
            subset = [translated_segments[i] for i in pending_indices]
            recovered = enrichment_service.enrich_segments(
                transcript_segments=subset,
                source_language=source_language,
                target_language=resolved_target_language,
            )
            for i, seg in zip(pending_indices, recovered):
                translated_segments[i] = seg
        translated_segments = _retry_failed_segments_with_failover(
            translated_segments,
            selected_profile,
            source_language,
            resolved_target_language,
        )
        # ← НОВОЕ: собираем полное полотно перевода
        full_translation = enrichment_service.build_full_translation(translated_segments)
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
        "full_translation": full_translation,   # ← НОВОЕ
    }
    task_manager.update(task_id, translation_results=translation_results)

    # Best-effort: переводы в knowledge layer, чтобы переживали
    # переоткрытие документа из библиотеки (чтение — KnowledgeReadService).
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
        full_translation=full_translation,   # ← НОВОЕ
    )


@router.post("/status/{task_id}/translation-import", response_model=TranslateTranscriptResponse)
def import_task_translation(task_id: str, req: ImportTranslationRequest):
    """Manual translation import: paste a full translation text and let the
    backend split it into segments automatically.
    """
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

    full_text = req.text.strip()
    if not full_text:
        raise HTTPException(status_code=422, detail="Translation text is empty")

    # Авто-разбиение вставленного текста на сегменты
    lines = _split_translation_text(full_text, len(task.transcript_segments))

    translated_segments: list[dict] = []
    for seg, line in zip(task.transcript_segments, lines):
        seg_dict = dict(seg)
        seg_dict["enrichment"] = {
            "translation": line,
            "translation_status": TranscriptEnrichmentService.STATUS_READY,
            "translation_error": None,
            "key_concepts": [],
            "entities": [],
            "tags": [],
            "extra": {},
        }
        translated_segments.append(seg_dict)

    full_translation = "\n\n".join(lines)
    cache_key = f"manual:{resolved_target_language.lower()}"
    translation_results = task.translation_results or {}
    translation_results[cache_key] = {
        "target_language": resolved_target_language,
        "ai_profile_id": "manual",
        "ai_profile_name": "Manual import",
        "ai_provider": "manual",
        "ai_model": "manual",
        "transcript_segments": translated_segments,
        "full_translation": full_translation,
    }
    task_manager.update(task_id, translation_results=translation_results)

    try:
        _get_knowledge_ingest().shadow_write_translations(task_manager.get(task_id))
    except Exception as shadow_exc:
        print(f"⚠️ Translation shadow write failed for task {task_id}: {shadow_exc}")

    return TranslateTranscriptResponse(
        task_id=task.id,
        target_language=resolved_target_language,
        ai_profile_id="manual",
        ai_profile_name="Manual import",
        transcript_segments=translated_segments,
        full_translation=full_translation,
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
    # Register the job so status polling and translation work for YouTube
    # tasks exactly as for file tasks.
    task_manager.create(task_id, source="youtube")

    uploaded_path: str | None = None
    audio_path: str | None = None
    transcript_path: str | None = None
    summary_path: str | None = None
    timings: dict[str, float] = {}
    selected_profile = None
    language: str | None = None

    try:
        selected_profile, provider = get_ai_provider(req.ai_profile)
        task_manager.update(
            task_id,
            ai_profile_id=selected_profile.id,
            ai_profile_name=selected_profile.display_name,
            ai_provider=selected_profile.provider,
            ai_model=selected_profile.model,
        )
        print(f"\n{'='*60}")
        print(f"TASK {task_id}: Processing YouTube URL (DEPRECATED)")
        print(f"URL: {req.url}")
        print(f"{'='*60}")
        
        print("STEP 1: Trying YouTube subtitles fast-path")
        transcribe_started = time.perf_counter()
        subtitles = fetch_youtube_subtitles(req.url, task_id, settings.audio_dir)
        if subtitles:
            transcript_segments = subtitles["segments"]
            transcript_language = subtitles.get("language")
            transcript = "\n".join(seg["text"] for seg in transcript_segments)
            timings["transcription_seconds"] = round(time.perf_counter() - transcribe_started, 3)
            print(
                f"STEP 1 done: using {subtitles['kind']} subtitles "
                f"({transcript_language}), {len(transcript_segments)} segments, "
                f"{timings['transcription_seconds']}s"
            )
        else:
            print("STEP 1: No subtitles available, downloading audio from YouTube")
            youtube_source = get_input_source(InputSourceType.YOUTUBE)
            audio_path = youtube_source.extract_audio(req.url, task_id, settings.audio_dir)

            print("STEP 2: Transcribing")
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
            language = chapter_result.get("language")

        timings["ai_seconds"] = round(time.perf_counter() - ai_started, 3)
        timings["total_seconds"] = round(time.perf_counter() - transcribe_started, 3)

        transcript_path = f"data/transcripts/{task_id}.txt"
        summary_path = f"data/summaries/{task_id}.txt"
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
            transcript_path=transcript_path,
            summary_path=summary_path,
            ai_profile_id=selected_profile.id,
            ai_profile_name=selected_profile.display_name,
            ai_provider=selected_profile.provider,
            ai_model=selected_profile.model,
        )
        task_manager.update(task_id, timings=timings)

        # Best-effort shadow write into the knowledge layer (ADR-0006).
        # Runs after set_result, so failures cannot affect the task outcome.
        try:
            document_id = _get_knowledge_ingest().shadow_write_task(
                task_manager.get(task_id), None, req.url
            )
            if document_id:
                task_manager.update(task_id, document_id=document_id)
        except Exception as shadow_exc:
            print(f"⚠️ Shadow write failed for task {task_id}: {shadow_exc}")

        print(f"✅ Task {task_id} completed successfully")
        print(f"{'='*60}\n")

        return VideoResponse(
            task_id=task_id,
            transcript=transcript,
            transcript_segments=transcript_segments,
            chapters=chapters,
            summary=summary,
            language=language,
            timings=timings,
        )

    except AIProviderConfigurationError as e:
        task_manager.set_error(task_id, str(e))
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        import traceback
        error_message = to_user_facing_ai_error(selected_profile, e) if selected_profile else str(e)
        task_manager.set_error(task_id, error_message)
        print(f"❌ Task {task_id} failed: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=error_message,
        )
    finally:
        # Keep transcript/summary artifacts: they are persistent results
        # referenced by the task record (see ADR-0002, C5).
        cleanup_service.cleanup(uploaded_path, audio_path)
        cleanup_service.cleanup_prefixed_files(settings.audio_dir, task_id)
