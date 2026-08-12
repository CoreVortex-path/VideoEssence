"""FB2 (FictionBook) text extraction without any AI/API usage.

FB2 is XML, so the standard library's xml.etree.ElementTree is used —
no third-party dependency is required.

Each structural <section> becomes one or more ExtractedChunk items
carrying an ``fb2_section`` locator with the 1-based section number in
document order (plus a ``part`` index when a section is split into
several chunks).
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from backend.services.document_extraction import (
    DocumentExtractor,
    ExtractedChunk,
    ExtractedDocument,
)

# Sections larger than this are split into paragraph-grouped chunks
# so that chunks stay usable for retrieval.
_MAX_CHUNK_CHARS = 2000


def _local_name(tag: str) -> str:
    """Strip the XML namespace from a tag name."""
    return tag.rsplit("}", 1)[-1]


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in elem if _local_name(child.tag) == name]


def _first_text(elem: ET.Element, name: str) -> str | None:
    for child in _children(elem, name):
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return None


def _paragraph_texts(section: ET.Element) -> list[str]:
    """Direct <p> paragraphs of a section (nested sections excluded)."""
    texts = []
    for para in _children(section, "p"):
        text = "".join(para.itertext()).strip()
        if text:
            texts.append(text)
    return texts


def _split_paragraphs(paragraphs: list[str]) -> list[str]:
    """Group paragraphs into chunk texts bounded by _MAX_CHUNK_CHARS."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        if current and current_len + len(para) > _MAX_CHUNK_CHARS:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


class Fb2Extractor(DocumentExtractor):
    """Extracts text from FB2 files section by section."""

    def extract(self, path: Path) -> ExtractedDocument:
        path = Path(path)
        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid FB2 file {path}: not well-formed XML ({exc})") from exc

        root = tree.getroot()
        if _local_name(root.tag) != "FictionBook":
            raise ValueError(
                f"Invalid FB2 file {path}: root element is "
                f"'{_local_name(root.tag)}', expected 'FictionBook'"
            )

        title = None
        language = None
        for description in _children(root, "description"):
            for title_info in _children(description, "title-info"):
                title = _first_text(title_info, "book-title") or title
                language = _first_text(title_info, "lang") or language

        chunks: list[ExtractedChunk] = []
        ordinal = 0
        section_number = 0

        def walk(elem: ET.Element) -> None:
            nonlocal ordinal, section_number
            for section in _children(elem, "section"):
                section_number += 1
                number = section_number
                parts = _split_paragraphs(_paragraph_texts(section))
                for part_index, text in enumerate(parts, start=1):
                    payload: dict = {"section": number}
                    if len(parts) > 1:
                        payload["part"] = part_index
                    chunks.append(
                        ExtractedChunk(
                            text=text,
                            ordinal=ordinal,
                            locator_type="fb2_section",
                            locator_payload=payload,
                        )
                    )
                    ordinal += 1
                walk(section)  # nested sections follow in document order

        for body in _children(root, "body"):
            walk(body)

        return ExtractedDocument(
            title=title,
            language=language,
            chunks=chunks,
            metadata={"section_count": section_number},
        )
