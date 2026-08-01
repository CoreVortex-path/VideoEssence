import re
import time
from pathlib import Path
from typing import Any
from google import genai
from google.genai import types

from .ai_provider import BaseAIProvider
from ..config.ai_token_limits import TokenLimits, DEFAULT as _DEFAULT_LIMITS


class GoogleAIProvider(BaseAIProvider):
    # Provider-level hard cap to prevent accidental oversized requests.
    MAX_ALLOWED_TOKENS = 8192

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        token_limits: TokenLimits = _DEFAULT_LIMITS,
    ):
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is empty")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.limits = token_limits
        self.fallback_models: list[str] = []
        # Retry transient per-minute quota windows (429 with a short retryDelay);
        # daily free-tier exhaustion still fails fast (see _generate_content).
        self.max_quota_retries = 4

    def summarize(self, text: str) -> str:

        prompt = f"""
You are an expert technical analyst. Your task is to extract unique, actionable insights from the provided video transcript.

### CRITICAL REQUIREMENTS:
1. LANGUAGE: You MUST write the entire output in the same language as the source text/video. (If the transcript is in Russian, write in Russian).
2. CONCISENESS & NO REPETITION: Do not repeat the same ideas across different sections. Each bullet point must contain new, distinct information.
3. ADAPTABILITY: Match the length of your response to the length and density of the video. If the video is short or simple, combine points, keep sections brief, and do not invent padding.

### OUTPUT STRUCTURE:

# Основные тезисы
[Deliver a single, high-density bulleted list combining the main lessons, technical facts, and metrics. Do not split facts and takeaways if it causes duplication. Merge them here. Max 3-5 points for short videos, up to 8 for long ones.Be carefull transcrit can рфы typo/incorrect text recognition)]

# Заключение
[A 1-sentence final verdict or forward-looking conclusion. Do not summarize what you already wrote; state the ultimate significance of the video.]

Transcript:

{text}
"""

        return self.generate_text(prompt, max_tokens=self.limits.SUMMARY)

    def generate_text(self, prompt: str, max_tokens: int | None = None) -> str:
        response = self._generate_content(contents=prompt, max_tokens=max_tokens)
        output = (response.text or "").strip()
        if not output:
            raise ValueError("Gemini returned empty text response")
        return output

    def transcribe_and_summarize_file(self, file_path: str) -> dict[str, Any]:
        """Use Gemini Files API to produce transcript and summary in one model pass."""
        media_path = Path(file_path)
        uploaded_file = self.client.files.upload(file=str(media_path))

        prompt = """
You are a precise media analyst.

Task:
1. Create a full transcript from the provided audio/video.
2. Create a concise summary in the same language as the media.

Return strict JSON only with this schema:
{
  "transcript": "string",
  "summary": "string",
  "language": "string"
}

Rules:
- Do not wrap JSON in markdown.
- "summary" should be actionable, non-repetitive, and structured with short bullet lines separated by "\\n".
- "language" should be a language name (e.g., "Russian", "English").
"""

        response = self._generate_content(
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=self.limits.TRANSCRIBE_AND_SUMMARIZE,
            ),
        )

        text = (response.text or "").strip()
        if not text:
            raise ValueError("Gemini returned empty response")

        payload = self.parse_ai_json(text)
        transcript = (payload.get("transcript") or "").strip()
        summary = (payload.get("summary") or "").strip()
        language = (payload.get("language") or "").strip() or None

        if not transcript:
            raise ValueError("Gemini did not return transcript")
        if not summary:
            raise ValueError("Gemini did not return summary")

        return {
            "transcript": transcript,
            "summary": summary,
            "language": language,
        }

    def summarize_with_chapters(
        self,
        transcript_segments: list[dict[str, Any]],
        source_language: str | None = None,
    ) -> dict[str, Any]:
        """Summarize timestamped transcript and build chapters with existing timestamps only."""
        if not transcript_segments:
            raise ValueError("Transcript segments are empty")

        timestamped_transcript = "\n".join(
            f"[{self._sec_to_ts(float(seg['start']))}] {str(seg.get('text', '')).strip()}"
            for seg in transcript_segments
            if str(seg.get("text", "")).strip()
        )

        available_starts = [round(float(seg["start"]), 3) for seg in transcript_segments]
        segment_count = len(transcript_segments)
        if segment_count < 25:
            target_chapter_count = 3
        elif segment_count < 80:
            target_chapter_count = 5
        else:
            target_chapter_count = 7

        normalized_language = (source_language or "").strip().lower()
        language_instruction = (
            f"The transcript language detected by ASR is '{normalized_language}'. "
            "You must write every textual field (summary, chapter.title, chapter.summary) in this exact language."
            if normalized_language
            else "Write every textual field (summary, chapter.title, chapter.summary) in the same language as the transcript."
        )

        prompt = f"""
You are given a transcript that already contains trusted timestamps from speech recognition.

Task:
1. Write a concise summary in the source transcript language.
2. Build a chapter list for interactive navigation.

Language rule:
- {language_instruction}

Critical rule:
- Do not invent timestamps.
- Every chapter.start must be one of the existing segment start values.

Chapter granularity rules:
- Create high-level sections, not one chapter per transcript line.
- Return at most {target_chapter_count} chapters.
- Each chapter title: max 6 words.
- Each chapter summary: max 14 words, one sentence.
- Avoid repeating the same idea across chapters.

Existing segment starts (seconds):
{available_starts}

Transcript with timestamps:
{timestamped_transcript}

Return strict JSON only:
{{
  "summary": "string",
  "chapters": [
    {{"title": "string", "summary": "string", "start": 0.0}}
  ],
  "language": "string"
}}

Rules:
- No markdown wrappers.
- chapters must be ordered by start ascending.
- chapter summaries should be short and actionable.
"""

        response = self._generate_content(
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=self.limits.SUMMARY_WITH_CHAPTERS,
            ),
        )

        text = (response.text or "").strip()
        if not text:
            raise ValueError("Gemini returned empty response")

        payload = self.parse_ai_json(text)

        summary = (payload.get("summary") or "").strip()
        language = (payload.get("language") or "").strip() or normalized_language or None
        chapters_raw = payload.get("chapters") or []

        if not summary:
            raise ValueError("Gemini did not return summary")

        start_set = set(available_starts)
        chapters: list[dict[str, Any]] = []
        seen_starts: set[float] = set()
        for item in chapters_raw:
            try:
                raw_start = item.get("start")
                if raw_start is None:
                    continue
                start = round(float(raw_start), 3)
            except (TypeError, ValueError):
                continue
            if start not in start_set:
                continue
            if start in seen_starts:
                continue
            title = str(item.get("title", "")).strip()
            chapter_summary = str(item.get("summary", "")).strip()
            if not title or not chapter_summary:
                continue

            title_words = title.split()
            if len(title_words) > 6:
                title = " ".join(title_words[:6])

            summary_words = chapter_summary.split()
            if len(summary_words) > 14:
                chapter_summary = " ".join(summary_words[:14]).rstrip(".,;:!?") + "."

            chapters.append(
                {
                    "title": title,
                    "summary": chapter_summary,
                    "start": start,
                }
            )
            seen_starts.add(start)

        chapters.sort(key=lambda x: x["start"])
        chapters = chapters[:target_chapter_count]
        if not chapters:
            # Fallback to first segment start without inventing a new timestamp.
            chapters = [
                {
                    "title": "Full Video",
                    "summary": summary,
                    "start": available_starts[0],
                }
            ]

        return {
            "summary": summary,
            "chapters": chapters,
            "language": language,
        }

    def translate_text(self, text: str, target_language: str) -> str:
        """Translate arbitrary text to the requested language using Gemini."""
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

        return self.generate_text(prompt, max_tokens=self.limits.TRANSLATION)

    @staticmethod
    def _sec_to_ts(seconds: float) -> str:
        total = max(0, int(seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _generate_content(self, contents: Any, config: Any | None = None, max_tokens: int | None = None) -> Any:
        models_to_try = [self.model_name, *self.fallback_models]
        last_quota_error: Exception | None = None
        effective_config = config
        if effective_config is None and max_tokens is not None:
            effective_config = types.GenerateContentConfig(max_output_tokens=max_tokens)

        for model in models_to_try:
            for attempt in range(self.max_quota_retries + 1):
                try:
                    return self.client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=effective_config,
                    )
                except Exception as e:
                    if self._is_quota_error(e):
                        last_quota_error = e
                        if self._is_daily_quota_error(e):
                            # Daily free-tier quota: fail fast for this model to avoid wasting attempts.
                            break
                        retry_seconds = self._extract_retry_delay_seconds(e)
                        can_retry_same_model = (
                            attempt < self.max_quota_retries
                            and retry_seconds is not None
                            and retry_seconds <= 60
                        )
                        if can_retry_same_model:
                            time.sleep(min(max(retry_seconds, 1), 60))
                            continue
                        break
                    raise RuntimeError(f"Gemini request failed: {e}") from e

        raise RuntimeError(self._format_quota_error(last_quota_error, models_to_try))

    @staticmethod
    def _is_quota_error(error: Exception) -> bool:
        message = str(error)
        return (
            "429" in message
            or "RESOURCE_EXHAUSTED" in message
            or "Quota" in message
            or "quota" in message
        )

    @staticmethod
    def _extract_retry_delay_seconds(error: Exception) -> int | None:
        message = str(error)
        patterns = [
            r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s",
            r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    return int(float(match.group(1)) + 0.999)
                except Exception:
                    continue
        return None

    @staticmethod
    def _is_daily_quota_error(error: Exception) -> bool:
        message = str(error)
        return (
            "GenerateRequestsPerDayPerProjectPerModel-FreeTier" in message
            or "per day" in message.lower()
            or "current quota" in message.lower()
        )

    def _format_quota_error(self, error: Exception | None, models_tried: list[str]) -> str:
        retry_seconds = self._extract_retry_delay_seconds(error) if error else None
        retry_hint = (
            f" Retry after about {retry_seconds}s."
            if retry_seconds is not None
            else " Retry later or switch to another API key/project with quota."
        )
        models_text = ", ".join(models_tried)
        return (
            f"Gemini quota exceeded for models [{models_text}]."
            + retry_hint
        )
