"""Formula recognition port: image of a formula region -> LaTeX.

FormulaVisionService depends only on the FormulaRecognizer interface,
never on a concrete AI provider. Implementations:

- AIProviderFormulaRecognizer — wraps any BaseAIProvider with image
  support (Gemini, OpenRouter vision models);
- (future) a local pix2tex-based recognizer can implement the same port
  without touching the vision service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .ai_provider import BaseAIProvider

# Prompt-versioned contract: any change here must bump
# PROMPT_VERSION_FORMULA_LATEX in formula_vision_service (ADR-0004).
FORMULA_LATEX_PROMPT = """
Transcribe the mathematical formula in this image into LaTeX.

Rules:
- Return ONLY the LaTeX code, no explanations, no markdown fences.
- Do not wrap the result in $ or $$ delimiters.
- If the image contains no recognizable formula, return exactly: UNRECOGNIZED
""".strip()

UNRECOGNIZED_MARKER = "UNRECOGNIZED"


class FormulaRecognizer(ABC):
    """Minimal port: one formula region image in, LaTeX string out."""

    @abstractmethod
    def recognize_latex(self, image_path: Path) -> str:
        """Return LaTeX for the formula in the image.

        Raises on provider/transport errors; returns the
        UNRECOGNIZED_MARKER when no formula is visible.
        """
        raise NotImplementedError()


class AIProviderFormulaRecognizer(FormulaRecognizer):
    """Formula recognition via any image-capable BaseAIProvider."""

    def __init__(self, provider: BaseAIProvider, max_tokens: int) -> None:
        self._provider = provider
        self._max_tokens = max_tokens

    def recognize_latex(self, image_path: Path) -> str:
        return self._provider.generate_text_for_image(
            FORMULA_LATEX_PROMPT, image_path, max_tokens=self._max_tokens
        )
