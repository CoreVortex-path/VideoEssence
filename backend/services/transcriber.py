from __future__ import annotations

from typing import Any
from pathlib import Path
from threading import Lock
import os

try:
    from faster_whisper import WhisperModel
except Exception as e:
    print("IMPORT ERROR:", e)
    raise


class Transcriber:
    """Wraps the speech-to-text model (faster-whisper) behind a simple interface."""

    _model_cache: dict[tuple[str, str, str], WhisperModel] = {}
    _cache_lock = Lock()

    def __init__(self, model_size: str = "small") -> None:
        if WhisperModel is None:
            raise RuntimeError("faster-whisper is not installed")
        device = "cpu"
        compute_type = "int8"
        cache_key = (model_size, device, compute_type)

        with self._cache_lock:
            cached_model = self._model_cache.get(cache_key)
            if cached_model is None:
                cpu_threads = max(1, (os.cpu_count() or 4) - 1)
                cached_model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=cpu_threads,
                )
                self._model_cache[cache_key] = cached_model

        self.model = cached_model

    def transcribe_with_segments(self, audio_path: str) -> tuple[str, list[dict[str, Any]]]:
        """Transcribe and return both plain text and timestamped segments."""
        transcript_lines: list[str] = []
        output_segments: list[dict[str, Any]] = []
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
            vad_filter=False,
        )

        for segment in segments:
            text = segment.text.strip()
            transcript_lines.append(text)
            output_segments.append(
                {
                    "start": round(float(segment.start), 3),
                    "end": round(float(segment.end), 3),
                    "text": text,
                }
            )

        return "\n".join(transcript_lines), output_segments

    def transcribe(self, audio_path: str) -> str:
        """Transcribe the given audio file to plain text.

        Returns the full transcript as a string.
        """
        transcript, _segments = self.transcribe_with_segments(audio_path)
        return transcript
