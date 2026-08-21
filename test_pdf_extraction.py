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


# --- Formula detection (local, no AI) --------------------------------------

MATH_FONT = "china-s"  # bundled CJK font with math/Greek glyph coverage


def test_plain_text_with_digits_not_formula():
    print("Testing plain text with digits is not a formula candidate...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_pdf(
            Path(tmp) / "doc.pdf",
            [["Invoice 12345, total 999.99 due 2024-01-01"],
             ["Page 3 of 10, section 2.4"]],
        )
        result = _extract(pdf)
        assert result.formulas == [], f"unexpected candidates: {result.formulas}"
    print("✅ Plain text with digits produces no candidates")
    return True


def test_math_symbols_text():
    print("Testing text with math symbols...")
    with tempfile.TemporaryDirectory() as tmp:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 100), "∫ f(x) dx = F(b) - F(a) ≤ ∞",
                         fontname=MATH_FONT, fontsize=12)
        page.insert_text((72, 140), "Just an ordinary sentence.", fontsize=12)
        path = Path(tmp) / "doc.pdf"
        doc.save(path)
        doc.close()

        result = _extract(path)
        text_candidates = [f for f in result.formulas if f.kind == "formula_text"]
        assert len(text_candidates) == 1, f"expected 1 formula_text, got {result.formulas}"
        candidate = text_candidates[0]
        assert "∫" in candidate.text, f"bad candidate text: {candidate.text!r}"
        assert candidate.page == 1, f"bad page: {candidate.page}"
        x0, y0, x1, y1 = candidate.bbox
        assert x0 < x1 and y0 < y1, f"bad bbox: {candidate.bbox}"
        assert x0 >= 71 and y0 >= 80, f"bbox off position: {candidate.bbox}"
    print("✅ Math symbols text works")
    return True


def test_formula_line_heuristics():
    print("Testing formula line heuristics (superscript / math font)...")
    from backend.services.extractors.formula_detector import FormulaDetector

    is_formula = FormulaDetector.is_formula_line
    superscript_line = {"spans": [
        {"text": "E = mc", "font": "Helvetica", "flags": 0},
        {"text": "2", "font": "Helvetica", "flags": 1},  # superscript
    ]}
    assert is_formula(superscript_line), "superscript + operator must be a formula"

    math_font_line = {"spans": [
        {"text": "x1", "font": "CMMI10", "flags": 0},
    ]}
    assert is_formula(math_font_line), "math font must be a formula"

    symbol_line = {"spans": [
        {"text": "a ≤ b", "font": "Helvetica", "flags": 0},
    ]}
    assert is_formula(symbol_line), "math symbol must be a formula"

    plain_digits = {"spans": [
        {"text": "Invoice 12345, total 999.99", "font": "Helvetica", "flags": 0},
    ]}
    assert not is_formula(plain_digits), "plain digits must not be a formula"

    plain_text = {"spans": [
        {"text": "Just an ordinary sentence.", "font": "Helvetica", "flags": 0},
    ]}
    assert not is_formula(plain_text), "plain text must not be a formula"

    empty_line = {"spans": [{"text": "   ", "font": "Helvetica", "flags": 0}]}
    assert not is_formula(empty_line), "blank line must not be a formula"
    print("✅ Formula line heuristics work")
    return True


def test_image_candidate():
    print("Testing image candidate...")
    with tempfile.TemporaryDirectory() as tmp:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Text above the formula image.", fontsize=12)
        # rect aspect matches the 60x40 pixmap so the image fills it exactly
        rect = pymupdf.Rect(100, 120, 190, 180)
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40))
        pixmap.clear_with(30)
        page.insert_image(rect, pixmap=pixmap)
        path = Path(tmp) / "doc.pdf"
        doc.save(path)
        doc.close()

        result = _extract(path)
        image_candidates = [f for f in result.formulas if f.kind == "formula_image"]
        assert len(image_candidates) == 1, f"expected 1 formula_image, got {result.formulas}"
        candidate = image_candidates[0]
        assert candidate.page == 1, f"bad page: {candidate.page}"
        x0, y0, x1, y1 = candidate.bbox
        assert abs(x0 - rect.x0) < 2 and abs(y0 - rect.y0) < 2, f"bad bbox: {candidate.bbox}"
        assert abs(x1 - rect.x1) < 2 and abs(y1 - rect.y1) < 2, f"bad bbox: {candidate.bbox}"
    print("✅ Image candidate works")
    return True


