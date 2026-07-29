#!/usr/bin/env python3
"""
Tests for the Phase 1 security fixes (ADR-0002).

Covers:
- C1: task_id validation at the route boundary + store defense-in-depth
- C2: upload extension validation, size limit, streaming, partial-file cleanup
- C4: CORS origin restriction + health endpoint key metadata removal
- C5: cleanup preserves transcript/summary artifacts

Uses TestClient and temp directories; never mutates data/.
"""

import asyncio
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Windows consoles may default to cp1251; emoji markers need UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def test_c1_route_boundary():
    """Non-UUID task ids are rejected with 400 before touching storage."""
    print("Testing C1 route boundary validation...")
    from fastapi.testclient import TestClient
    from backend.app import app

    client = TestClient(app)

    r = client.get("/videos/status/not-a-uuid")
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    r = client.get("/videos/status/..%2F..%2F..%2Fsecret")
    assert r.status_code in (400, 404), f"Traversal attempt got {r.status_code}"

    r = client.post(
        "/videos/status/not-a-uuid/translate",
        json={"target_language": "ru"},
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    # Valid UUID shape still reaches the normal 404 path.
    r = client.get("/videos/status/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404, f"Expected 404 for unknown valid UUID, got {r.status_code}"

    print("✅ Route boundary rejects invalid ids, accepts UUID shape")
    return True


def test_c1_store_defense():
    """JsonTaskStore refuses unsafe ids even if callers bypass routes."""
    print("\nTesting C1 store defense-in-depth...")
    from backend.services.storage import JsonTaskStore, Task

    with tempfile.TemporaryDirectory() as tmp:
        store = JsonTaskStore(Path(tmp))

        # load() refuses safely.
        assert store.load("../evil") is None
        assert store.load("a/b") is None
        assert store.load("") is None

        # save() fails loudly.
        try:
            store.save(Task(id="../evil", source="file"))
        except ValueError:
            pass
        else:
            raise AssertionError("save() accepted an unsafe task id")

        assert list(Path(tmp).iterdir()) == [], "Unsafe ids must not create files"

    print("✅ Store rejects unsafe ids (load→None, save→ValueError, no files)")
    return True


def test_c2_upload_validation():
    """Extension check, size limit, streaming, and partial-file cleanup."""
    print("\nTesting C2 upload hardening...")
    from fastapi import UploadFile
    from backend.config.settings import settings
    from backend.services.file_handler import (
        UploadValidationError,
        save_uploaded_file,
    )

    async def scenario():
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)

            # Unsupported extension rejected before writing.
            bad = UploadFile(file=io.BytesIO(b"x" * 100), filename="evil.exe")
            try:
                await save_uploaded_file(bad, dest)
            except UploadValidationError as e:
                assert e.status_code == 422
            else:
                raise AssertionError("Unsupported extension accepted")
            assert list(dest.iterdir()) == [], "Rejected upload left a file"

            # Oversized upload rejected mid-stream, partial file removed.
            original_limit = settings.max_upload_size_mb
            settings.max_upload_size_mb = 1
            try:
                big = UploadFile(
                    file=io.BytesIO(b"x" * (1024 * 1024 + 10)),
                    filename="big.mp3",
                )
                try:
                    await save_uploaded_file(big, dest)
                except UploadValidationError as e:
                    assert e.status_code == 413
                else:
                    raise AssertionError("Oversized upload accepted")
                assert list(dest.iterdir()) == [], "Partial oversized upload left on disk"

                # Valid upload streams to disk intact, with content hash.
                payload = b"audio-bytes" * 1000
                ok = UploadFile(file=io.BytesIO(payload), filename="ok.mp3")
                saved, digest = await save_uploaded_file(ok, dest)
                assert Path(saved).read_bytes() == payload
                import hashlib
                assert digest == hashlib.sha256(payload).hexdigest()
            finally:
                settings.max_upload_size_mb = original_limit

    asyncio.run(scenario())
    print("✅ Uploads: 422 on bad type, 413 + cleanup on oversize, valid streams OK")
    return True


def test_c4_cors_and_health():
    """CORS restricted to localhost; health leaks no key metadata."""
    print("\nTesting C4 CORS + health endpoint...")
    from fastapi.testclient import TestClient
    from backend.app import app
    from backend.config.settings import settings

    client = TestClient(app)

    r = client.get("/videos/ai-profiles", headers={"Origin": "http://evil.example.com"})
    acao = r.headers.get("access-control-allow-origin")
    assert acao in (None, ""), f"Untrusted origin got ACAO: {acao}"

    r = client.get("/videos/ai-profiles", headers={"Origin": "http://localhost:8000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8000"

    # Health endpoint: force the no-key branch (no network) and check the body.
    original_key = settings.google_api_key
    settings.google_api_key = None
    try:
        r = client.get("/videos/health/gemini")
        assert r.status_code == 503
        body = r.json()
        assert "key_prefix" not in body and "key_length" not in body
    finally:
        settings.google_api_key = original_key

    print("✅ CORS restricted to localhost; health response has no key metadata")
    return True


def test_c5_cleanup_preserves_artifacts():
    """Cleanup calls in the pipeline no longer target transcript/summary files."""
    print("\nTesting C5 artifact preservation...")
    import inspect
    import backend.routes.video as video_module

    source = inspect.getsource(video_module)
    assert "cleanup_service.cleanup(uploaded_path, audio_path, transcript_path, summary_path)" not in source, \
        "Old cleanup call still deletes persisted artifacts"

    print("✅ Pipeline cleanup no longer deletes transcript/summary artifacts")
    return True


def main():
    print("=" * 60)
    print("VideoBrain Security Fixes (ADR-0002) - Test Suite")
    print("=" * 60)

    tests = [
        test_c1_route_boundary,
        test_c1_store_defense,
        test_c2_upload_validation,
        test_c4_cors_and_health,
        test_c5_cleanup_preserves_artifacts,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except AssertionError as e:
            print(f"❌ Assertion failed: {e}")
            results.append(False)
        except Exception as e:
            print(f"❌ Test crashed: {e}")
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
