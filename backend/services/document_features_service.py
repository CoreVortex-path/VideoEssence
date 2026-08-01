from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from .ai_provider import AIProfile, AIProviderConfigurationError, to_user_facing_ai_error
from .ai_text_generator import AITextGenerator
from .knowledge_read_service import KnowledgeReadService
from .storage import (
    ChatConversation,
    ChatMessage,
    ChatStore,
    DocumentStore,
    Highlight,
    HighlightStore,
    KnowledgeStore,
    Note,
    NoteStore,
)

# Factory type: accepts an optional profile id string, returns (profile, generator).
ProviderFactory = Callable[[Optional[str]], tuple[AIProfile, AITextGenerator]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_chunk_belongs_to_document(
    knowledge: KnowledgeStore,
    document_id: str,
    chunk_id: str,
) -> None:
    """Raise FeatureValidationError if chunk_id is not in this document's chunk set."""
    chunks = knowledge.load_chunks(document_id)
    if not any(c.id == chunk_id for c in chunks):
        raise FeatureValidationError("chunk_id does not belong to this document")


class FeatureNotFoundError(RuntimeError):
    pass


class FeatureValidationError(ValueError):
    pass


@dataclass
class SearchHit:
    source: str
    chunk_id: str | None
    matched_text: str
    position: int
    note_id: str | None = None


class ChatService:
    def __init__(
        self,
        documents: DocumentStore,
        interactions: ChatStore,
        knowledge_reader: KnowledgeReadService,
        provider_factory: ProviderFactory,
    ) -> None:
        self._documents = documents
        self._interactions = interactions
        self._knowledge_reader = knowledge_reader
        self._provider_factory = provider_factory

    def create_conversation(self, document_id: str, title: str | None = None) -> ChatConversation:
        self._require_document(document_id)
        now = _utc_now_iso()
        conversation = ChatConversation(
            id=str(uuid.uuid4()),
            document_id=document_id,
            title=title.strip() if title else None,
            created_at=now,
            updated_at=now,
        )
        self._interactions.save_conversation(conversation)
        return conversation

    def list_conversations(self, document_id: str) -> list[ChatConversation]:
        self._require_document(document_id)
        return self._interactions.list_conversations(document_id)

    def list_messages(self, document_id: str, conversation_id: str) -> list[ChatMessage]:
        conversation = self._get_conversation(document_id, conversation_id)
        return self._interactions.list_messages(conversation.id)

    def answer(
        self,
        document_id: str,
        conversation_id: str,
        message_text: str,
        ai_profile: str | None = None,
    ) -> tuple[ChatMessage, ChatMessage]:
        text = (message_text or "").strip()
        if not text:
            raise FeatureValidationError("message must not be empty")
        conversation = self._get_conversation(document_id, conversation_id)
        context = self._knowledge_reader.get_document_context(document_id)
        if context is None:
            raise FeatureNotFoundError("Document knowledge context is unavailable")

        selected_chunks = self._select_relevant_chunks(text, context.get("chunks") or [])
        if not selected_chunks:
            raise FeatureNotFoundError("No chunks available for this document")

        now = _utc_now_iso()
        user_message = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            role="user",
            content=text,
            created_at=now,
            metadata={},
        )
        self._interactions.save_message(user_message)

        history = self._interactions.list_messages(conversation.id)
        prompt = self._build_prompt(context, selected_chunks, history)
        try:
            selected_profile, provider = self._provider_factory(ai_profile)
            answer_text = provider.generate_text(prompt)
        except AIProviderConfigurationError:
            raise
        except Exception as exc:
            raise RuntimeError(
                to_user_facing_ai_error(None, exc)
            ) from exc

        assistant_message = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            role="assistant",
            content=answer_text.strip(),
            created_at=_utc_now_iso(),
            metadata={
                "ai_profile_id": selected_profile.id,
                "ai_profile_name": selected_profile.display_name,
                "ai_provider": selected_profile.provider,
                "ai_model": selected_profile.model,
                "source_chunk_ids": [chunk["chunk_id"] for chunk in selected_chunks],
                "retrieval_strategy": "keyword-overlap-v1",
            },
        )
        self._interactions.save_message(assistant_message)

        conversation.updated_at = assistant_message.created_at
        self._interactions.save_conversation(conversation)
        return user_message, assistant_message

    def _get_conversation(self, document_id: str, conversation_id: str) -> ChatConversation:
        self._require_document(document_id)
        conversation = self._interactions.load_conversation(conversation_id)
        if conversation is None:
            raise FeatureNotFoundError("Conversation not found")
        if conversation.document_id != document_id:
            raise FeatureValidationError("Conversation does not belong to this document")
        return conversation

    def _require_document(self, document_id: str) -> None:
        if self._documents.load(document_id) is None:
            raise FeatureNotFoundError("Document not found")

    @staticmethod
    def _build_prompt(
        context: dict[str, Any],
        selected_chunks: list[dict[str, Any]],
        history: list[ChatMessage],
    ) -> str:
        history_tail = history[-8:]
        history_lines = [
            f"{item.role.upper()}: {item.content}"
            for item in history_tail
        ]
        chunk_lines = [
            f"[{chunk['chunk_id']}] {chunk['text']}"
            for chunk in selected_chunks
        ]
        summary = context.get("summary") or "No summary available"
        return (
            "You are a helpful assistant answering strictly from the provided document context.\n"
            "If context is insufficient, explicitly say it.\n\n"
            f"Document title: {context.get('title') or 'Untitled'}\n"
            f"Document language: {context.get('primary_language') or 'unknown'}\n"
            f"Document summary: {summary}\n\n"
            "Relevant chunks:\n"
            + "\n".join(chunk_lines)
            + "\n\nConversation history:\n"
            + "\n".join(history_lines)
            + "\n\nAnswer the latest USER message."
        )

    @staticmethod
    def _select_relevant_chunks(
        question: str,
        chunks: list[dict[str, Any]],
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        q_terms = {token.lower() for token in question.split() if len(token.strip()) > 2}
        scored: list[tuple[int, int, dict[str, Any]]] = []
        for index, chunk in enumerate(chunks):
            text = str(chunk.get("text") or "")
            terms = {token.lower() for token in text.split()}
            overlap = len(q_terms.intersection(terms)) if q_terms else 0
            scored.append((overlap, -index, chunk))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        picked = [item[2] for item in scored[:top_k] if item[0] > 0]
        if picked:
            return picked
        return chunks[:top_k]


class NotesService:
    def __init__(
        self,
        documents: DocumentStore,
        interactions: NoteStore,
        knowledge: KnowledgeStore,
    ) -> None:
        self._documents = documents
        self._interactions = interactions
        self._knowledge = knowledge

    def create(
        self,
        document_id: str,
        text: str,
        chunk_id: str | None,
        selected_text: str | None,
    ) -> Note:
        self._require_document(document_id)
        note_text = (text or "").strip()
        if not note_text:
            raise FeatureValidationError("text must not be empty")
        if chunk_id:
            _validate_chunk_belongs_to_document(self._knowledge, document_id, chunk_id)
        now = _utc_now_iso()
        note = Note(
            id=str(uuid.uuid4()),
            document_id=document_id,
            chunk_id=chunk_id,
            selected_text=selected_text,
            text=note_text,
            created_at=now,
            updated_at=now,
        )
        self._interactions.save_note(note)
        return note

    def list(self, document_id: str) -> list[Note]:
        self._require_document(document_id)
        return self._interactions.list_notes(document_id)

    def get(self, document_id: str, note_id: str) -> Note:
        self._require_document(document_id)
        note = self._interactions.load_note(note_id)
        if note is None or note.document_id != document_id:
            raise FeatureNotFoundError("Note not found")
        return note

    def update(
        self,
        document_id: str,
        note_id: str,
        text: str,
        chunk_id: str | None,
        selected_text: str | None,
    ) -> Note:
        note = self.get(document_id, note_id)
        note_text = (text or "").strip()
        if not note_text:
            raise FeatureValidationError("text must not be empty")
        if chunk_id:
            _validate_chunk_belongs_to_document(self._knowledge, document_id, chunk_id)
        note.text = note_text
        note.chunk_id = chunk_id
        note.selected_text = selected_text
        note.updated_at = _utc_now_iso()
        self._interactions.save_note(note)
        return note

    def delete(self, document_id: str, note_id: str) -> None:
        self.get(document_id, note_id)
        if not self._interactions.delete_note(note_id):
            raise FeatureNotFoundError("Note not found")

    def _require_document(self, document_id: str) -> None:
        if self._documents.load(document_id) is None:
            raise FeatureNotFoundError("Document not found")


class HighlightsService:
    def __init__(
        self,
        documents: DocumentStore,
        interactions: HighlightStore,
        knowledge: KnowledgeStore,
    ) -> None:
        self._documents = documents
        self._interactions = interactions
        self._knowledge = knowledge

    def create(
        self,
        document_id: str,
        chunk_id: str,
        start_offset: int,
        end_offset: int,
        text: str,
        color: str,
    ) -> Highlight:
        self._require_document(document_id)
        clean_text = (text or "").strip()
        clean_color = (color or "").strip()
        if not chunk_id:
            raise FeatureValidationError("chunk_id must not be empty")
        if start_offset < 0 or end_offset <= start_offset:
            raise FeatureValidationError("Invalid highlight range")
        if not clean_text:
            raise FeatureValidationError("text must not be empty")
        if not clean_color:
            raise FeatureValidationError("color must not be empty")
        _validate_chunk_belongs_to_document(self._knowledge, document_id, chunk_id)
        now = _utc_now_iso()
        highlight = Highlight(
            id=str(uuid.uuid4()),
            document_id=document_id,
            chunk_id=chunk_id,
            start_offset=start_offset,
            end_offset=end_offset,
            text=clean_text,
            color=clean_color,
            created_at=now,
            updated_at=now,
        )
        self._interactions.save_highlight(highlight)
        return highlight

    def list(self, document_id: str) -> list[Highlight]:
        self._require_document(document_id)
        return self._interactions.list_highlights(document_id)

    def get(self, document_id: str, highlight_id: str) -> Highlight:
        self._require_document(document_id)
        highlight = self._interactions.load_highlight(highlight_id)
        if highlight is None or highlight.document_id != document_id:
            raise FeatureNotFoundError("Highlight not found")
        return highlight

    def update(
        self,
        document_id: str,
        highlight_id: str,
        chunk_id: str,
        start_offset: int,
        end_offset: int,
        text: str,
        color: str,
    ) -> Highlight:
        highlight = self.get(document_id, highlight_id)
        clean_text = (text or "").strip()
        clean_color = (color or "").strip()
        if not chunk_id:
            raise FeatureValidationError("chunk_id must not be empty")
        if start_offset < 0 or end_offset <= start_offset:
            raise FeatureValidationError("Invalid highlight range")
        if not clean_text:
            raise FeatureValidationError("text must not be empty")
        if not clean_color:
            raise FeatureValidationError("color must not be empty")
        _validate_chunk_belongs_to_document(self._knowledge, document_id, chunk_id)
        highlight.chunk_id = chunk_id
        highlight.start_offset = start_offset
        highlight.end_offset = end_offset
        highlight.text = clean_text
        highlight.color = clean_color
        highlight.updated_at = _utc_now_iso()
        self._interactions.save_highlight(highlight)
        return highlight

    def delete(self, document_id: str, highlight_id: str) -> None:
        self.get(document_id, highlight_id)
        if not self._interactions.delete_highlight(highlight_id):
            raise FeatureNotFoundError("Highlight not found")

    def _require_document(self, document_id: str) -> None:
        if self._documents.load(document_id) is None:
            raise FeatureNotFoundError("Document not found")


class SearchService:
    def __init__(
        self,
        documents: DocumentStore,
        knowledge: KnowledgeStore,
        interactions: NoteStore,
    ) -> None:
        self._documents = documents
        self._knowledge = knowledge
        self._interactions = interactions

    def search(
        self,
        document_id: str,
        query: str,
        include_transcript: bool = True,
        include_translation: bool = True,
        include_notes: bool = True,
    ) -> list[SearchHit]:
        if self._documents.load(document_id) is None:
            raise FeatureNotFoundError("Document not found")
        q = (query or "").strip()
        if not q:
            raise FeatureValidationError("query must not be empty")

        hits: list[SearchHit] = []
        lower_q = q.lower()
        chunks = self._knowledge.load_chunks(document_id)

        if include_transcript:
            for chunk in chunks:
                hits.extend(
                    SearchHit(
                        source="transcript",
                        chunk_id=chunk.id,
                        matched_text=chunk.text[pos : pos + len(q)],
                        position=pos,
                    )
                    for pos in _find_positions(chunk.text, lower_q)
                )

        if include_translation:
            for chunk in chunks:
                enrichments = self._knowledge.load_enrichments("chunk", chunk.id, type="translation")
                if not enrichments:
                    continue
                translation = (enrichments[0].payload or {}).get("text")
                if not isinstance(translation, str):
                    continue
                hits.extend(
                    SearchHit(
                        source="translation",
                        chunk_id=chunk.id,
                        matched_text=translation[pos : pos + len(q)],
                        position=pos,
                    )
                    for pos in _find_positions(translation, lower_q)
                )

        if include_notes:
            notes = self._interactions.list_notes(document_id)
            for note in notes:
                note_text = note.text or ""
                hits.extend(
                    SearchHit(
                        source="note",
                        chunk_id=note.chunk_id,
                        matched_text=note_text[pos : pos + len(q)],
                        position=pos,
                        note_id=note.id,
                    )
                    for pos in _find_positions(note_text, lower_q)
                )

        return sorted(hits, key=lambda item: (item.position, item.source))


class KnowledgeGraphService:
    def get_document_graph(self, document_id: str) -> dict[str, Any]:
        return {
            "document_id": document_id,
            "entities": [
                {"id": "entity-1", "label": "Product", "type": "concept"},
                {"id": "entity-2", "label": "User", "type": "actor"},
                {"id": "entity-3", "label": "Backend API", "type": "system"},
            ],
            "relations": [
                {"from": "entity-2", "to": "entity-1", "type": "uses"},
                {"from": "entity-3", "to": "entity-1", "type": "serves"},
            ],
            "stats": {
                "entity_count": 3,
                "relation_count": 2,
                "status": "mock",
            },
        }


def _find_positions(text: str, lowered_query: str) -> Iterable[int]:
    lower_text = (text or "").lower()
    start = 0
    while True:
        pos = lower_text.find(lowered_query, start)
        if pos < 0:
            break
        yield pos
        start = pos + 1


def search_hits_to_dict(items: list[SearchHit]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]
