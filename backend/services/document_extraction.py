from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class ExtractedChunk:
    text: str
    ordinal: int
    locator_type: str | None = None
    locator_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class FormulaCandidate:
    """A detected formula region on a document page (no AI involved).

    ``kind`` is one of ``formula_text`` | ``formula_image`` | ``formula_vector``.
    ``bbox`` is ``[x0, y0, x1, y1]`` in PDF points on the 1-based ``page``.
    Rendering the region to PNG is deliberately deferred to a later stage,
    where a document id is available for the output path.
    """

    kind: str
    page: int
    bbox: list[float]
    text: str | None = None


@dataclass
class ExtractedDocument:
    title: str | None
    language: str | None
    chunks: list[ExtractedChunk]
    metadata: dict[str, Any] = field(default_factory=dict)
    formulas: list[FormulaCandidate] = field(default_factory=list)


class DocumentExtractor(Protocol):
    def extract(self, path: Path) -> ExtractedDocument:
        ...