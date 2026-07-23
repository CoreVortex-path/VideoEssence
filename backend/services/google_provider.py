import json
from pathlib import Path
from typing import Any
from google import genai
from google.genai import types

from .ai_provider import BaseAIProvider


class GoogleAIProvider(BaseAIProvider):

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is empty")
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

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

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        return response.text

    def transcribe_and_summarize_file(self, file_path: str) -> dict[str, Any]:
        """Use Gemini Files API to produce transcript and summary in one model pass."""
        media_path = Path(file_path)
        uploaded_file = self.client.files.upload(file=str(media_path))

        prompt = """
You are a precise media analyst.

Task:
1. Create a full transcript from the provided audio/video.
2. Create a concise summary in the Russian language as the media.

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

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        text = (response.text or "").strip()
        if not text:
            raise ValueError("Gemini returned empty response")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            cleaned = text
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                cleaned = cleaned.replace("json", "", 1).strip()
            payload = json.loads(cleaned)

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

    def summarize_with_chapters(self, transcript_segments: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize timestamped transcript and build chapters with existing timestamps only."""
        if not transcript_segments:
            raise ValueError("Transcript segments are empty")

        timestamped_transcript = "\n".join(
            f"[{self._sec_to_ts(float(seg['start']))}] {str(seg.get('text', '')).strip()}"
            for seg in transcript_segments
            if str(seg.get("text", "")).strip()
        )

        available_starts = [round(float(seg["start"]), 3) for seg in transcript_segments]

        prompt = f"""
You are given a transcript that already contains trusted timestamps from speech recognition.

Task:
1. Write a concise summary in the same language as the transcript.
2. Build a chapter list for interactive navigation.

Critical rule:
- Do not invent timestamps.
- Every chapter.start must be one of the existing segment start values.

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

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        text = (response.text or "").strip()
        if not text:
            raise ValueError("Gemini returned empty response")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            cleaned = text
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                cleaned = cleaned.replace("json", "", 1).strip()
            payload = json.loads(cleaned)

        summary = (payload.get("summary") or "").strip()
        language = (payload.get("language") or "").strip() or None
        chapters_raw = payload.get("chapters") or []

        if not summary:
            raise ValueError("Gemini did not return summary")

        start_set = set(available_starts)
        chapters: list[dict[str, Any]] = []
        for item in chapters_raw:
            start = round(float(item.get("start", 0.0)), 3)
            if start not in start_set:
                continue
            title = str(item.get("title", "")).strip()
            chapter_summary = str(item.get("summary", "")).strip()
            if not title or not chapter_summary:
                continue
            chapters.append(
                {
                    "title": title,
                    "summary": chapter_summary,
                    "start": start,
                }
            )

        chapters.sort(key=lambda x: x["start"])
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

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        translated_text = (response.text or "").strip()
        if not translated_text:
            raise ValueError("Gemini returned empty translation")
        return translated_text

    @staticmethod
    def _sec_to_ts(seconds: float) -> str:
        total = max(0, int(seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
