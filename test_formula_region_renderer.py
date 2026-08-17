#!/usr/bin/env python3
"""
Tests for backend.services.formula_region_renderer.FormulaRegionRenderer.
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

from backend.services.extractors.pdf_extractor import PdfExtractor
from backend.services.formula_region_renderer import FormulaRegionRenderer

DOC_ID = "test-doc"
DPI = 200
PT_PER_PX = 72.0 / DPI


def _pixmap(width: int = 60, height: int = 40) -> pymupdf.Pixmap:
    pm = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height))
    pm.clear_with(30)
    return pm


def _make_image_pdf(path: Path, rect: pymupdf.Rect) -> Path:
    """One page with a single aspect-matched image at rect."""
    doc = pymupdf.open()
    page = doc.new_page()
    pm = _pixmap()
    page.insert_image(rect, pixmap=pm)
    doc.save(path)
    doc.close()
    return path


def _make_vector_pdf(path: Path) -> Path:
    """One page with a stacked-fraction-like vector formula."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((120, 292), "a", fontsize=12)
    page.insert_text((120, 320), "b", fontsize=12)
    page.draw_line((100, 300), (160, 300))
    page.draw_line((100, 306), (160, 306))
    doc.save(path)
    doc.close()
    return path


def _make_plain_text_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Just an ordinary sentence.", fontsize=12)
    doc.save(path)
    doc.close()
    return path


def _png_size(path: Path) -> tuple[int, int]:
    pm = pymupdf.Pixmap(str(path))
    return pm.width, pm.height


