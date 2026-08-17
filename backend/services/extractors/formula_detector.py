"""Heuristic, AI-free detection of formula regions in PDF pages.

Uses only PyMuPDF: text span fonts/flags/geometry, embedded images and
vector drawings. It does NOT transcribe formulas — it only locates
candidate regions (page + bbox + kind) for later processing.
"""

import pymupdf

from backend.services.document_extraction import FormulaCandidate

KIND_TEXT = "formula_text"
KIND_IMAGE = "formula_image"
KIND_VECTOR = "formula_vector"
KIND_REGION = "formula_region"

# Relational/operator-like math symbols that rarely appear in prose.
MATH_SYMBOLS = frozenset(
    "∫∑∏√∂∇±×÷≠≤≥≈∞∈∉∀∃∪∩⊂⊆⊄⊅→←↔⇒⇔∝∠⊗⊕∧∨¬∴≡∼≅"
)
GREEK = frozenset("αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΥΦΧΨΩ")
OPERATORS = frozenset("=+−–*/^<>|")

# Font-name fragments typical for math typesetting (lower-cased match).
# Note: "cmr" (Computer Modern Roman) is body text in LaTeX docs and is
# deliberately NOT here. "MathematicalPi" is deliberately NOT here either:
# MathPi-Three supplies brackets for ordinary prose, so a font-name rule
# would flag nearly every line (see formula_region detection instead).
MATH_FONT_MARKERS = (
    "cmmi", "cmsy", "cmex", "msam", "msbm", "eufm", "stmary",
    "mathjax", "cambria math", "latin modern math", "asana math",
    "stix", "mt extra", "symbol",
)

SUPERSCRIPT_FLAG = 1  # bit 0 of span "flags"

# Image filters: ignore tiny icons/bullets and full-page scans/backgrounds.
MIN_IMAGE_WIDTH = 15.0
MIN_IMAGE_HEIGHT = 10.0
MAX_IMAGE_PAGE_FRACTION = 0.85

# Vector heuristic: clusters of short, thin horizontal lines (fraction bars).
# Table rules span most of the page width and are filtered out by max width.
VECTOR_LINE_MAX_HEIGHT = 3.0
VECTOR_LINE_MIN_WIDTH = 8.0
VECTOR_LINE_MAX_PAGE_WIDTH_FRACTION = 0.4
VECTOR_CLUSTER_GAP = 6.0  # pt, merge distance between nearby lines
VECTOR_MIN_LINES = 2

# Math-context guards against table rules and chart elements:
# - a real stacked fraction has vertical separation between its bars
#   (chart markers / double-drawn strokes sit at the same y);
# - booktabs-style tables emit several rule clusters with the SAME x-range
#   down the page, fraction bars do not repeat identically;
# - a fraction bar has numerator/denominator text directly above AND below
#   within a small vertical gap, overlapping the bar's x-range.
VECTOR_MIN_VERTICAL_SPAN = 1.0
VECTOR_SAME_X_TOLERANCE = 2.0
VECTOR_TEXT_GAP = 24.0
VECTOR_TEXT_Y_TOLERANCE = 2.0

# Region heuristic (custom-encoded math fonts, e.g. MathematicalPi):
# display equations whose glyphs extract as control characters cannot be
# caught by Unicode heuristics. They ARE locatable by an equation-number
# line — a short line holding only "(N)" (parens may extract as control
# chars) at the right edge of the column. The equation body is the
# nearest line to the LEFT of the number on the same baseline row, plus
# fraction parts stacked directly above/below it. Control characters are
# never decoded — the region goes to the renderer/vision.
REGION_MAX_LINES = 6
REGION_MAX_TEXT_CHARS = 150
REGION_NUMBER_MAX_RAW_LEN = 6
REGION_ROW_CENTER_TOLERANCE = 5.0  # pt, same-baseline-row test
REGION_FALLBACK_ABOVE = 30.0  # pt above the number for tall equations
REGION_SEED_X_TOLERANCE = 8.0  # body must end left of the number (+slack)
REGION_EXPAND_UP = 5.0  # pt above the body union (fraction numerator)
REGION_EXPAND_DOWN = 8.0  # pt below the body union (fraction denominator)
REGION_EXPAND_X = 25.0  # pt horizontal slack around the body's x-range
REGION_MAX_BODY_LINE_CHARS = 55  # prose lines never join the body


