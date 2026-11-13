from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from fastapi import APIRouter, HTTPException, Query

from ..services.ai_provider import AIProviderConfigurationError, get_ai_provider
from ..services.document_features_service import (
    ChatService,
    FeatureNotFoundError,
    FeatureValidationError,
    HighlightsService,
    KnowledgeGraphService,
    NotesService,
    SearchService,
    search_hits_to_dict,
)
from ..services.knowledge_read_service import KnowledgeReadService
from ..services.storage import (
    ChatConversation,
    ChatMessage,
    Highlight,
    Note,
    default_document_store,
    default_interaction_store,
    default_knowledge_store,
    is_valid_task_id,
)
from ..schemas.document_features import (
    ChatConversationResponse,
    ChatMessageResponse,
    CreateChatConversationRequest,
    GlobalNoteCreateRequest,
    HighlightCreateRequest,
    HighlightResponse,
    HighlightUpdateRequest,
    KnowledgeGraphResponse,
    NoteCreateRequest,
    NoteResponse,
    NoteUpdateRequest,
    SearchResponse,
    SendAssistantMessageRequest,
    SendChatMessageRequest,
    SendChatMessageResponse,
)

router = APIRouter()

_chat_service: ChatService | None = None
_notes_service: NotesService | None = None
_highlights_service: HighlightsService | None = None
_search_service: SearchService | None = None
_knowledge_graph_service: KnowledgeGraphService | None = None