def test_formula_image_png_created():
    print("Testing formula_image renders to PNG...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_image_pdf(Path(tmp) / "doc.pdf", pymupdf.Rect(100, 120, 190, 180))
        result = PdfExtractor().extract(pdf)
        candidates = [f for f in result.formulas if f.kind == "formula_image"]
        assert len(candidates) == 1, f"expected 1 formula_image, got {result.formulas}"

        renderer = FormulaRegionRenderer(output_root=Path(tmp) / "out")
        out = renderer.render(pdf, DOC_ID, candidates[0], index=0)
        assert out.exists(), "PNG was not created"
        assert out.suffix == ".png"
        with open(out, "rb") as fh:
            assert fh.read(8) == b"\x89PNG\r\n\x1a\n", "not a PNG file"
    print("✅ formula_image PNG works")
    return True


def test_formula_vector_png_created():
    print("Testing formula_vector renders to PNG...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_vector_pdf(Path(tmp) / "doc.pdf")
        result = PdfExtractor().extract(pdf)
        candidates = [f for f in result.formulas if f.kind == "formula_vector"]
        assert len(candidates) == 1, f"expected 1 formula_vector, got {result.formulas}"

        renderer = FormulaRegionRenderer(output_root=Path(tmp) / "out")
        out = renderer.render(pdf, DOC_ID, candidates[0], index=0)
        assert out.exists() and out.suffix == ".png", f"PNG missing: {out}"
    print("✅ formula_vector PNG works")
    return True


def test_bbox_defines_region():
    print("Testing bbox defines the rendered region...")
    with tempfile.TemporaryDirectory() as tmp:
        rect = pymupdf.Rect(100, 120, 190, 180)  # 90x60 pt
        pdf = _make_image_pdf(Path(tmp) / "doc.pdf", rect)
        result = PdfExtractor().extract(pdf)
        candidate = [f for f in result.formulas if f.kind == "formula_image"][0]

        padding = 4.0
        renderer = FormulaRegionRenderer(output_root=Path(tmp) / "out", padding=padding)
        out = renderer.render(pdf, DOC_ID, candidate, index=0)
        width, height = _png_size(out)
        expected_w = (rect.width + 2 * padding) / PT_PER_PX
        expected_h = (rect.height + 2 * padding) / PT_PER_PX
        assert abs(width - expected_w) <= 2, f"width {width} != ~{expected_w}"
        assert abs(height - expected_h) <= 2, f"height {height} != ~{expected_h}"
    print("✅ bbox region works")
    return True


def test_padding_clipped_at_page_edge():
    print("Testing padding does not cross page bounds...")
    with tempfile.TemporaryDirectory() as tmp:
        rect = pymupdf.Rect(0, 0, 60, 40)  # image flush with the top-left corner
        pdf = _make_image_pdf(Path(tmp) / "doc.pdf", rect)
        result = PdfExtractor().extract(pdf)
        candidate = [f for f in result.formulas if f.kind == "formula_image"][0]

        padding = 10.0
        renderer = FormulaRegionRenderer(output_root=Path(tmp) / "out", padding=padding)
        out = renderer.render(pdf, DOC_ID, candidate, index=0)  # must not raise
        width, height = _png_size(out)
        # clipped to the page: left/top padding is cut off
        expected_w = (rect.width + padding) / PT_PER_PX  # only right padding kept
        expected_h = (rect.height + padding) / PT_PER_PX  # only bottom padding kept
        assert abs(width - expected_w) <= 2, f"width {width} != ~{expected_w}"
        assert abs(height - expected_h) <= 2, f"height {height} != ~{expected_h}"
    print("✅ Page-edge padding works")
    return True


def test_deterministic_filename():
    print("Testing deterministic filename...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_image_pdf(Path(tmp) / "doc.pdf", pymupdf.Rect(100, 120, 190, 180))
        result = PdfExtractor().extract(pdf)
        candidate = result.formulas[0]

        renderer = FormulaRegionRenderer(output_root=Path(tmp) / "out")
        first = renderer.render(pdf, DOC_ID, candidate, index=0)
        second = renderer.render(pdf, DOC_ID, candidate, index=0)
        assert first == second, f"names differ: {first} vs {second}"
        assert first.name == "p01_f00_formula_image.png", f"bad name: {first.name}"
        assert first.parent.name == DOC_ID, f"bad dir: {first.parent}"
    print("✅ Deterministic filename works")
    return True


def test_repeat_call_does_not_rerender():
    print("Testing repeat call does not create another file...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_image_pdf(Path(tmp) / "doc.pdf", pymupdf.Rect(100, 120, 190, 180))
        result = PdfExtractor().extract(pdf)
        candidate = result.formulas[0]

        renderer = FormulaRegionRenderer(output_root=Path(tmp) / "out")
        first = renderer.render(pdf, DOC_ID, candidate, index=0)
        content = first.read_bytes()
        again = renderer.render(pdf, DOC_ID, candidate, index=0)
        assert again == first
        assert again.read_bytes() == content, "file content changed on repeat call"
        files = list((Path(tmp) / "out" / DOC_ID).glob("*.png"))
        assert len(files) == 1, f"expected 1 file, got {files}"
    print("✅ No re-render on repeat call")
    return True


def test_multiple_candidates_no_overwrite():
    print("Testing multiple candidates do not overwrite each other...")
    with tempfile.TemporaryDirectory() as tmp:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_image(pymupdf.Rect(100, 100, 190, 160), pixmap=_pixmap())
        page.insert_image(pymupdf.Rect(100, 300, 190, 360), pixmap=_pixmap())
        pdf = Path(tmp) / "doc.pdf"
        doc.save(pdf)
        doc.close()

        result = PdfExtractor().extract(pdf)
        assert len(result.formulas) == 2, f"expected 2 candidates, got {result.formulas}"

        renderer = FormulaRegionRenderer(output_root=Path(tmp) / "out")
        paths = [
            renderer.render(pdf, DOC_ID, candidate, index=i)
            for i, candidate in enumerate(result.formulas)
        ]
        assert paths[0] != paths[1], f"candidates share a path: {paths}"
        assert all(p.exists() for p in paths)
        files = list((Path(tmp) / "out" / DOC_ID).glob("*.png"))
        assert len(files) == 2, f"expected 2 files, got {files}"
    print("✅ Multiple candidates work")
    return True


def test_plain_text_triggers_no_render():
    print("Testing plain text chunks never reach the renderer...")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _make_plain_text_pdf(Path(tmp) / "doc.pdf")
        result = PdfExtractor().extract(pdf)
        assert len(result.chunks) == 1, "text chunk must still be extracted"
        assert result.formulas == [], f"plain text must yield no candidates: {result.formulas}"

        out_root = Path(tmp) / "out"
        renderer = FormulaRegionRenderer(output_root=out_root)
        for i, candidate in enumerate(result.formulas):  # empty: nothing rendered
            renderer.render(pdf, DOC_ID, candidate, index=i)
        assert not out_root.exists(), f"no output dir must be created, got {out_root}"
    print("✅ Plain text triggers no render")
    return True


def main() -> int:
    tests = [
        test_formula_image_png_created,
        test_formula_vector_png_created,
        test_bbox_defines_region,
        test_padding_clipped_at_page_edge,
        test_deterministic_filename,
        test_repeat_call_does_not_rerender,
        test_multiple_candidates_no_overwrite,
        test_plain_text_triggers_no_render,
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
