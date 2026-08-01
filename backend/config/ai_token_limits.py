"""
Centralized max_tokens budgets for every AI operation type.

Each operation is a named field on TokenLimits.  Providers and services
import this module instead of defining class-level magic numbers.

Per-profile overrides live in PROFILE_OVERRIDES — add a new entry here
to tune limits for a specific AI profile without touching any
business-logic code.

Usage::

    from ..config.ai_token_limits import get_limits

    limits = get_limits(profile_id)          # resolves overrides
    provider.summarize(text, max_tokens=limits.SUMMARY)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenLimits:
    """Max output token budgets for each AI operation.

    All values are *output* token ceilings; prompt/input tokens are not
    counted here.  Adjust a value in PROFILE_OVERRIDES to change behaviour
    for a specific AI profile without touching provider or service code.
    """

    # Translation of transcript segments (per-batch output)
    TRANSLATION: int = 700
    # Plain summary (no chapter breakdown)
    SUMMARY: int = 1200
    # Summary with timestamped chapter navigation.
    # Gemini 2.5 thinking models count reasoning ("thought") tokens against
    # max_output_tokens, so the visible JSON output only gets what thinking
    # leaves behind. A tight budget here truncates the response mid-JSON
    # (finish_reason=MAX_TOKENS) on longer transcripts; 8192 matches the
    # provider-level hard cap and leaves ample headroom for thinking.
    SUMMARY_WITH_CHAPTERS: int = 8192
    # Gemini one-shot transcribe + summarize pass
    TRANSCRIBE_AND_SUMMARIZE: int = 2200
    # Enrichment batch — lower and upper bounds used by the dynamic estimator.
    # The estimator sizes only the *visible* JSON output, but on Gemini 2.5
    # thinking models the reasoning ("thought") tokens are billed from the
    # same max_output_tokens budget, so batches truncated mid-JSON
    # (finish_reason=MAX_TOKENS) at the old 1024–4096 bounds. The bounds now
    # include headroom for thinking; 8192 matches the provider hard cap.
    ENRICHMENT_MIN: int = 2048
    ENRICHMENT_MAX: int = 8192
    # General-purpose chat / Q&A
    CHAT: int = 1024
    # Future operations (reserved for upcoming features)
    MIND_MAP: int = 2048
    CONCEPT_EXTRACTION: int = 1024
    FLASHCARDS: int = 1024


# Baseline used when no profile-specific override exists.
DEFAULT: TokenLimits = TokenLimits()

# Per-profile overrides.  Keys must match AIProfile.id values defined in
# ai_provider.py.  Only profiles that need different budgets need entries here.
PROFILE_OVERRIDES: dict[str, TokenLimits] = {
    # OpenRouter charges per token — use tighter defaults to avoid 402 errors.
    "openrouter_default": TokenLimits(
        TRANSLATION=700,
        SUMMARY=900,
        SUMMARY_WITH_CHAPTERS=1800,
        TRANSCRIBE_AND_SUMMARIZE=2000,
        ENRICHMENT_MIN=1024,
        ENRICHMENT_MAX=8192,
        CHAT=1024,
        MIND_MAP=2048,
        CONCEPT_EXTRACTION=1024,
        FLASHCARDS=1024,
    ),
}


def get_limits(profile_id: str | None = None) -> TokenLimits:
    """Return token limits for *profile_id*, falling back to DEFAULT."""
    if profile_id:
        override = PROFILE_OVERRIDES.get(profile_id)
        if override is not None:
            return override
    return DEFAULT
