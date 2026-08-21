from __future__ import annotations

import math
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from .ai_provider import AIProfile, AIProviderConfigurationError, to_user_facing_ai_error
from .ai_text_generator import AITextGenerator
from .knowledge_read_service import KnowledgeReadService
from ..config.ai_token_limits import get_limits
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


# Sentinel document_id for assistant conversations that are not tied to any
# document (global AI assistant). The column is NOT NULL but has no FK, and
# the value passes the safe-id check.
GLOBAL_DOCUMENT_ID = "global"

# Modes of the global assistant: search across the whole knowledge library,
# or a plain general-purpose chat without any retrieval.
ASSISTANT_MODES = ("library", "general")

# Translation matches weigh less than original-text matches: the translation
# is generated text and may drift from the user's wording.
TRANSLATION_MATCH_WEIGHT = 0.8

# Max chunks per single document in library-mode retrieval, so one large
# document cannot fill the whole context window.
LIBRARY_PER_DOCUMENT_LIMIT = 3

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _normalize_tokens(text: str) -> list[str]:
    """Lower-cased word tokens with surrounding punctuation stripped."""
    return _WORD_RE.findall((text or "").lower())


def _token_stem(token: str) -> str:
    """Crude stem for ru/en: drop up to 2 trailing chars from longer tokens."""
    if len(token) <= 5:
        return token
    return token[: max(5, len(token) - 2)]


