from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Literal


class SegmentEntity(BaseModel):
    label: str
    value: str


class SegmentEnrichment(BaseModel):
    translation: Optional[str] = None
    translation_status: Literal["ready", "failed", "not_generated"] = "not_generated"
    translation_error: Optional[str] = None
    key_concepts: list[str] = Field(default_factory=list)
    entities: list[SegmentEntity] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    extra: dict[str, str] = Field(default_factory=dict)


class TranscriptSegment(BaseModel):
    start: float = Field(description="Segment start time in seconds")
    end: float = Field(description="Segment end time in seconds")
    text: str
    enrichment: Optional[SegmentEnrichment] = None


class Chapter(BaseModel):
    title: str
    summary: str
    start: float = Field(description="Chapter start time in seconds")


class ProcessMediaRequest(BaseModel):
    """Request to process local media file or YouTube URL.
    
    Primary input: file uploads via multipart/form-data
    Optional: YouTube URL support for backward compatibility
    """
    model_size: Optional[str] = Field("small", description="Whisper model size: tiny, small, medium, large")
    ai_profile: Optional[str] = Field("gemini_flash", description="AI profile id")


class ProcessMediaResponse(BaseModel):
    """Response with transcription and summary."""
    task_id: str
    transcript: str
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    summary: str
    language: Optional[str] = None
    source_type: str = Field(description="'file' or 'youtube'")


class VideoRequest(BaseModel):
    """Legacy: YouTube URL request (deprecated, use file upload instead)."""
    url: str
    ai_profile: Optional[str] = "gemini_flash"


class TaskResponse(BaseModel):
    """Legacy: Task response."""
    task_id: str
    status: str
