#!/usr/bin/env python3
"""
Tests for document-scoped chat, notes, highlights, search, and knowledge-graph stub APIs.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _seed_document(tmp: str):
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore, Task

    db = Path(tmp) / "videobrain.db"
    documents = SqliteDocumentStore(db)
    knowledge = SqliteKnowledgeStore(db)
    task = Task(
        id="task-seed",
        source="file",
        status="completed",
        transcript="Hello world\nTranslated idea",
        transcript_segments=[
            {"start": 0.0, "end": 1.0, "text": "Hello world"},
            {"start": 1.0, "end": 2.0, "text": "Translated idea"},
        ],
        summary="Seed summary",
        chapters=[{"title": "Intro", "summary": "seed", "start": 0.0}],
        language="english",
        transcript_language="en",
        ai_profile_id="gemini_flash",
        ai_model="gemini-2.5-flash",
        translation_results={
            "gemini_flash:russian": {
                "target_language": "Russian",
                "ai_profile_id": "gemini_flash",
                "transcript_segments": [
                    {"enrichment": {"translation": "Привет мир", "translation_status": "ready"}},
                    {"enrichment": {"translation": "Переведенная идея", "translation_status": "ready"}},
                ],
            }
        },
    )
    ingest = KnowledgeIngestService(documents, knowledge)
    document_id = ingest.shadow_write_task(task, content_hash="seed-hash", origin_filename="seed.mp4")
    assert document_id is not None
    task.document_id = document_id
    assert ingest.shadow_write_translations(task) > 0
    return db, document_id


def test_interaction_store_roundtrip():
    print("Testing interaction store roundtrip...")
    from backend.services.storage import (
        ChatConversation,
        ChatMessage,
        Highlight,
        Note,
        SqliteInteractionStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteInteractionStore(Path(tmp) / "videobrain.db")
        conversation = ChatConversation(id="conv-1", document_id="doc-1")
        store.save_conversation(conversation)
        assert store.load_conversation("conv-1") is not None

        msg = ChatMessage(id="msg-1", conversation_id="conv-1", role="user", content="hi")
        store.save_message(msg)
        assert len(store.list_messages("conv-1")) == 1

        note = Note(id="note-1", document_id="doc-1", text="remember this")
        store.save_note(note)
        assert store.load_note("note-1") is not None
        assert len(store.list_notes("doc-1")) == 1
        assert store.delete_note("note-1")

        highlight = Highlight(
            id="hl-1",
            document_id="doc-1",
            chunk_id="chunk-1",
            start_offset=1,
            end_offset=4,
            text="ell",
            color="yellow",
        )
        store.save_highlight(highlight)
        assert store.load_highlight("hl-1") is not None
        assert len(store.list_highlights("doc-1")) == 1
        assert store.delete_highlight("hl-1")

    print("✅ Interaction store works")
    return True


def test_search_service():
    print("\nTesting search service...")
    from backend.services.document_features_service import SearchService
    from backend.services.storage import SqliteDocumentStore, SqliteInteractionStore, SqliteKnowledgeStore, Note

    with tempfile.TemporaryDirectory() as tmp:
        db, document_id = _seed_document(tmp)
        interactions = SqliteInteractionStore(db)
        interactions.save_note(
            Note(id="note-1", document_id=document_id, chunk_id=None, selected_text=None, text="My hello note")
        )
        service = SearchService(
            documents=SqliteDocumentStore(db),
            knowledge=SqliteKnowledgeStore(db),
            interactions=interactions,
        )

        transcript_hits = service.search(document_id, "hello", include_translation=False, include_notes=False)
        assert any(item.source == "transcript" for item in transcript_hits)

        translation_hits = service.search(document_id, "Привет", include_transcript=False, include_notes=False)
        assert any(item.source == "translation" for item in translation_hits)

        note_hits = service.search(document_id, "hello", include_transcript=False, include_translation=False)
        assert any(item.source == "note" for item in note_hits)

    print("✅ Search service finds transcript/translation/notes")
    return True


def test_document_feature_routes():
    print("\nTesting document feature routes...")
    import backend.routes.document_features as route_module
    from fastapi import FastAPI
    from backend.services.document_features_service import (
        ChatService,
        HighlightsService,
        KnowledgeGraphService,
        NotesService,
        SearchService,
    )
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import SqliteDocumentStore, SqliteInteractionStore, SqliteKnowledgeStore
    from fastapi.testclient import TestClient

    class _FakeProvider:
        def generate_text(self, prompt: str, max_tokens=None) -> str:
            return "Document-based answer"

    class _FakeProfile:
        id = "fake"
        display_name = "Fake Profile"
        provider = "fake"
        model = "fake-model"

    def _fake_factory(profile_id=None):
        return (_FakeProfile(), _FakeProvider())

    with tempfile.TemporaryDirectory() as tmp:
        db, document_id = _seed_document(tmp)
        documents = SqliteDocumentStore(db)
        knowledge = SqliteKnowledgeStore(db)
        interactions = SqliteInteractionStore(db)

        # Load a real chunk_id that belongs to this document (chunk validation requires it).
        chunks = knowledge.load_chunks(document_id)
        assert chunks, "Seed must produce at least one chunk"
        real_chunk_id = chunks[0].id

        original_chat = route_module._chat_service
        original_notes = route_module._notes_service
        original_highlights = route_module._highlights_service
        original_search = route_module._search_service
        original_graph = route_module._knowledge_graph_service
        try:
            route_module._chat_service = ChatService(
                documents=documents,
                interactions=interactions,
                knowledge_reader=KnowledgeReadService(documents, knowledge),
                provider_factory=_fake_factory,
            )
            route_module._notes_service = NotesService(documents, interactions, knowledge)
            route_module._highlights_service = HighlightsService(documents, interactions, knowledge)
            route_module._search_service = SearchService(documents, knowledge, interactions)
            route_module._knowledge_graph_service = KnowledgeGraphService()

            app = FastAPI()
            app.include_router(route_module.router)
            client = TestClient(app)

            created_conversation = client.post(
                f"/documents/{document_id}/chat/conversations",
                json={"title": "Doc chat"},
            )
            assert created_conversation.status_code == 201
            conversation_id = created_conversation.json()["id"]

            send_message = client.post(
                f"/documents/{document_id}/chat/conversations/{conversation_id}/messages",
                json={"message": "What is in this document?"},
            )
            assert send_message.status_code == 200
            assert send_message.json()["assistant_message"]["content"] == "Document-based answer"

            create_note = client.post(
                f"/documents/{document_id}/notes",
                json={"text": "important note"},
            )
            assert create_note.status_code == 201

            list_notes = client.get(f"/documents/{document_id}/notes")
            assert list_notes.status_code == 200
            assert len(list_notes.json()) == 1

            create_highlight = client.post(
                f"/documents/{document_id}/highlights",
                json={
                    "chunk_id": real_chunk_id,
                    "start_offset": 0,
                    "end_offset": 5,
                    "text": "Hello",
                    "color": "yellow",
                },
            )
            assert create_highlight.status_code == 201, create_highlight.text

            search = client.get(f"/documents/{document_id}/search?q=hello")
            assert search.status_code == 200
            assert len(search.json()["results"]) > 0

            graph = client.get(f"/documents/{document_id}/knowledge-graph")
            assert graph.status_code == 200
            assert graph.json()["stats"]["status"] == "mock"
        finally:
            route_module._chat_service = original_chat
            route_module._notes_service = original_notes
            route_module._highlights_service = original_highlights
            route_module._search_service = original_search
            route_module._knowledge_graph_service = original_graph

    print("✅ Routes are working")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Document Features - Test Suite")
    print("=" * 60)

    tests = [
        test_interaction_store_roundtrip,
        test_search_service,
        test_document_feature_routes,
    ]
    results = []
    for test in tests:
        try:
            results.append(test())
        except AssertionError as exc:
            print(f"❌ Assertion failed: {exc}")
            results.append(False)
        except Exception as exc:
            print(f"❌ Test crashed: {exc}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    if all(results):
        print("✅ All tests passed!")
        return 0
    print("❌ Some tests failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