def _tokens_match(a: str, b: str) -> bool:
    """Exact match, prefix match (min length 4), or shared crude stem."""
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    if len(a) >= 6 and len(b) >= 6:
        stem_a, stem_b = _token_stem(a), _token_stem(b)
        return stem_a == stem_b or stem_a.startswith(stem_b) or stem_b.startswith(stem_a)
    return False


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

        all_chunks = context.get("chunks") or []
        if not all_chunks:
            raise FeatureNotFoundError("No chunks available for this document")
        # Zero overlap is not an error: the answer is built with an explicit
        # "no relevant fragments" note in the prompt instead of silently
        # falling back to the first chunks.
        selected_chunks = self._select_relevant_chunks(text, all_chunks)

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
        selected_profile: AIProfile | None = None
        try:
            selected_profile, provider = self._provider_factory(ai_profile)
            # max_tokens обязателен для OpenRouter-провайдера
            answer_text = provider.generate_text(
                prompt, max_tokens=get_limits(selected_profile.id).CHAT
            )
        except AIProviderConfigurationError:
            raise
        except Exception as exc:
            raise RuntimeError(
                to_user_facing_ai_error(selected_profile, exc)
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
                "retrieval_strategy": (
                    "keyword-overlap-v2" if selected_chunks else "none-matched"
                ),
                "matched_chunks": len(selected_chunks),
            },
        )
        self._interactions.save_message(assistant_message)

        conversation.updated_at = assistant_message.created_at
        self._interactions.save_conversation(conversation)
        return user_message, assistant_message

    # --- Global assistant (not tied to any document) ---

    def create_global_conversation(self, title: str | None = None) -> ChatConversation:
        now = _utc_now_iso()
        conversation = ChatConversation(
            id=str(uuid.uuid4()),
            document_id=GLOBAL_DOCUMENT_ID,
            title=title.strip() if title else None,
            created_at=now,
            updated_at=now,
        )
        self._interactions.save_conversation(conversation)
        return conversation

    def list_global_conversations(self) -> list[ChatConversation]:
        return self._interactions.list_conversations(GLOBAL_DOCUMENT_ID)

    def list_global_messages(self, conversation_id: str) -> list[ChatMessage]:
        conversation = self._get_global_conversation(conversation_id)
        return self._interactions.list_messages(conversation.id)

    def answer_global(
        self,
        conversation_id: str,
        message_text: str,
        mode: str = "library",
        ai_profile: str | None = None,
    ) -> tuple[ChatMessage, ChatMessage]:
        text = (message_text or "").strip()
        if not text:
            raise FeatureValidationError("message must not be empty")
        if mode not in ASSISTANT_MODES:
            raise FeatureValidationError(
                f"Unknown assistant mode {mode!r}; expected one of {ASSISTANT_MODES}"
            )
        conversation = self._get_global_conversation(conversation_id)

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
        selected_chunks: list[dict[str, Any]] = []
        if mode == "library":
            library_chunks = self._knowledge_reader.get_library_chunks()
            selected_chunks = self._select_relevant_chunks(
                text, library_chunks, per_document_limit=LIBRARY_PER_DOCUMENT_LIMIT
            )
            prompt = self._build_library_prompt(selected_chunks, history)
        else:
            prompt = self._build_general_prompt(history)

        selected_profile: AIProfile | None = None
        try:
            selected_profile, provider = self._provider_factory(ai_profile)
            # max_tokens обязателен для OpenRouter-провайдера
            answer_text = provider.generate_text(
                prompt, max_tokens=get_limits(selected_profile.id).CHAT
            )
        except AIProviderConfigurationError:
            raise
        except Exception as exc:
            raise RuntimeError(
                to_user_facing_ai_error(selected_profile, exc)
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
                "assistant_mode": mode,
                "source_chunk_ids": [chunk["chunk_id"] for chunk in selected_chunks],
                "source_documents": sorted(
                    {chunk["doc_title"] for chunk in selected_chunks}
                ),
                "retrieval_strategy": (
                    "none"
                    if mode != "library"
                    else ("keyword-overlap-v2" if selected_chunks else "none-matched")
                ),
                "matched_chunks": len(selected_chunks),
            },
        )
        self._interactions.save_message(assistant_message)

        conversation.updated_at = assistant_message.created_at
        self._interactions.save_conversation(conversation)
        return user_message, assistant_message

    def _get_global_conversation(self, conversation_id: str) -> ChatConversation:
        conversation = self._interactions.load_conversation(conversation_id)
        if conversation is None:
            raise FeatureNotFoundError("Conversation not found")
        if conversation.document_id != GLOBAL_DOCUMENT_ID:
            raise FeatureValidationError("Conversation is not a global assistant conversation")
        return conversation

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
    def _history_lines(history: list[ChatMessage]) -> list[str]:
        return [
            f"{item.role.upper()}: {item.content}"
            for item in history[-8:]
        ]

    @staticmethod
    def _build_prompt(
        context: dict[str, Any],
        selected_chunks: list[dict[str, Any]],
        history: list[ChatMessage],
    ) -> str:
        history_lines = ChatService._history_lines(history)
        summary = context.get("summary") or "No summary available"
        if selected_chunks:
            chunks_section = "Relevant chunks:\n" + "\n".join(
                f"[{chunk['chunk_id']}] {chunk['text']}"
                for chunk in selected_chunks
            )
        else:
            chunks_section = (
                "No relevant fragments were found in this document for the "
                "user's question. Answer from your general knowledge (the "
                "document summary above may still help) and explicitly say "
                "that the document materials do not cover this question."
            )
        return (
            "You are a helpful assistant answering from the provided document context.\n"
            "If context is insufficient, explicitly say it.\n\n"
            f"Document title: {context.get('title') or 'Untitled'}\n"
            f"Document language: {context.get('primary_language') or 'unknown'}\n"
            f"Document summary: {summary}\n\n"
            + chunks_section
            + "\n\nConversation history:\n"
            + "\n".join(history_lines)
            + "\n\nAnswer the latest USER message."
        )

    @staticmethod
    def _build_library_prompt(
        selected_chunks: list[dict[str, Any]],
        history: list[ChatMessage],
    ) -> str:
        history_lines = ChatService._history_lines(history)
        if selected_chunks:
            excerpts = "\n".join(
                f"[{chunk['doc_title']} | {chunk['chunk_id']}] {chunk['text']}"
                for chunk in selected_chunks
            )
        else:
            excerpts = "No relevant excerpts found in the library."
        return (
            "You are a helpful AI assistant with access to the user's video library.\n"
            "Answer using the library excerpts below when they are relevant. "
            "When the excerpts do not cover the question, answer from your general "
            "knowledge and briefly mention that the library has nothing on this topic.\n"
            "Answer in the same language as the user's message.\n\n"
            f"Library excerpts:\n{excerpts}\n\n"
            "Conversation history:\n"
            + "\n".join(history_lines)
            + "\n\nAnswer the latest USER message."
        )

    @staticmethod
    def _build_general_prompt(history: list[ChatMessage]) -> str:
        history_lines = ChatService._history_lines(history)
        return (
            "You are a helpful general-purpose AI assistant. Answer clearly and concisely.\n"
            "If you do not know something, say so honestly. "
            "Answer in the same language as the user's message.\n\n"
            "Conversation history:\n"
            + "\n".join(history_lines)
            + "\n\nAnswer the latest USER message."
        )

    @staticmethod
    def _count_matches(q_terms: set[str], text: str) -> int:
        """How many question terms match this text (exact / prefix / stem)."""
        tokens = set(_normalize_tokens(text))
        if not tokens:
            return 0
        # Bucket by first 4 chars: any fuzzy match (prefix or stem) always
        # shares a 4-char head, so we never compare full token lists.
        buckets: dict[str, list[str]] = {}
        for token in tokens:
            if len(token) >= 4:
                buckets.setdefault(token[:4], []).append(token)
        hits = 0
        for term in q_terms:
            if term in tokens:
                hits += 1
            elif len(term) >= 4 and any(
                _tokens_match(term, candidate)
                for candidate in buckets.get(term[:4], ())
            ):
                hits += 1
        return hits

    @staticmethod
    def _chunk_score(q_terms: set[str], chunk: dict[str, Any]) -> float:
        text_hits = ChatService._count_matches(q_terms, str(chunk.get("text") or ""))
        translation = str(chunk.get("translation") or "")
        translation_hits = (
            ChatService._count_matches(q_terms, translation) if translation else 0
        )
        return text_hits + TRANSLATION_MATCH_WEIGHT * translation_hits

    @staticmethod
    def _select_relevant_chunks(
        question: str,
        chunks: list[dict[str, Any]],
        top_k: int = 8,
        per_document_limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Score chunks by token overlap with the question; best first.

        Returns an empty list when nothing matched — callers must handle the
        no-match case explicitly instead of silently using the first chunks.
        """
        q_terms = {t for t in _normalize_tokens(question) if len(t) > 2}
        if not q_terms:
            return []
        scored = [
            (ChatService._chunk_score(q_terms, chunk), -index, chunk)
            for index, chunk in enumerate(chunks)
        ]
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        picked: list[dict[str, Any]] = []
        per_document: dict[str, int] = {}
        for score, _neg_index, chunk in scored:
            if score <= 0 or len(picked) >= top_k:
                break
            if per_document_limit is not None:
                doc_key = str(chunk.get("document_id") or "")
                if per_document.get(doc_key, 0) >= per_document_limit:
                    continue
                per_document[doc_key] = per_document.get(doc_key, 0) + 1
            picked.append(chunk)
        return picked


class NotesService:
    # position = [x, y] in PDF points, origin top-left (PyMuPDF convention).
    _NOTE_SORTS = {
        "created_at_asc": ("created_at", False),
        "created_at_desc": ("created_at", True),
        "updated_at_asc": ("updated_at", False),
        "updated_at_desc": ("updated_at", True),
        "tag_asc": ("tag", False),
        "document_id": ("document_id", False),
    }

    def __init__(
        self,
        documents: DocumentStore,
        interactions: NoteStore,
        knowledge: KnowledgeStore,
    ) -> None:
        self._documents = documents
        self._interactions = interactions
        self._knowledge = knowledge

    @staticmethod
    def _validate_anchor(page: int | None, position: list[float] | None) -> None:
        if page is not None and page < 1:
            raise FeatureValidationError("page must be >= 1")
        if position is None:
            return
        if page is None:
            raise FeatureValidationError("position requires page")
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 2
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in position)
        ):
            raise FeatureValidationError("position must be [x, y] of finite numbers")

    def create(
        self,
        document_id: str | None,
        text: str,
        chunk_id: str | None,
        selected_text: str | None,
        tag: str | None = None,
        page: int | None = None,
        position: list[float] | None = None,
    ) -> Note:
        if document_id:
            self._require_document(document_id)
        note_text = (text or "").strip()
        if not note_text:
            raise FeatureValidationError("text must not be empty")
        if chunk_id:
            if not document_id:
                raise FeatureValidationError("chunk_id requires document_id")
            _validate_chunk_belongs_to_document(self._knowledge, document_id, chunk_id)
        self._validate_anchor(page, position)
        now = _utc_now_iso()
        note = Note(
            id=str(uuid.uuid4()),
            document_id=document_id,
            chunk_id=chunk_id,
            selected_text=selected_text,
            text=note_text,
            tag=(tag or "").strip() or None,
            page=page,
            position=[float(v) for v in position] if position is not None else None,
            created_at=now,
            updated_at=now,
        )
        self._interactions.save_note(note)
        return note

    def list(self, document_id: str) -> list[Note]:
        self._require_document(document_id)
        return self._interactions.list_notes(document_id)

    def list_global(
        self,
        tag: str | None = None,
        document_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "updated_at_desc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Note]:
        """Backend-side filter/sort/paginate over all notes (global memory)."""
        if sort not in self._NOTE_SORTS:
            raise FeatureValidationError(
                f"Invalid sort; expected one of {sorted(self._NOTE_SORTS)}"
            )
        tag_norm = (tag or "").strip().lower() or None
        from_day = (date_from or "")[:10] or None
        to_day = (date_to or "")[:10] or None

        notes = self._interactions.list_all_notes()
        if tag_norm is not None:
            notes = [n for n in notes if (n.tag or "").strip().lower() == tag_norm]
        if document_id:
            notes = [n for n in notes if n.document_id == document_id]
        if from_day:
            notes = [n for n in notes if (n.created_at or "")[:10] >= from_day]
        if to_day:
            notes = [n for n in notes if (n.created_at or "")[:10] <= to_day]

        field, reverse = self._NOTE_SORTS[sort]
        notes.sort(key=lambda n: getattr(n, field) or "", reverse=reverse)
        return notes[offset : offset + limit]

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
        tag: str | None = None,
        page: int | None = None,
        position: list[float] | None = None,
    ) -> Note:
        note = self.get(document_id, note_id)
        note_text = (text or "").strip()
        if not note_text:
            raise FeatureValidationError("text must not be empty")
        if chunk_id:
            _validate_chunk_belongs_to_document(self._knowledge, document_id, chunk_id)
        self._validate_anchor(page, position)
        note.text = note_text
        note.chunk_id = chunk_id
        note.selected_text = selected_text
        # tag/page/position: None keeps the current value, "" clears the tag.
        if tag is not None:
            note.tag = tag.strip() or None
        if page is not None:
            note.page = page
        if position is not None:
            note.position = [float(v) for v in position]
        note.updated_at = _utc_now_iso()
        self._interactions.save_note(note)
        return note

    def get_global(self, note_id: str) -> Note:
        note = self._interactions.load_note(note_id)
        if note is None:
            raise FeatureNotFoundError("Note not found")
        return note

    def update_global(
        self,
        note_id: str,
        text: str,
        tag: str | None = None,
    ) -> Note:
        """Update a note by id without a document scope (global notes memory).

        Only content and tag are editable here; the navigation anchor
        (document/page/position) is immutable after creation.
        """
        note = self.get_global(note_id)
        note_text = (text or "").strip()
        if not note_text:
            raise FeatureValidationError("text must not be empty")
        note.text = note_text
        if tag is not None:
            note.tag = tag.strip() or None
        note.updated_at = _utc_now_iso()
        self._interactions.save_note(note)
        return note

    def delete_global(self, note_id: str) -> None:
        self.get_global(note_id)
        if not self._interactions.delete_note(note_id):
            raise FeatureNotFoundError("Note not found")

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
