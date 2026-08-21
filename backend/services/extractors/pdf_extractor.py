"""PDF text extraction without any AI/API usage.

Each PDF page becomes one or more ExtractedChunk items carrying a
``pdf_page`` locator with the 1-based page number. Additionally, a
heuristic FormulaDetector locates formula candidate regions
(page + bbox + kind) on each page; candidates are returned on
``ExtractedDocument.formulas`` and do not affect the text chunks.
"""

from pathlib import Path

import pymupdf

from backend.services.document_extraction import (
    DocumentExtractor,
    ExtractedChunk,
    ExtractedDocument,
)
from backend.services.extractors.formula_detector import FormulaDetector


class PdfExtractor(DocumentExtractor):
    """Extracts text from PDF files page by page using PyMuPDF."""

    def __init__(self, formula_detector: FormulaDetector | None = None) -> None:
        self._formula_detector = formula_detector or FormulaDetector()

    def extract(self, path: Path) -> ExtractedDocument:
        path = Path(path)
        with pymupdf.open(path) as doc:
            metadata = doc.metadata or {}
            title = (metadata.get("title") or "").strip() or None

            chunks: list[ExtractedChunk] = []
            ordinal = 0
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                page_number = page_index + 1  # 1-based
                for block in page.get_text("blocks"):
                    # block: (x0, y0, x1, y1, text, block_no, block_type)
                    if len(block) < 7 or block[6] != 0:  # text blocks only
                        continue
                    text = (block[4] or "").strip()
                    if not text:
                        continue
                    chunks.append(
                        ExtractedChunk(
                            text=text,
                            ordinal=ordinal,
                            locator_type="pdf_page",
                            locator_payload={"page": page_number},
                        )
                    )
                    ordinal += 1

            return ExtractedDocument(
                title=title,
                language=None,
                chunks=chunks,
                metadata={"page_count": doc.page_count},
                formulas=self._formula_detector.detect(doc),
            )
