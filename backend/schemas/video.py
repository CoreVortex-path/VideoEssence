from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Literal


class TranscriptSegment(BaseModel):
    start: float = Field(description="Segment start time in seconds")
    end: float = Field(description="Segment end time in seconds")
    text: str


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
    provider: Optional[str] = None


class TaskResponse(BaseModel):
    """Legacy: Task response."""
    task_id: str
    status: str
