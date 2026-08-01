from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from ..config.settings import settings
from .ai_text_generator import AITextGenerator


class BaseAIProvider(AITextGenerator, ABC):
    """Abstract AI provider. Implementations should be replaceable.

    Inherits AITextGenerator so every concrete provider is automatically
    usable wherever the port interface is required.
    """

    @abstractmethod
    def summarize(self, text: str) -> str:
        raise NotImplementedError()

    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        """Generic text generation entrypoint used by specialized services."""
        raise NotImplementedError()

    @staticmethod
    def parse_ai_json(text: str) -> dict[str, Any] | list[Any]:
        """Robustly parse a JSON response from an AI model.

        Handles common AI model quirks:
        - Markdown code fences (```json ... ```)
        - Leading/trailing prose around the JSON block
        - JavaScript-style NaN / Infinity / -Infinity values (replaced with null)
        - Truncated or incomplete JSON raises JSONDecodeError normally
        """
        import datetime
        import pathlib

        raw = text or ""

        # ── Diagnostics: log the raw AI response before any modification ─────
        _log_dir = pathlib.Path("data/logs")
        try:
            _log_dir.mkdir(parents=True, exist_ok=True)
            _ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            _log_path = _log_dir / f"ai_response_{_ts}.txt"
            _log_lines = [
                f"=== AI RESPONSE DIAGNOSTIC: {_ts} ===",
                f"Total length (chars): {len(raw)}",
                f"--- First 500 chars ---",
                raw[:500],
                f"--- Last 500 chars ---",
                raw[-500:] if len(raw) > 500 else "(same as above — response shorter than 500 chars)",
                f"--- Starts with backtick: {raw.lstrip().startswith('`')} ---",
                f"--- Contains NaN: {'NaN' in raw} ---",
                f"--- Contains Infinity: {'Infinity' in raw} ---",
                f"=== END HEADER ===",
                "",
                raw,  # full untruncated response
            ]
            _log_path.write_text("\n".join(_log_lines), encoding="utf-8")
            print(f"[AI_JSON_DIAG] Response logged to {_log_path} (len={len(raw)})")
        except Exception as _log_err:
            print(f"[AI_JSON_DIAG] Could not write diagnostic log: {_log_err}")
        # ── End diagnostics ───────────────────────────────────────────────────

        cleaned = raw.strip()

        # Strip markdown fences.
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # Replace bare JS/Python non-JSON literals with null.
        # Order in the alternation matters: -Infinity must be tried before Infinity.
        cleaned = re.sub(r"\bNaN\b|-Infinity\b|\bInfinity\b", "null", cleaned)

        # First attempt: direct parse.
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Second attempt: find outermost { } or [ ] block to skip surrounding prose.
        for open_char, close_char in (("{", "}"), ("[", "]")):
            start = cleaned.find(open_char)
            end = cleaned.rfind(close_char)
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    continue

        # ── Diagnostics: save the raw response as a named failure artifact ───
        try:
            _fail_path = pathlib.Path("data/logs") / "failed_ai_response.json"
            _fail_path.write_text(raw, encoding="utf-8")
            print(f"[AI_JSON_DIAG] Parse FAILED. Full raw response saved to {_fail_path}")
        except Exception as _save_err:
            print(f"[AI_JSON_DIAG] Could not save failed_ai_response.json: {_save_err}")
        # ── End failure diagnostics ───────────────────────────────────────────

        raise json.JSONDecodeError(
            f"Could not parse AI JSON response (first 200 chars): {cleaned[:200]}",
            cleaned,
            0,
        )


class DummyAIProvider(BaseAIProvider):
    def summarize(self, text: str) -> str:
        # Trivial summarization for offline development
        return text[: min(len(text), 400)] + ("..." if len(text) > 400 else "")

    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        return self.summarize(prompt)


@dataclass(frozen=True)
class AIProfile:
    id: str
    display_name: str
    provider: str
    model: str


class AIProviderConfigurationError(RuntimeError):
    pass


DEFAULT_AI_PROFILE_ID = "gemini_flash"

AI_PROFILES: dict[str, AIProfile] = {
    "gemini_flash": AIProfile(
        id="gemini_flash",
        display_name="Gemini Flash",
        provider="gemini",
        model="gemini-2.5-flash",
    ),
    "gemini_pro": AIProfile(
        id="gemini_pro",
        display_name="Gemini Pro",
        provider="gemini",
        model="gemini-2.5-pro",
    ),
    "openrouter_default": AIProfile(
        id="openrouter_default",
        display_name="OpenRouter",
        provider="openrouter",
        model=settings.openrouter_model,
    ),
}

AI_PROFILE_ALIASES: dict[str, str] = {
    "gemini_flash": "gemini_flash",
    "gemini": "gemini_flash",
    "gemini_pro": "gemini_pro",
    "openrouter": "openrouter_default",
    "openrouter_default": "openrouter_default",
}


def is_quota_error(error: Exception) -> bool:
    msg = str(error)
    return (
        "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "Quota" in msg
        or "quota" in msg
    )


def resolve_ai_profile(profile_id: str | None) -> AIProfile:
    normalized = (profile_id or DEFAULT_AI_PROFILE_ID).strip().lower()
    resolved_id = AI_PROFILE_ALIASES.get(normalized)
    if not resolved_id:
        allowed = ", ".join(AI_PROFILES.keys())
        raise AIProviderConfigurationError(
            f"Unsupported ai_profile '{profile_id}'. Supported values: {allowed}"
        )
    return AI_PROFILES[resolved_id]


def build_ai_provider(profile: AIProfile) -> BaseAIProvider:
    from ..config.ai_token_limits import get_limits
    limits = get_limits(profile.id)

    if profile.provider == "gemini":
        if not settings.google_api_key:
            raise AIProviderConfigurationError("GOOGLE_API_KEY is empty. Gemini profile is unavailable.")
        from .google_provider import GoogleAIProvider
        return GoogleAIProvider(api_key=settings.google_api_key, model_name=profile.model, token_limits=limits)

    if profile.provider == "openrouter":
        if not settings.openrouter_api_key:
            raise AIProviderConfigurationError("OPENROUTER_API_KEY is empty. OpenRouter profile is unavailable.")
        from .openrouter_provider import OpenRouterAIProvider
        return OpenRouterAIProvider(api_key=settings.openrouter_api_key, model_name=profile.model, token_limits=limits)

    raise AIProviderConfigurationError(f"Unsupported provider '{profile.provider}' in profile '{profile.id}'")


def get_ai_provider(profile_id: str | None) -> tuple[AIProfile, BaseAIProvider]:
    profile = resolve_ai_profile(profile_id)
    provider = build_ai_provider(profile)
    return profile, provider


def get_ai_profiles_payload() -> dict[str, Any]:
    return {
        "default_profile": DEFAULT_AI_PROFILE_ID,
        "profiles": [
            {
                "id": p.id,
                "display_name": p.display_name,
                "provider": p.provider,
                "model": p.model,
            }
            for p in AI_PROFILES.values()
        ],
    }


def to_user_facing_ai_error(profile: AIProfile | None, error: Exception) -> str:
    if profile and profile.provider == "gemini" and is_quota_error(error):
        return "Квота Gemini исчерпана. Выберите OpenRouter или повторите попытку позже."
    return str(error)


def get_default_ai_provider() -> BaseAIProvider:
    try:
        _profile, provider = get_ai_provider(DEFAULT_AI_PROFILE_ID)
        return provider
    except Exception as e:
        print(f"⚠️ Failed to initialize default AI profile: {e}. Falling back to DummyAIProvider.")
        return DummyAIProvider()