def test_vector_candidate():
    print("Testing vector candidate...")
    with tempfile.TemporaryDirectory() as tmp:
        doc = pymupdf.open()
        page = doc.new_page()
        # stacked fraction bars with numerator/denominator text around them
        page.insert_text((120, 292), "a", fontsize=12)
        page.insert_text((120, 320), "b", fontsize=12)
        page.draw_line((100, 300), (160, 300))
        page.draw_line((100, 306), (160, 306))
        # page-wide rules (table/border style) must be ignored
        page.draw_line((72, 500), (520, 500))
        page.draw_line((72, 506), (520, 506))
        # a single short line must be ignored
        page.draw_line((400, 100), (420, 100))
        path = Path(tmp) / "doc.pdf"
        doc.save(path)
        doc.close()

        result = _extract(path)
        vector_candidates = [f for f in result.formulas if f.kind == "formula_vector"]
        assert len(vector_candidates) == 1, f"expected 1 formula_vector, got {result.formulas}"
        candidate = vector_candidates[0]
        assert candidate.page == 1, f"bad page: {candidate.page}"
        x0, y0, x1, y1 = candidate.bbox
        assert x0 <= 100 and x1 >= 160, f"bbox must span both lines: {candidate.bbox}"
        assert y0 <= 300 and y1 >= 306, f"bbox must span both lines: {candidate.bbox}"
    print("✅ Vector candidate works")
    return True


def test_table_rules_not_vector():
    print("Testing table rules are not formula_vector...")
    with tempfile.TemporaryDirectory() as tmp:
        doc = pymupdf.open()
        page = doc.new_page()
        # booktabs-style table: rule pairs repeating with the same x-range,
        # text rows above and below each pair (like a real table)
        page.insert_text((100, 292), "Header A    Header B", fontsize=12)
        page.draw_line((100, 300), (260, 300))
        page.draw_line((100, 306), (260, 306))
        page.insert_text((100, 326), "value 1     value 2", fontsize=12)
        page.insert_text((100, 392), "value 3     value 4", fontsize=12)
        page.draw_line((100, 400), (260, 400))
        page.draw_line((100, 406), (260, 406))
        page.insert_text((100, 426), "footer row", fontsize=12)
        path = Path(tmp) / "doc.pdf"
        doc.save(path)
        doc.close()

        result = _extract(path)
        vector_candidates = [f for f in result.formulas if f.kind == "formula_vector"]
        assert vector_candidates == [], f"table rules must not be candidates: {vector_candidates}"
    print("✅ Table rules are not formula_vector")
    return True


def test_graph_lines_not_vector():
    print("Testing graph/chart lines are not formula_vector...")
    with tempfile.TemporaryDirectory() as tmp:
        doc = pymupdf.open()
        page = doc.new_page()
        # double-drawn stroke at the same y (chart marker style)
        page.draw_line((400, 100), (430, 100))
        page.draw_line((400, 100), (430, 100))
        # chart axes: long lines, already filtered by max width
        page.draw_line((100, 200), (100, 400))
        page.draw_line((100, 400), (500, 400))
        # curve segment pairs without any math text around
        page.draw_line((200, 250), (240, 250))
        page.draw_line((200, 253), (240, 253))
        path = Path(tmp) / "doc.pdf"
        doc.save(path)
        doc.close()

        result = _extract(path)
        vector_candidates = [f for f in result.formulas if f.kind == "formula_vector"]
        assert vector_candidates == [], f"chart lines must not be candidates: {vector_candidates}"
    print("✅ Graph lines are not formula_vector")
    return True


# --- formula_region: custom-encoded math fonts (MathematicalPi-style) ------

def _line(x0, y0, x1, y1, text):
    return {"bbox": (x0, y0, x1, y1), "spans": [{"text": text, "font": "X", "flags": 0}]}


def test_equation_number_line():
    print("Testing equation-number line recognition...")
    from backend.services.extractors.formula_detector import FormulaDetector

    is_number = FormulaDetector._is_equation_number_line
    assert is_number(_line(540, 100, 551, 109, "\x036\x04")), "control-char parens"
    assert is_number(_line(540, 100, 551, 109, "(12)")), "literal parens"
    assert not is_number(_line(540, 100, 551, 109, "40")), "bare digit = axis tick"
    assert not is_number(_line(540, 100, 551, 109, "3")), "bare digit = section number"
    assert not is_number(_line(540, 100, 551, 109, "Eq. (8)")), "letters not allowed"
    assert not is_number(_line(540, 100, 551, 109, "(1234)")), "too many digits"
    print("✅ Equation-number line recognition works")
    return True


