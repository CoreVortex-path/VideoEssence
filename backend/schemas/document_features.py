from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatConversationResponse(BaseModel):
    id: str
    document_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateChatConversationRequest(BaseModel):
    title: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class SendChatMessageRequest(BaseModel):
    message: str
    ai_profile: Optional[str] = None


class SendChatMessageResponse(BaseModel):
    conversation_id: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class NoteCreateRequest(BaseModel):
    chunk_id: Optional[str] = None
    selected_text: Optional[str] = None
    text: str


class NoteUpdateRequest(BaseModel):
    chunk_id: Optional[str] = None
    selected_text: Optional[str] = None
    text: str


class NoteResponse(BaseModel):
    id: str
    document_id: str
    chunk_id: Optional[str] = None
    selected_text: Optional[str] = None
    text: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HighlightCreateRequest(BaseModel):
    chunk_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str
    color: str


class HighlightUpdateRequest(BaseModel):
    chunk_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str
    color: str


class HighlightResponse(BaseModel):
    id: str
    document_id: str
    chunk_id: str
    start_offset: int
    end_offset: int
    text: str
    color: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SearchResultItem(BaseModel):
    source: Literal["transcript", "translation", "note"]
    chunk_id: Optional[str] = None
    matched_text: str
    position: int
    note_id: Optional[str] = None


class SearchResponse(BaseModel):
    document_id: str
    query: str
    results: list[SearchResultItem] = Field(default_factory=list)


class KnowledgeGraphResponse(BaseModel):
    document_id: str
    entities: list[dict]
    relations: list[dict]
    stats: dict
