#!/usr/bin/env python3
"""
Tests for backend.services.extractors.fb2_extractor.Fb2Extractor.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FB2_NS = "http://www.gribuser.ru/xml/fictionbook/2.0"


def _make_fb2(
    sections: list[str],
    title: str | None = "Test Book",
    lang: str | None = "ru",
) -> str:
    """Build a minimal FB2 document; each section entry is raw section XML."""
    title_xml = f"<book-title>{title}</book-title>" if title is not None else ""
    lang_xml = f"<lang>{lang}</lang>" if lang is not None else ""
    body = "".join(sections)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<FictionBook xmlns="{FB2_NS}">'
        f"<description><title-info>{title_xml}{lang_xml}</title-info></description>"
        f"<body>{body}</body>"
        "</FictionBook>"
    )


def _section(*paragraphs: str, nested: str = "") -> str:
    paras = "".join(f"<p>{p}</p>" for p in paragraphs)
    return f"<section>{paras}{nested}</section>"


def _write(tmp: str, content: str, name: str = "book.fb2") -> Path:
    path = Path(tmp) / name
    path.write_text(content, encoding="utf-8")
    return path


def _extract(path: Path):
    from backend.services.extractors.fb2_extractor import Fb2Extractor

    return Fb2Extractor().extract(path)


def test_title():
    print("Testing title...")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(tmp, _make_fb2([_section("Text")], title="Моя Книга"))
        result = _extract(path)
        assert result.title == "Моя Книга", f"bad title: {result.title}"
    print("✅ Title works")
    return True


def test_language():
    print("Testing language...")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(tmp, _make_fb2([_section("Text")], lang="en"))
        result = _extract(path)
        assert result.language == "en", f"bad language: {result.language}"
    print("✅ Language works")
    return True


def test_multiple_sections():
    print("Testing multiple sections...")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(
            tmp,
            _make_fb2([_section("First"), _section("Second"), _section("Third")]),
        )
        result = _extract(path)
        assert len(result.chunks) == 3, f"expected 3 chunks, got {len(result.chunks)}"
        assert result.metadata.get("section_count") == 3
    print("✅ Multiple sections work")
    return True


def test_text_order():
    print("Testing text order...")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(
            tmp,
            _make_fb2([
                _section("Alpha", nested=_section("Nested one")),
                _section("Beta"),
            ]),
        )
        result = _extract(path)
        texts = [c.text for c in result.chunks]
        assert texts == ["Alpha", "Nested one", "Beta"], f"bad order: {texts}"
        ordinals = [c.ordinal for c in result.chunks]
        assert ordinals == list(range(len(ordinals))), f"bad ordinals: {ordinals}"
    print("✅ Text order works")
    return True


def test_locator_type():
    print("Testing locator_type...")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(tmp, _make_fb2([_section("One"), _section("Two")]))
        result = _extract(path)
        for chunk in result.chunks:
            assert chunk.locator_type == "fb2_section", f"bad locator_type: {chunk.locator_type}"
    print("✅ locator_type works")
    return True


def test_locator_payload():
    print("Testing locator_payload...")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(
            tmp,
            _make_fb2([_section("One", nested=_section("Nested")), _section("Two")]),
        )
        result = _extract(path)
        payloads = [c.locator_payload for c in result.chunks]
        assert payloads == [{"section": 1}, {"section": 2}, {"section": 3}], (
            f"bad payloads: {payloads}"
        )
    print("✅ locator_payload works")
    return True


def test_ordinal():
    print("Testing ordinal...")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(tmp, _make_fb2([_section("A"), _section("B"), _section("C")]))
        result = _extract(path)
        assert [c.ordinal for c in result.chunks] == [0, 1, 2]
    print("✅ ordinal works")
    return True


def test_missing_metadata():
    print("Testing missing metadata...")
    with tempfile.TemporaryDirectory() as tmp:
        # No title-info at all.
        content = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<FictionBook xmlns="{FB2_NS}">'
            "<description></description>"
            f"<body>{_section('Only text')}</body>"
            "</FictionBook>"
        )
        path = _write(tmp, content)
        result = _extract(path)
        assert result.title is None, f"expected None title, got {result.title}"
        assert result.language is None, f"expected None language, got {result.language}"
        assert len(result.chunks) == 1 and result.chunks[0].text == "Only text"

        # Empty title-info elements.
        path = _write(tmp, _make_fb2([_section("Text")], title=None, lang=None), "book2.fb2")
        result = _extract(path)
        assert result.title is None and result.language is None
    print("✅ Missing metadata works")
    return True


def test_invalid_fb2():
    print("Testing invalid FB2...")
    with tempfile.TemporaryDirectory() as tmp:
        # Not XML at all.
        path = _write(tmp, "this is not xml <", "broken.fb2")
        try:
            _extract(path)
            raise AssertionError("expected ValueError for malformed XML")
        except ValueError as exc:
            assert "Invalid FB2" in str(exc), f"unclear error: {exc}"

        # Valid XML but not FictionBook.
        path = _write(tmp, "<html><body>hi</body></html>", "notfb2.fb2")
        try:
            _extract(path)
            raise AssertionError("expected ValueError for non-FB2 XML")
        except ValueError as exc:
            assert "FictionBook" in str(exc), f"unclear error: {exc}"
    print("✅ Invalid FB2 errors work")
    return True


def main() -> int:
    tests = [
        test_title,
        test_language,
        test_multiple_sections,
        test_text_order,
        test_locator_type,
        test_locator_payload,
        test_ordinal,
        test_missing_metadata,
        test_invalid_fb2,
    ]
    results = []
    for test in tests:
        try:
            test()
            results.append(True)
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
