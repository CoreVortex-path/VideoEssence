"""Renders detected formula regions of a PDF to PNG files (no AI involved).

Takes FormulaCandidate items produced by FormulaDetector (page + bbox +
kind) and saves each region as a PNG under
``data/formula_images/<document_id>/`` using only PyMuPDF. Filenames are
deterministic: ``p<page>_f<index>_<kind>.png``. Existing files are NOT
re-rendered.
"""

from pathlib import Path

import pymupdf

from backend.services.document_extraction import FormulaCandidate

DEFAULT_OUTPUT_ROOT = Path("data") / "formula_images"
DEFAULT_PADDING = 4.0  # PDF points around the candidate bbox
DEFAULT_DPI = 200
MIN_DPI = 200
MAX_DPI = 300


class FormulaRegionRenderer:
    """Saves formula candidate regions of a PDF as PNG images."""

    def __init__(
        self,
        output_root: Path | str = DEFAULT_OUTPUT_ROOT,
        padding: float = DEFAULT_PADDING,
        dpi: int = DEFAULT_DPI,
    ) -> None:
        if not MIN_DPI <= dpi <= MAX_DPI:
            raise ValueError(f"dpi must be in {MIN_DPI}..{MAX_DPI}, got {dpi}")
        if padding < 0:
            raise ValueError(f"padding must be >= 0, got {padding}")
        self._output_root = Path(output_root)
        self._padding = padding
        self._dpi = dpi

    def render(
        self,
        pdf_path: Path,
        document_id: str,
        candidate: FormulaCandidate,
        index: int,
    ) -> Path:
        """Render one candidate region to PNG and return its path.

        ``index`` is the candidate's index within the document and makes the
        filename unique and deterministic. If the target file already exists
        it is returned as-is, without re-rendering.
        """
        out_dir = self._output_root / str(document_id)
        filename = f"p{candidate.page:02d}_f{index:02d}_{candidate.kind}.png"
        out_path = out_dir / filename
        if out_path.exists():
            return out_path

        with pymupdf.open(Path(pdf_path)) as doc:
            if not 1 <= candidate.page <= doc.page_count:
                raise ValueError(
                    f"candidate page {candidate.page} out of range 1..{doc.page_count}"
                )
            page = doc.load_page(candidate.page - 1)
            pad = self._padding
            x0, y0, x1, y1 = candidate.bbox
            rect = pymupdf.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad) & page.rect
            if rect.is_empty:
                raise ValueError(f"candidate bbox {candidate.bbox} is outside the page")
            pixmap = page.get_pixmap(clip=rect, dpi=self._dpi)
            out_dir.mkdir(parents=True, exist_ok=True)
            pixmap.save(out_path)
        return out_path
