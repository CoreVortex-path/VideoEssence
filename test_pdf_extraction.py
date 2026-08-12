#!/usr/bin/env python3
"""
Tests for backend.services.extractors.pdf_extractor.PdfExtractor.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pymupdf


def _make_pdf(path: Path, pages: list[list[str]], title: str | None = None) -> Path:
    """Create a PDF; each page is a list of paragraph strings."""
    doc = pymupdf.open()
    for paragraphs in pages:
        page = doc.new_page()
        y = 72
        for para in paragraphs:
            page.insert_text((72, y), para)
            y += 28  # blank line gap between paragraphs
    if title is not None:
        doc.set_metadata({"title": title})
    doc.save(path)
    doc.close()
    return path


def _extract(path: Path):
    from backend.services.extractors.pdf_extractor import PdfExtractor

    return PdfExtractor().extract(path)


def test_pdf_with_text():
    print("Testing PDF with text...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_pdf(Path(tmp) / "doc.pdf", [["Hello PDF world"]])
        result = _extract(pdf)
        assert len(result.chunks) >= 1, "expected at least one chunk"
        assert "Hello PDF world" in result.chunks[0].text
    print("✅ PDF with text works")
    return True


def test_multiple_pages():
    print("Testing multiple pages...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_pdf(
            Path(tmp) / "doc.pdf",
            [["First page text"], ["Second page text"], ["Third page text"]],
        )
        result = _extract(pdf)
        assert len(result.chunks) == 3, f"expected 3 chunks, got {len(result.chunks)}"
        assert [c.locator_payload["page"] for c in result.chunks] == [1, 2, 3]
        assert "Second page text" in result.chunks[1].text
        assert result.metadata.get("page_count") == 3
    print("✅ Multiple pages work")
    return True


def test_empty_page():
    print("Testing empty page...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_pdf(
            Path(tmp) / "doc.pdf",
            [["Text before"], [], ["Text after"]],
        )
        result = _extract(pdf)
        assert len(result.chunks) == 2, f"expected 2 chunks, got {len(result.chunks)}"
        pages = [c.locator_payload["page"] for c in result.chunks]
        assert pages == [1, 3], f"empty page must produce no chunks, got pages {pages}"
    print("✅ Empty page works")
    return True


def test_page_locator():
    print("Testing page locator...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_pdf(Path(tmp) / "doc.pdf", [["Alpha", "Beta"]])
        result = _extract(pdf)
        assert len(result.chunks) == 2, "two paragraphs should yield two chunks"
        for i, chunk in enumerate(result.chunks):
            assert chunk.locator_type == "pdf_page", f"bad locator_type: {chunk.locator_type}"
            assert chunk.locator_payload == {"page": 1}, f"bad payload: {chunk.locator_payload}"
            assert chunk.ordinal == i, f"bad ordinal: {chunk.ordinal}"
    print("✅ Page locator works")
    return True


def test_metadata_title():
    print("Testing metadata title...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_pdf(Path(tmp) / "doc.pdf", [["Body"]], title="My Document Title")
        result = _extract(pdf)
        assert result.title == "My Document Title", f"bad title: {result.title}"

        no_title = _make_pdf(Path(tmp) / "plain.pdf", [["Body"]])
        result = _extract(no_title)
        assert result.title is None, f"expected None title, got {result.title}"
    print("✅ Metadata title works")
    return True


def main() -> int:
    tests = [
        test_pdf_with_text,
        test_multiple_pages,
        test_empty_page,
        test_page_locator,
        test_metadata_title,
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
