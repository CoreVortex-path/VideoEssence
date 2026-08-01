"""Task and knowledge persistence: interfaces, backends, and schemas."""

from .base import TaskStore
from .document_models import Document, document_from_dict, document_to_dict
from .document_store import DocumentStore, SqliteDocumentStore
from .json_store import JsonTaskStore
from .interaction_models import ChatConversation, ChatMessage, Highlight, Note
from .interaction_store import (
    ChatStore,
    HighlightStore,
    InteractionStore,
    NoteStore,
    SqliteInteractionStore,
)
from .knowledge_models import (
    Enrichment,
    KnowledgeChunk,
    chunk_from_dict,
    chunk_to_dict,
    enrichment_from_dict,
    enrichment_to_dict,
)
from .knowledge_store import KnowledgeStore, SqliteKnowledgeStore
from .models import Task, is_valid_task_id, task_from_dict, task_to_dict
from .sqlite_store import SqliteTaskStore

__all__ = [
    "Task",
    "TaskStore",
    "JsonTaskStore",
    "SqliteTaskStore",
    "Document",
    "DocumentStore",
    "SqliteDocumentStore",
    "KnowledgeChunk",
    "Enrichment",
    "KnowledgeStore",
    "SqliteKnowledgeStore",
    "is_valid_task_id",
    "task_from_dict",
    "task_to_dict",
    "document_from_dict",
    "document_to_dict",
    "chunk_from_dict",
    "chunk_to_dict",
    "enrichment_from_dict",
    "enrichment_to_dict",
    "default_document_store",
    "default_knowledge_store",
    "ChatConversation",
    "ChatMessage",
    "Note",
    "Highlight",
    "ChatStore",
    "NoteStore",
    "HighlightStore",
    "InteractionStore",
    "SqliteInteractionStore",
    "default_interaction_store",
]


def default_document_store() -> DocumentStore:
    """Composition root for document persistence (ADR-0005)."""
    from ...config.settings import settings

    return SqliteDocumentStore(settings.tasks_db_path)


def default_knowledge_store() -> KnowledgeStore:
    """Composition root for knowledge persistence (ADR-0005)."""
    from ...config.settings import settings

    return SqliteKnowledgeStore(settings.tasks_db_path)


def default_interaction_store() -> InteractionStore:
    """Composition root for notes/highlights/chat persistence."""
    from ...config.settings import settings

    return SqliteInteractionStore(settings.tasks_db_path)