@contextmanager
def _handle_feature_errors() -> Generator[None, None, None]:
    """Translate domain exceptions to FastAPI HTTP responses.

    Catches in order: FeatureNotFoundError (→ 404), FeatureValidationError
    (→ 422), AIProviderConfigurationError (→ 422), RuntimeError (→ 500).
    HTTPException raised by _validate_id propagates untouched.
    """
    try:
        yield
    except FeatureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FeatureValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except AIProviderConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _validate_id(value: str, field_name: str) -> str:
    if not is_valid_task_id(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return value


def _to_conversation_response(item: ChatConversation) -> ChatConversationResponse:
    return ChatConversationResponse(
        id=item.id,
        document_id=item.document_id,
        title=item.title,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_message_response(item: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=item.id,
        conversation_id=item.conversation_id,
        role=item.role,
        content=item.content,
        created_at=item.created_at,
        metadata=item.metadata,
    )


def _to_note_response(item: Note) -> NoteResponse:
    return NoteResponse(
        id=item.id,
        document_id=item.document_id,
        chunk_id=item.chunk_id,
        selected_text=item.selected_text,
        text=item.text,
        tag=item.tag,
        page=item.page,
        position=item.position,
        video_time=item.video_time,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_highlight_response(item: Highlight) -> HighlightResponse:
    return HighlightResponse(
        id=item.id,
        document_id=item.document_id,
        chunk_id=item.chunk_id,
        start_offset=item.start_offset,
        end_offset=item.end_offset,
        text=item.text,
        color=item.color,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        documents = default_document_store()
        knowledge = default_knowledge_store()
        _chat_service = ChatService(
            documents=documents,
            interactions=default_interaction_store(),
            knowledge_reader=KnowledgeReadService(documents, knowledge),
            provider_factory=get_ai_provider,
        )
    return _chat_service


def _get_notes_service() -> NotesService:
    global _notes_service
    if _notes_service is None:
        _notes_service = NotesService(
            documents=default_document_store(),
            interactions=default_interaction_store(),
            knowledge=default_knowledge_store(),
        )
    return _notes_service


def _get_highlights_service() -> HighlightsService:
    global _highlights_service
    if _highlights_service is None:
        _highlights_service = HighlightsService(
            documents=default_document_store(),
            interactions=default_interaction_store(),
            knowledge=default_knowledge_store(),
        )
    return _highlights_service


def _get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService(
            documents=default_document_store(),
            knowledge=default_knowledge_store(),
            interactions=default_interaction_store(),
        )
    return _search_service


def _get_knowledge_graph_service() -> KnowledgeGraphService:
    global _knowledge_graph_service
    if _knowledge_graph_service is None:
        _knowledge_graph_service = KnowledgeGraphService()
    return _knowledge_graph_service


@router.post(
    "/documents/{document_id}/chat/conversations",
    response_model=ChatConversationResponse,
    status_code=201,
)
def create_chat_conversation(document_id: str, req: CreateChatConversationRequest):
    with _handle_feature_errors():
        conversation = _get_chat_service().create_conversation(
            _validate_id(document_id, "document_id"),
            req.title,
        )
        return _to_conversation_response(conversation)


@router.get(
    "/documents/{document_id}/chat/conversations",
    response_model=list[ChatConversationResponse],
)
def list_chat_conversations(document_id: str):
    with _handle_feature_errors():
        items = _get_chat_service().list_conversations(_validate_id(document_id, "document_id"))
        return [_to_conversation_response(item) for item in items]


@router.get(
    "/documents/{document_id}/chat/conversations/{conversation_id}/messages",
    response_model=list[ChatMessageResponse],
)
def list_chat_messages(document_id: str, conversation_id: str):
    with _handle_feature_errors():
        items = _get_chat_service().list_messages(
            _validate_id(document_id, "document_id"),
            _validate_id(conversation_id, "conversation_id"),
        )
        return [_to_message_response(item) for item in items]


@router.post(
    "/documents/{document_id}/chat/conversations/{conversation_id}/messages",
    response_model=SendChatMessageResponse,
)
def send_chat_message(document_id: str, conversation_id: str, req: SendChatMessageRequest):
    with _handle_feature_errors():
        user_message, assistant_message = _get_chat_service().answer(
            _validate_id(document_id, "document_id"),
            _validate_id(conversation_id, "conversation_id"),
            req.message,
            req.ai_profile,
        )
        return SendChatMessageResponse(
            conversation_id=conversation_id,
            user_message=_to_message_response(user_message),
            assistant_message=_to_message_response(assistant_message),
        )


@router.post(
    "/assistant/conversations",
    response_model=ChatConversationResponse,
    status_code=201,
)
def create_assistant_conversation(req: CreateChatConversationRequest):
    with _handle_feature_errors():
        conversation = _get_chat_service().create_global_conversation(req.title)
        return _to_conversation_response(conversation)


@router.get(
    "/assistant/conversations",
    response_model=list[ChatConversationResponse],
)
def list_assistant_conversations():
    with _handle_feature_errors():
        items = _get_chat_service().list_global_conversations()
        return [_to_conversation_response(item) for item in items]


@router.get(
    "/assistant/conversations/{conversation_id}/messages",
    response_model=list[ChatMessageResponse],
)
def list_assistant_messages(conversation_id: str):
    with _handle_feature_errors():
        items = _get_chat_service().list_global_messages(
            _validate_id(conversation_id, "conversation_id"),
        )
        return [_to_message_response(item) for item in items]


@router.post(
    "/assistant/conversations/{conversation_id}/messages",
    response_model=SendChatMessageResponse,
)
def send_assistant_message(conversation_id: str, req: SendAssistantMessageRequest):
    with _handle_feature_errors():
        user_message, assistant_message = _get_chat_service().answer_global(
            _validate_id(conversation_id, "conversation_id"),
            req.message,
            req.mode,
            req.ai_profile,
        )
        return SendChatMessageResponse(
            conversation_id=conversation_id,
            user_message=_to_message_response(user_message),
            assistant_message=_to_message_response(assistant_message),
        )


@router.post("/notes", response_model=NoteResponse, status_code=201)
def create_global_note(req: GlobalNoteCreateRequest):
    """Global note: document_id optional (a note may exist without a document)."""
    with _handle_feature_errors():
        document_id = _validate_id(req.document_id, "document_id") if req.document_id else None
        note = _get_notes_service().create(
            document_id,
            req.text,
            req.chunk_id,
            req.selected_text,
            tag=req.tag,
            page=req.page,
            position=req.position,
        )
        return _to_note_response(note)


@router.get("/notes", response_model=list[NoteResponse])
def list_global_notes(
    tag: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort: str = Query(default="updated_at_desc"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Global notes memory with backend-side filter/sort/pagination."""
    with _handle_feature_errors():
        items = _get_notes_service().list_global(
            tag=tag,
            document_id=_validate_id(document_id, "document_id") if document_id else None,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return [_to_note_response(item) for item in items]


@router.put("/notes/{note_id}", response_model=NoteResponse)
def update_global_note(note_id: str, req: NoteUpdateRequest):
    """Update text/tag of any note by id (incl. notes without a document)."""
    with _handle_feature_errors():
        note = _get_notes_service().update_global(
            _validate_id(note_id, "note_id"),
            req.text,
            tag=req.tag,
        )
        return _to_note_response(note)


@router.delete("/notes/{note_id}", status_code=204)
def delete_global_note(note_id: str):
    with _handle_feature_errors():
        _get_notes_service().delete_global(_validate_id(note_id, "note_id"))
        return None


@router.post("/documents/{document_id}/notes", response_model=NoteResponse, status_code=201)
def create_note(document_id: str, req: NoteCreateRequest):
    with _handle_feature_errors():
        note = _get_notes_service().create(
            _validate_id(document_id, "document_id"),
            req.text,
            req.chunk_id,
            req.selected_text,
            tag=req.tag,
            page=req.page,
            position=req.position,
            video_time=req.video_time,
        )
        return _to_note_response(note)


@router.get("/documents/{document_id}/notes", response_model=list[NoteResponse])
def list_notes(document_id: str):
    with _handle_feature_errors():
        items = _get_notes_service().list(_validate_id(document_id, "document_id"))
        return [_to_note_response(item) for item in items]


@router.get("/documents/{document_id}/notes/{note_id}", response_model=NoteResponse)
def get_note(document_id: str, note_id: str):
    with _handle_feature_errors():
        note = _get_notes_service().get(
            _validate_id(document_id, "document_id"),
            _validate_id(note_id, "note_id"),
        )
        return _to_note_response(note)


@router.put("/documents/{document_id}/notes/{note_id}", response_model=NoteResponse)
def update_note(document_id: str, note_id: str, req: NoteUpdateRequest):
    with _handle_feature_errors():
        note = _get_notes_service().update(
            _validate_id(document_id, "document_id"),
            _validate_id(note_id, "note_id"),
            req.text,
            req.chunk_id,
            req.selected_text,
            tag=req.tag,
            page=req.page,
            position=req.position,
            video_time=req.video_time,
        )
        return _to_note_response(note)


@router.delete("/documents/{document_id}/notes/{note_id}", status_code=204)
def delete_note(document_id: str, note_id: str):
    with _handle_feature_errors():
        _get_notes_service().delete(
            _validate_id(document_id, "document_id"),
            _validate_id(note_id, "note_id"),
        )
        return None


@router.post(
    "/documents/{document_id}/highlights",
    response_model=HighlightResponse,
    status_code=201,
)
def create_highlight(document_id: str, req: HighlightCreateRequest):
    with _handle_feature_errors():
        item = _get_highlights_service().create(
            _validate_id(document_id, "document_id"),
            req.chunk_id,
            req.start_offset,
            req.end_offset,
            req.text,
            req.color,
        )
        return _to_highlight_response(item)


@router.get("/documents/{document_id}/highlights", response_model=list[HighlightResponse])
def list_highlights(document_id: str):
    with _handle_feature_errors():
        items = _get_highlights_service().list(_validate_id(document_id, "document_id"))
        return [_to_highlight_response(item) for item in items]


@router.get(
    "/documents/{document_id}/highlights/{highlight_id}",
    response_model=HighlightResponse,
)
def get_highlight(document_id: str, highlight_id: str):
    with _handle_feature_errors():
        item = _get_highlights_service().get(
            _validate_id(document_id, "document_id"),
            _validate_id(highlight_id, "highlight_id"),
        )
        return _to_highlight_response(item)


@router.put(
    "/documents/{document_id}/highlights/{highlight_id}",
    response_model=HighlightResponse,
)
def update_highlight(document_id: str, highlight_id: str, req: HighlightUpdateRequest):
    with _handle_feature_errors():
        item = _get_highlights_service().update(
            _validate_id(document_id, "document_id"),
            _validate_id(highlight_id, "highlight_id"),
            req.chunk_id,
            req.start_offset,
            req.end_offset,
            req.text,
            req.color,
        )
        return _to_highlight_response(item)


@router.delete("/documents/{document_id}/highlights/{highlight_id}", status_code=204)
def delete_highlight(document_id: str, highlight_id: str):
    with _handle_feature_errors():
        _get_highlights_service().delete(
            _validate_id(document_id, "document_id"),
            _validate_id(highlight_id, "highlight_id"),
        )
        return None


@router.get("/documents/{document_id}/search", response_model=SearchResponse)
def search_document(
    document_id: str,
    q: str = Query(..., min_length=1),
    transcript: bool = True,
    translation: bool = True,
    notes: bool = True,
):
    with _handle_feature_errors():
        hits = _get_search_service().search(
            _validate_id(document_id, "document_id"),
            q,
            include_transcript=transcript,
            include_translation=translation,
            include_notes=notes,
        )
        return SearchResponse(
            document_id=document_id,
            query=q,
            results=search_hits_to_dict(hits),
        )


@router.get("/documents/{document_id}/knowledge-graph", response_model=KnowledgeGraphResponse)
def get_knowledge_graph(document_id: str):
    document_id = _validate_id(document_id, "document_id")
    return KnowledgeGraphResponse(**_get_knowledge_graph_service().get_document_graph(document_id))
