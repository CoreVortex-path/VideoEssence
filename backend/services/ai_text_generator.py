from __future__ import annotations

from abc import ABC, abstractmethod


class AITextGenerator(ABC):
    """Port for single-turn text generation used by application services.

    Application services depend only on this interface; the concrete AI
    provider is resolved at the composition root (route layer) and injected
    as a callable factory — ``Callable[[profile_id | None], tuple[Any, AITextGenerator]]``.
    This keeps services testable without real API keys and makes swapping
    providers (or adding RAG pre-processing) a composition-root concern.
    """

    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        """Generate a text response for the given prompt."""
        raise NotImplementedError()
