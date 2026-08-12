#!/usr/bin/env python3
"""
Tests for chat retrieval quality: token normalization, translation matching,
honest no-match fallback, and per-document quota in library mode.
"""

import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class _FakeProvider:
    def __init__(self):
        self.prompts: list[str] = []

    def generate_text(self, prompt: str, max_tokens=None) -> str:
        self.prompts.append(prompt)
        return "Fake answer"


class _FakeProfile:
    id = "fake"
    display_name = "Fake Profile"
    provider = "fake"
    model = "fake-model"


def _make_factory(provider: _FakeProvider):
    def _factory(profile_id=None):
        return (_FakeProfile(), provider)

    return _factory


def _seed_document(tmp: str):
    """One document: English chunks with Russian translations."""
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


def _seed_library(tmp: str) -> dict[str, str]:
    """Three documents; document A dominates by chunk count."""
    from backend.services.knowledge_ingest_service import KnowledgeIngestService
    from backend.services.storage import SqliteDocumentStore, SqliteKnowledgeStore, Task

    db = Path(tmp) / "videobrain.db"
    documents = SqliteDocumentStore(db)
    knowledge = SqliteKnowledgeStore(db)
    ingest = KnowledgeIngestService(documents, knowledge)
    doc_ids: dict[str, str] = {}

    def add(key: str, title: str, texts: list[str]) -> None:
        task = Task(
            id=f"task-{key}",
            source="file",
            status="completed",
            transcript="\n".join(texts),
            transcript_segments=[
                {"start": float(i), "end": float(i + 1), "text": text}
                for i, text in enumerate(texts)
            ],
            summary=f"{title} summary",
            chapters=[{"title": "Intro", "summary": "seed", "start": 0.0}],
            language="english",
            transcript_language="en",
            ai_profile_id="gemini_flash",
            ai_model="gemini-2.5-flash",
        )
        document_id = ingest.shadow_write_task(task, content_hash=f"hash-{key}", origin_filename=title)
        assert document_id is not None
        doc_ids[key] = document_id

    add("a", "Alpha Doc", [f"alpha topic part {i}" for i in range(10)])
    add("b", "Beta Doc", ["alpha side note one", "alpha side note two"])
    add("c", "Gamma Doc", ["alpha brief mention"])
    return doc_ids


def test_token_normalization():
    print("Testing token normalization (punctuation/case/endings)...")
    from backend.services.document_features_service import ChatService

    chunks = [{"chunk_id": "c1", "text": "Работа нейросетей показала результат"}]
    selected = ChatService._select_relevant_chunks(
        "Расскажи про работу, нейросети!", chunks
    )
    assert selected and selected[0]["chunk_id"] == "c1", (
        "question tokens must match chunk tokens despite punctuation, case and endings"
    )
    print("✅ Normalization matches inflected/punctuated tokens")
    return True


def test_translation_matching():
    print("\nTesting cross-language matching via chunk translations...")
    from backend.services.document_features_service import ChatService
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import (
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db, document_id = _seed_document(tmp)
        documents = SqliteDocumentStore(db)
        knowledge = SqliteKnowledgeStore(db)
        chunks = knowledge.load_chunks(document_id)
        provider = _FakeProvider()
        service = ChatService(
            documents=documents,
            interactions=SqliteInteractionStore(db),
            knowledge_reader=KnowledgeReadService(documents, knowledge),
            provider_factory=_make_factory(provider),
        )
        conversation = service.create_conversation(document_id)
        _, assistant = service.answer(
            document_id, conversation.id, "Расскажи про привет"
        )
        # English chunk "Hello world" is reachable only through its Russian
        # translation "Привет мир".
        assert assistant.metadata["source_chunk_ids"] == [chunks[0].id], (
            f"expected first chunk via translation match, got {assistant.metadata}"
        )
        assert assistant.metadata["retrieval_strategy"] == "keyword-overlap-v2"
        assert assistant.metadata["matched_chunks"] == 1
    print("✅ Russian question matches English chunk via its translation")
    return True


def test_no_match_fallback_is_honest():
    print("\nTesting honest fallback on zero overlap...")
    from backend.services.document_features_service import ChatService
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import (
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db, document_id = _seed_document(tmp)
        documents = SqliteDocumentStore(db)
        provider = _FakeProvider()
        service = ChatService(
            documents=documents,
            interactions=SqliteInteractionStore(db),
            knowledge_reader=KnowledgeReadService(documents, SqliteKnowledgeStore(db)),
            provider_factory=_make_factory(provider),
        )
        conversation = service.create_conversation(document_id)
        _, assistant = service.answer(
            document_id, conversation.id, "quantum zebra xyzzy"
        )
        metadata = assistant.metadata
        assert metadata["retrieval_strategy"] == "none-matched", metadata
        assert metadata["matched_chunks"] == 0, metadata
        assert metadata["source_chunk_ids"] == [], (
            "no silent first-8-chunks fallback allowed"
        )
        assert provider.prompts, "provider must have been called"
        assert "No relevant fragments" in provider.prompts[0], (
            "prompt must explicitly state that nothing relevant was found"
        )
    print("✅ Zero overlap yields empty selection, flagged metadata, honest prompt")
    return True


def test_library_per_document_quota():
    print("\nTesting per-document quota in library mode...")
    from backend.services.document_features_service import (
        ChatService,
        LIBRARY_PER_DOCUMENT_LIMIT,
    )
    from backend.services.knowledge_read_service import KnowledgeReadService
    from backend.services.storage import (
        SqliteDocumentStore,
        SqliteInteractionStore,
        SqliteKnowledgeStore,
    )

    with tempfile.TemporaryDirectory() as tmp:
        doc_ids = _seed_library(tmp)
        db = Path(tmp) / "videobrain.db"
        documents = SqliteDocumentStore(db)
        knowledge = SqliteKnowledgeStore(db)
        reader = KnowledgeReadService(documents, knowledge)

        library_chunks = reader.get_library_chunks()
        selected = ChatService._select_relevant_chunks(
            "Tell me about alpha",
            library_chunks,
            per_document_limit=LIBRARY_PER_DOCUMENT_LIMIT,
        )
        per_doc = Counter(chunk["document_id"] for chunk in selected)
        assert per_doc[doc_ids["a"]] <= LIBRARY_PER_DOCUMENT_LIMIT, per_doc
        assert len(per_doc) >= 2, f"expected at least 2 documents, got {per_doc}"

        provider = _FakeProvider()
        service = ChatService(
            documents=documents,
            interactions=SqliteInteractionStore(db),
            knowledge_reader=reader,
            provider_factory=_make_factory(provider),
        )
        conversation = service.create_global_conversation()
        _, assistant = service.answer_global(
            conversation.id, "Tell me about alpha", mode="library"
        )
        assert len(assistant.metadata["source_documents"]) >= 2, assistant.metadata
    print("✅ Library quota keeps one big document from dominating")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Chat Retrieval - Test Suite")
    print("=" * 60)

    tests = [
        test_token_normalization,
        test_translation_matching,
        test_no_match_fallback_is_honest,
        test_library_per_document_quota,
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
