"""Document text extractors (PDF, FB2) and their registry.

Each supported extension maps to its DocumentExtractor implementation and
the Document.source_type value defined in docs/domain-model.md (open set:
``file_media``, ``youtube``, ``pdf``, ``epub``, ...; ``fb2`` extends it
for FictionBook files).
"""

from pathlib import Path

from backend.services.document_extraction import DocumentExtractor
from backend.services.extractors.fb2_extractor import Fb2Extractor
from backend.services.extractors.pdf_extractor import PdfExtractor

# extension -> (Document.source_type, extractor class)
_EXTRACTORS: dict[str, tuple[str, type[DocumentExtractor]]] = {
    ".pdf": ("pdf", PdfExtractor),
    ".fb2": ("fb2", Fb2Extractor),
}

SUPPORTED_DOCUMENT_FORMATS = frozenset(_EXTRACTORS)


def get_extractor(path: Path) -> DocumentExtractor | None:
    """Return the extractor for a file's extension, or None if unsupported."""
    entry = _EXTRACTORS.get(Path(path).suffix.lower())
    return entry[1]() if entry else None


def get_document_source_type(path: Path) -> str | None:
    """Return the Document.source_type for a file's extension, or None."""
    entry = _EXTRACTORS.get(Path(path).suffix.lower())
    return entry[0] if entry else None