def test_region_collection():
    print("Testing region body collection around an equation number...")
    from backend.services.extractors.formula_detector import FormulaDetector

    # Layout: display equation with a fraction, number right-aligned,
    # prose lines around (full-width, no custom glyphs or too long).
    number = _line(540.6, 569.6, 551.4, 578.9, "\x036\x04")
    lines = [
        _line(60.6, 559.5, 300.2, 568.8, "where A is the coefficient matrix. " * 2),
        number,
        _line(413.9, 563.2, 447.3, 578.9, "p\x03m\x04 = 1"),   # numerator, same row
        _line(441.2, 574.9, 449.0, 585.4, "2n"),                # denominator below
        _line(60.6, 569.8, 300.2, 578.8, "prose on the same row, left column " * 2),
        _line(312.1, 569.8, 551.6, 578.8, "right prose ending past the number"),
    ]
    group = FormulaDetector._collect_region_lines(lines, 1)
    assert group is not None, "fraction equation must be found"
    texts = sorted(FormulaDetector._line_text(lines[i]) for i in group)
    assert texts == ["2n", "p\x03m\x04 = 1"], f"bad body: {texts}"

    # Prose-only surroundings -> no region.
    prose_only = [
        _line(60.6, 100.0, 300.2, 109.0, "ordinary prose line " * 3),
        _line(540.6, 100.0, 551.4, 109.0, "\x038\x04"),
    ]
    assert FormulaDetector._collect_region_lines(prose_only, 1) is None

    # Tall equation: main row far above the vertically centered number.
    tall = [
        _line(74.6, 362.5, 120.0, 380.7, "p\x03\x06\x05Y\x04 ="),
        _line(124.6, 362.5, 206.2, 380.7, "p\x03\x06\x05m,Y\x04p\x03m\x05Y\x04"),
        _line(107.1, 379.8, 122.3, 386.2, "m\x01M"),
        _line(289.1, 391.3, 300.0, 400.6, "\x038\x04"),
    ]
    group = FormulaDetector._collect_region_lines(tall, 3)
    assert group is not None, "tall equation must be found via fallback"
    assert len(group) == 3, f"tall equation body: {group}"
    print("✅ Region collection works")
    return True


def test_text_chunks_unaffected_by_formulas():
    print("Testing text extraction is unaffected by formula detection...")
    with tempfile.TemporaryDirectory() as tmp:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Plain paragraph one.", fontsize=12)
        page.insert_text((72, 100), "∫ f(x) dx = 0", fontname=MATH_FONT, fontsize=12)
        rect = pymupdf.Rect(100, 140, 200, 190)
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 40))
        pixmap.clear_with(30)
        page.insert_image(rect, pixmap=pixmap)
        path = Path(tmp) / "doc.pdf"
        doc.save(path)
        doc.close()

        result = _extract(path)
        # chunks behave exactly as before: text blocks only, pdf_page locators
        assert len(result.chunks) == 2, f"expected 2 chunks, got {len(result.chunks)}"
        for i, chunk in enumerate(result.chunks):
            assert chunk.locator_type == "pdf_page"
            assert chunk.locator_payload == {"page": 1}
            assert chunk.ordinal == i
        assert result.chunks[0].text == "Plain paragraph one."
        # candidates live separately and cover both the math line and the image
        kinds = sorted(f.kind for f in result.formulas)
        assert kinds == ["formula_image", "formula_text"], f"bad kinds: {kinds}"
    print("✅ Text chunks unaffected by formulas")
    return True


def main() -> int:
    tests = [
        test_pdf_with_text,
        test_multiple_pages,
        test_empty_page,
        test_page_locator,
        test_metadata_title,
        test_plain_text_with_digits_not_formula,
        test_math_symbols_text,
        test_formula_line_heuristics,
        test_image_candidate,
        test_vector_candidate,
        test_table_rules_not_vector,
        test_graph_lines_not_vector,
        test_equation_number_line,
        test_region_collection,
        test_text_chunks_unaffected_by_formulas,
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
