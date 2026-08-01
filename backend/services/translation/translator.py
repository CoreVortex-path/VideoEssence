from __future__ import annotations

from ..ai_provider import BaseAIProvider


class Translator:
    """Тонкая обёртка над AI-провайдером: prompt -> raw text.

    Никакой логики батчинга или парсинга. Ретраи по квоте (429) живут
    внутри провайдера — он знает retryDelay из ответа API.
    """

    def __init__(self, ai_provider: BaseAIProvider, max_tokens: int = 8192) -> None:
        self.ai_provider = ai_provider
        self.max_tokens = max_tokens

    def translate(self, prompt: str) -> str:
        return self.ai_provider.generate_text(prompt, max_tokens=self.max_tokens)
