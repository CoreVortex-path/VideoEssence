from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .ai_provider import BaseAIProvider
from ..config.ai_token_limits import TokenLimits, get_limits as _get_limits

_OPENROUTER_PROFILE_ID = "openrouter_default"


class OpenRouterAIProvider(BaseAIProvider):
    # Hard provider-level guardrails (not per-operation budgets).
    # 8192 matches the enrichment/summary budgets in ai_token_limits.py;
    # the previous 250 clamp truncated every longer operation mid-output.
    MAX_ALLOWED_TOKENS = 8192
    MIN_ALLOWED_TOKENS = 128

    def __init__(
        self,
        api_key: str,
        model_name: str = "openai/gpt-4o-mini",
        token_limits: TokenLimits | None = None,
    ):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is empty")
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.limits: TokenLimits = token_limits or _get_limits(_OPENROUTER_PROFILE_ID)

    def summarize(self, text: str) -> str:
        prompt = f"""
You are an expert technical analyst.
Write a concise summary in the same language as the transcript.
Avoid repetition.

Transcript:
{text}
"""
        return self.generate_text(prompt, max_tokens=self.limits.SUMMARY)

    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        if max_tokens is None:
            raise ValueError("OpenRouter generate_text requires explicit max_tokens")
        return self._chat_text(prompt, max_tokens=max_tokens)

    def supports_image_input(self) -> bool:
        return True

    def generate_text_for_image(
        self, prompt: str, image_path: Path, max_tokens: int | None = None
    ) -> str:
        """Vision call via OpenAI-compatible content parts.

        Note: the profile's model must be vision-capable (e.g.
        or_gemini_flash); text-only models fail at the API level and the
        caller treats that as a best-effort failure.
        """
        encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{encoded}"},
                    },
                ],
            }
        ]
        return self._chat_messages(
            messages, max_tokens=max_tokens or self.limits.FORMULA_VISION
        )

    def summarize_with_chapters(
        self,
        transcript_segments: list[dict[str, Any]],
        source_language: str | None = None,
    ) -> dict[str, Any]:
        if not transcript_segments:
            raise ValueError("Transcript segments are empty")

        timestamped_transcript = "\\n".join(
            f"[{self._sec_to_ts(float(seg['start']))}] {str(seg.get('text', '')).strip()}"
            for seg in transcript_segments
            if str(seg.get("text", "")).strip()
        )
        available_starts = [round(float(seg["start"]), 3) for seg in transcript_segments]

        normalized_language = (source_language or "").strip().lower()
        language_instruction = (
            f"The transcript language is '{normalized_language}'. Write all fields (summary, chapters, keywords, suggested_questions) in this language."
            if normalized_language
            else "Write all fields (summary, chapters, keywords, suggested_questions) in the same language as the transcript."
        )

        prompt = f"""
You are given a transcript with trusted timestamps.

Task:
1. Write a concise summary.
2. Build chapter list for navigation.
3. Extract 5-8 key terms or short noun phrases (1-3 words) of the document.
4. Suggest 2-3 questions a viewer may ask, each answerable from the transcript (max 15 words).

Language rule:
- {language_instruction}

Critical rules:
- Do not invent timestamps.
- Every chapter.start must be one of existing start values.

Existing starts:
{available_starts}

Transcript:
{timestamped_transcript}

Return strict JSON only:
{{
  "summary": "string",
  "chapters": [
    {{"title": "string", "summary": "string", "start": 0.0}}
  ],
  "keywords": ["string"],
  "suggested_questions": ["string"],
  "language": "string"
}}
"""
        raw = self._chat_text(prompt, max_tokens=self.limits.SUMMARY_WITH_CHAPTERS)
        payload = self._load_json(raw)

        summary = (payload.get("summary") or "").strip()
        language = (payload.get("language") or "").strip() or normalized_language or None
        chapters_raw = payload.get("chapters") or []

        if not summary:
            raise ValueError("OpenRouter did not return summary")

        start_set = set(available_starts)
        chapters: list[dict[str, Any]] = []
        for item in chapters_raw:
            try:
                raw_start = item.get("start")
                if raw_start is None:
                    continue
                start = round(float(raw_start), 3)
            except Exception:
                continue
            if start not in start_set:
                continue
            title = str(item.get("title", "")).strip()
            chapter_summary = str(item.get("summary", "")).strip()
            if not title or not chapter_summary:
                continue
            chapters.append({"title": title, "summary": chapter_summary, "start": start})

        chapters.sort(key=lambda x: x["start"])
        if not chapters:
            chapters = [{"title": "Full Video", "summary": summary, "start": available_starts[0]}]

        return {
            "summary": summary,
            "chapters": chapters,
            "keywords": self.normalize_str_list(payload.get("keywords"), 10),
            "suggested_questions": self.normalize_str_list(payload.get("suggested_questions"), 3),
            "language": language,
        }

    def translate_text(self, text: str, target_language: str) -> str:
        cleaned_text = (text or "").strip()
        cleaned_target_language = (target_language or "").strip()
        if not cleaned_text:
            raise ValueError("Text to translate is empty")
        if not cleaned_target_language:
            raise ValueError("Target language is empty")

        prompt = f"""
Translate the text below into {cleaned_target_language}.

Rules:
- Preserve meaning.
- Keep timestamps, numbers, filenames, URLs, code identifiers, and proper nouns unchanged unless natural translation is required.
- Return only the translated text.

Text:
{cleaned_text}
"""
        translated = self.generate_text(prompt, max_tokens=self.limits.TRANSLATION).strip()
        if not translated:
            raise ValueError("OpenRouter returned empty translation")
        return translated

    def _chat_text(self, prompt: str, max_tokens: int) -> str:
        return self._chat_messages(
            [{"role": "user", "content": prompt}], max_tokens=max_tokens
        )

    def _chat_messages(self, messages: list[dict[str, Any]], max_tokens: int) -> str:
        capped_max_tokens = max(self.MIN_ALLOWED_TOKENS, min(int(max_tokens), self.MAX_ALLOWED_TOKENS))

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": capped_max_tokens,
        }
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "VideoEssense",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            err_text = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            raise RuntimeError(f"OpenRouter request failed ({e.code}): {err_text[:500]}") from e
        except Exception as e:
            raise RuntimeError(f"OpenRouter request failed: {e}") from e

        try:
            data = json.loads(body)
            text = data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"OpenRouter response parse failed: {body[:500]}") from e

        return (text or "").strip()

    @staticmethod
    def _load_json(text: str) -> dict[str, Any]:
        result = OpenRouterAIProvider.parse_ai_json(text)
        if isinstance(result, dict):
            return result
        return {"data": result}

    @staticmethod
    def _sec_to_ts(seconds: float) -> str:
        total = max(0, int(seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