class FormulaDetector:
    """Detects formula candidate regions on the pages of an open PDF."""

    def detect(self, doc: pymupdf.Document) -> list[FormulaCandidate]:
        candidates: list[FormulaCandidate] = []
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_number = page_index + 1  # 1-based
            regions = self._detect_regions(page, page_number)
            text_candidates = self._detect_text(page, page_number)
            if regions:
                # A region subsumes any formula_text line inside it (e.g. the
                # numerator line of a custom-font display equation).
                region_boxes = [pymupdf.Rect(r.bbox) for r in regions]
                text_candidates = [
                    c for c in text_candidates
                    if not any(not (box & pymupdf.Rect(c.bbox)).is_empty for box in region_boxes)
                ]
            candidates.extend(text_candidates)
            candidates.extend(self._detect_images(page, page_number))
            candidates.extend(self._detect_vectors(page, page_number))
            candidates.extend(regions)
        return candidates

    # -- formula_text ------------------------------------------------------

    def _detect_text(self, page: pymupdf.Page, page_number: int) -> list[FormulaCandidate]:
        candidates = []
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                if not self.is_formula_line(line):
                    continue
                text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                candidates.append(
                    FormulaCandidate(
                        kind=KIND_TEXT,
                        page=page_number,
                        bbox=[round(v, 2) for v in line["bbox"]],
                        text=text,
                    )
                )
        return candidates

    @staticmethod
    def is_formula_line(line: dict) -> bool:
        """Heuristic: does a text line look like a formula?

        Plain text with digits is NOT a formula. A line qualifies when:
        - it uses a math font (cmmi/cmsy/mathjax/...); or
        - it contains math symbols or Greek letters together with an
          operator or a second math character; or
        - it contains a superscript span plus an operator or math symbol.
        """
        spans = line.get("spans", [])
        text = "".join(span.get("text", "") for span in spans)
        if not text.strip():
            return False

        lower_text = text
        symbol_count = sum(1 for c in lower_text if c in MATH_SYMBOLS)
        greek_count = sum(1 for c in lower_text if c in GREEK)
        mathy = symbol_count + greek_count
        # Math symbols like ≤, ≠, ∫ are themselves operators/relations.
        has_operator = any(c in OPERATORS or c in MATH_SYMBOLS for c in lower_text)
        has_math_font = any(
            marker in (span.get("font") or "").lower()
            for span in spans
            for marker in MATH_FONT_MARKERS
        )
        has_superscript = any(
            (span.get("flags", 0) & SUPERSCRIPT_FLAG) for span in spans
        )

        if has_math_font and mathy + sum(c.isalnum() for c in lower_text) > 0:
            return True
        if mathy >= 1 and (has_operator or mathy >= 2):
            return True
        if has_superscript and (has_operator or mathy >= 1):
            return True
        return False

    # -- formula_image -----------------------------------------------------

    def _detect_images(self, page: pymupdf.Page, page_number: int) -> list[FormulaCandidate]:
        candidates = []
        page_area = abs(page.rect)
        seen: set[tuple] = set()
        for image_info in page.get_images(full=True):
            xref = image_info[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                continue
            for rect in rects:
                if rect.is_empty or rect.is_infinite:
                    continue
                if rect.width < MIN_IMAGE_WIDTH or rect.height < MIN_IMAGE_HEIGHT:
                    continue
                if page_area and abs(rect) > MAX_IMAGE_PAGE_FRACTION * page_area:
                    continue
                key = (round(rect.x0, 1), round(rect.y0, 1), round(rect.x1, 1), round(rect.y1, 1))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    FormulaCandidate(
                        kind=KIND_IMAGE,
                        page=page_number,
                        bbox=[round(v, 2) for v in rect],
                    )
                )
        return candidates

    # -- formula_vector ----------------------------------------------------

    def _detect_vectors(self, page: pymupdf.Page, page_number: int) -> list[FormulaCandidate]:
        max_line_width = page.rect.width * VECTOR_LINE_MAX_PAGE_WIDTH_FRACTION
        lines: list[pymupdf.Rect] = []
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            # Note: degenerate (zero-height) rects are expected for thin
            # lines, so is_empty is NOT used as a filter here.
            if rect is None or rect.is_infinite:
                continue
            if (
                rect.height <= VECTOR_LINE_MAX_HEIGHT
                and VECTOR_LINE_MIN_WIDTH <= rect.width <= max_line_width
            ):
                lines.append(rect)

        clusters = [
            cluster
            for cluster in self._cluster_rects(lines)
            if len(cluster) >= VECTOR_MIN_LINES
        ]
        if not clusters:
            return []
        unions = [self._union_bbox(cluster) for cluster in clusters]
        text_spans = self._page_text_spans(page)

        candidates = []
        for cluster, bbox in zip(clusters, unions):
            x0, y0, x1, y1 = bbox
            # Chart markers / double-drawn strokes: no vertical separation.
            if y1 - y0 < VECTOR_MIN_VERTICAL_SPAN:
                continue
            # Table rule sets repeat with (nearly) the same x-range.
            if any(
                other is not cluster
                and abs(other_bbox[0] - x0) <= VECTOR_SAME_X_TOLERANCE
                and abs(other_bbox[2] - x1) <= VECTOR_SAME_X_TOLERANCE
                for other, other_bbox in zip(clusters, unions)
            ):
                continue
            # Math context: text directly above AND below the bars.
            if not self._has_text_above_and_below(text_spans, bbox):
                continue
            candidates.append(
                FormulaCandidate(
                    kind=KIND_VECTOR,
                    page=page_number,
                    bbox=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                )
            )
        return candidates

    @staticmethod
    def _union_bbox(cluster: list[pymupdf.Rect]) -> tuple[float, float, float, float]:
        # Computed manually: Rect.__or__ ignores degenerate (zero-height)
        # rects, which these thin lines are.
        return (
            min(r.x0 for r in cluster),
            min(r.y0 for r in cluster),
            max(r.x1 for r in cluster),
            max(r.y1 for r in cluster),
        )

    @staticmethod
    def _page_text_spans(page: pymupdf.Page) -> list[tuple[float, float, float, float]]:
        spans = []
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if (span.get("text") or "").strip():
                        spans.append(tuple(span["bbox"]))
        return spans

    @staticmethod
    def _has_text_above_and_below(
        text_spans: list[tuple[float, float, float, float]],
        bbox: tuple[float, float, float, float],
    ) -> bool:
        x0, y0, x1, y1 = bbox
        above = below = False
        for sx0, sy0, sx1, sy1 in text_spans:
            if sx1 < x0 or sx0 > x1:  # must overlap the bars' x-range
                continue
            if sy1 <= y0 + VECTOR_TEXT_Y_TOLERANCE and y0 - sy1 <= VECTOR_TEXT_GAP:
                above = True
            elif sy0 >= y1 - VECTOR_TEXT_Y_TOLERANCE and sy0 - y1 <= VECTOR_TEXT_GAP:
                below = True
            if above and below:
                return True
        return False

    @staticmethod
    def _cluster_rects(rects: list[pymupdf.Rect]) -> list[list[pymupdf.Rect]]:
        """Greedy merge of rects that nearly touch (fraction-bar stacking).

        Grown copies are used for the intersection test because the raw
        rects are degenerate (zero height) and never intersect directly.
        """
        gap = (-VECTOR_CLUSTER_GAP, -VECTOR_CLUSTER_GAP,
               VECTOR_CLUSTER_GAP, VECTOR_CLUSTER_GAP)
        clusters: list[list[pymupdf.Rect]] = []
        grown_unions: list[pymupdf.Rect] = []
        for rect in rects:
            grown = rect + gap
            placed = False
            for cluster, grown_union in zip(clusters, grown_unions):
                if not (grown_union & grown).is_empty:
                    cluster.append(rect)
                    grown_union |= rect + gap
                    placed = True
                    break
            if not placed:
                clusters.append([rect])
                grown_unions.append(rect + gap)
        return clusters

    # -- formula_region (custom-encoded math fonts) ---------------------------

    def _detect_regions(self, page: pymupdf.Page, page_number: int) -> list[FormulaCandidate]:
        """Locate display equations set in custom-encoded math fonts.

        Such equations (e.g. MathematicalPi) extract as control characters
        and are invisible to Unicode heuristics. The anchor is the equation
        NUMBER: a short line containing only "(N)" — parens may themselves
        extract as control chars. The body is the nearest line to the left
        of the number on the same baseline row, plus fraction parts stacked
        directly above/below it. Control characters are never decoded; the
        region is left for the renderer/vision stage.
        """
        lines = self._page_text_lines(page)
        candidates = []
        claimed: set[int] = set()
        accepted: list[pymupdf.Rect] = []
        for index, line in enumerate(lines):
            if index in claimed or not self._is_equation_number_line(line):
                continue
            group = self._collect_region_lines(lines, index)
            if group is None:
                continue
            x0 = min(lines[i]["bbox"][0] for i in group)
            y0 = min(lines[i]["bbox"][1] for i in group)
            x1 = max(lines[i]["bbox"][2] for i in group)
            y1 = max(lines[i]["bbox"][3] for i in group)
            bbox = pymupdf.Rect(x0, y0, x1, y1)
            if any(not (bbox & other).is_empty for other in accepted):
                continue  # overlapping anchors describe the same equation
            candidates.append(FormulaCandidate(
                kind=KIND_REGION,
                page=page_number,
                bbox=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
            ))
            accepted.append(bbox)
            claimed.update(group)
            claimed.add(index)
        return candidates

    @staticmethod
    def _page_text_lines(page: pymupdf.Page) -> list[dict]:
        lines = []
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if (s.get("text") or "").strip()]
                if spans:
                    lines.append({"bbox": tuple(line["bbox"]), "spans": spans})
        return lines

    @staticmethod
    def _line_text(line: dict) -> str:
        return "".join(s.get("text", "") for s in line["spans"])

    @staticmethod
    def _is_equation_number_line(line: dict) -> bool:
        """A line holding only an equation number like "(6)".

        Digits and parens; parens may be control chars from a custom font
        encoding, so those are allowed but never interpreted. A paren (or
        its control-char form) is REQUIRED — bare digits are axis tick
        labels and section numbers, not equation numbers.
        """
        raw = FormulaDetector._line_text(line).strip()
        if not raw or len(raw) > REGION_NUMBER_MAX_RAW_LEN:
            return False
        if not all(c.isdigit() or c in "()" or ord(c) < 32 for c in raw):
            return False
        if not any(c in "()" or ord(c) < 32 for c in raw):
            return False
        digits = sum(c.isdigit() for c in raw)
        return 1 <= digits <= 3

    @staticmethod
    def _has_custom_math_glyphs(line: dict) -> bool:
        """Control chars in extracted text = custom-encoded math glyphs."""
        return any(
            ord(c) < 32
            for span in line["spans"]
            for c in span.get("text", "")
        )

    @staticmethod
    def _collect_region_lines(lines: list[dict], number_index: int) -> list[int] | None:
        """Equation body lines for a number line, or None if not an equation.

        1. row = custom-math lines on the number's baseline row, ending
           left of the number (multi-line equation rows all join);
        2. fallback for tall equations: custom-math lines strictly above
           the number within a small window;
        3. body = row + short lines stacked directly above/below the row
           union (fraction parts, sum limits); prose never joins.
        """
        num_bbox = lines[number_index]["bbox"]
        num_center_y = (num_bbox[1] + num_bbox[3]) / 2
        max_body_x1 = num_bbox[0] + REGION_SEED_X_TOLERANCE

        def row_candidate(i: int, center_y: float) -> bool:
            line = lines[i]
            return (
                line["bbox"][2] <= max_body_x1
                and len(FormulaDetector._line_text(line)) <= REGION_MAX_BODY_LINE_CHARS
                and FormulaDetector._has_custom_math_glyphs(line)
            )

        row = [
            i for i, line in enumerate(lines)
            if i != number_index
            and abs((line["bbox"][1] + line["bbox"][3]) / 2 - num_center_y)
                <= REGION_ROW_CENTER_TOLERANCE
            and row_candidate(i, num_center_y)
        ]
        if not row:
            # Tall equation (big operators): the number is vertically
            # centered on the whole equation, its main row sits higher.
            row = [
                i for i, line in enumerate(lines)
                if i != number_index
                and (REGION_ROW_CENTER_TOLERANCE
                     < num_center_y - (line["bbox"][1] + line["bbox"][3]) / 2
                     <= REGION_FALLBACK_ABOVE)
                and row_candidate(i, num_center_y)
            ]
        if not row:
            return None

        ux0 = min(lines[i]["bbox"][0] for i in row)
        uy0 = min(lines[i]["bbox"][1] for i in row)
        ux1 = max(lines[i]["bbox"][2] for i in row)
        uy1 = max(lines[i]["bbox"][3] for i in row)
        band_y0, band_y1 = uy0 - REGION_EXPAND_UP, uy1 + REGION_EXPAND_DOWN

        body = list(row)
        for i, line in enumerate(lines):
            if i == number_index or i in row:
                continue
            x0, y0, x1, y1 = line["bbox"]
            if x1 > max_body_x1 or y0 > band_y1 or y1 < band_y0:
                continue
            center_x = (x0 + x1) / 2
            if not (ux0 - REGION_EXPAND_X <= center_x <= ux1 + REGION_EXPAND_X):
                continue
            if len(FormulaDetector._line_text(line)) > REGION_MAX_BODY_LINE_CHARS:
                continue
            body.append(i)

        if len(body) > REGION_MAX_LINES:
            return None
        if sum(len(FormulaDetector._line_text(lines[i])) for i in body) > REGION_MAX_TEXT_CHARS:
            return None
        return body
