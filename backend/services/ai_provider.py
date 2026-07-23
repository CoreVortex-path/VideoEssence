from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from ..config.settings import settings


class BaseAIProvider(ABC):
    """Abstract AI provider. Implementations should be replaceable.

    Keep interface minimal: `summarize(text) -> str` for now.
    """

    @abstractmethod
    def summarize(self, text: str) -> str:
        raise NotImplementedError()


class DummyAIProvider(BaseAIProvider):
    def summarize(self, text: str) -> str:
        # Trivial summarization for offline development
        return text[: min(len(text), 400)] + ("..." if len(text) > 400 else "")


def get_default_ai_provider() -> BaseAIProvider:
    try:
        if settings.google_api_key:
            from .google_provider import GoogleAIProvider
            print("✅ Using Google Gemini")
            return GoogleAIProvider(api_key=settings.google_api_key)
            
    except Exception as e:
        print(f"❌ Ошибка при инициализации Google Gemini: {e}")
        raise RuntimeError(f"Failed to initialize Google Gemini provider: {e}") from e

    # Если settings.google_api_key пустой (ИИ не настроен), 
    # код не зайдет в if и корректно вернет заглушку здесь:
    print("⚠️ Ключ Google API не найден. Используется DummyAIProvider.")
    return DummyAIProvider()

