from __future__ import annotations

from collections import Counter
import math
import subprocess
import tempfile
from typing import Any
from pathlib import Path
from threading import Lock
import os
import shutil

try:
    from faster_whisper import WhisperModel
except Exception as e:
    print("IMPORT ERROR:", e)
    raise


class Transcriber:
    """Wraps the speech-to-text model (faster-whisper) behind a simple interface."""

    CHUNK_SECONDS = 600.0
    OVERLAP_SECONDS = 2.0
    CHUNKING_THRESHOLD_SECONDS = 900.0

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

    def transcribe_with_segments(self, audio_path: str) -> tuple[str, list[dict[str, Any]], str | None]:
        """Transcribe and return plain text, timestamped segments, and detected language code."""
        duration_seconds = self._probe_duration_seconds(audio_path)
        if duration_seconds is None or duration_seconds <= self.CHUNKING_THRESHOLD_SECONDS:
            return self._transcribe_single_pass(audio_path)

        return self._transcribe_chunked(audio_path, duration_seconds)

    def _transcribe_single_pass(self, audio_path: str) -> tuple[str, list[dict[str, Any]], str | None]:
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

        transcript = "\n".join(transcript_lines)
        detected_language = getattr(info, "language", None)
        if detected_language:
            detected_language = str(detected_language).strip().lower()
        return transcript, output_segments, detected_language

    def _transcribe_chunked(self, audio_path: str, duration_seconds: float) -> tuple[str, list[dict[str, Any]], str | None]:
        chunk_specs = self._build_chunk_specs(duration_seconds)
        total_chunks = len(chunk_specs)
        print(f"🧩 Chunked transcription enabled: {total_chunks} parts")

        output_segments: list[dict[str, Any]] = []
        language_counter: Counter[str] = Counter()

        source_path = Path(audio_path)
        suffix = source_path.suffix if source_path.suffix else ".wav"

        with tempfile.TemporaryDirectory(prefix="whisper_chunks_") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            for index, spec in enumerate(chunk_specs, start=1):
                chunk_path = tmp_dir_path / f"chunk_{index:05d}{suffix}"
                try:
                    print(
                        "🧩 Processing chunk "
                        f"{index}/{total_chunks} "
                        f"(start={spec['chunk_start']:.1f}s, duration={spec['chunk_duration']:.1f}s)"
                    )
                    self._extract_chunk(audio_path, chunk_path, spec["chunk_start"], spec["chunk_duration"])

                    segments, info = self.model.transcribe(
                        str(chunk_path),
                        beam_size=1,
                        best_of=1,
                        condition_on_previous_text=False,
                        vad_filter=False,
                    )

                    detected_language = getattr(info, "language", None)
                    if detected_language:
                        language_counter[str(detected_language).strip().lower()] += 1

                    primary_start = spec["primary_start"]
                    primary_end = spec["primary_end"]
                    chunk_start = spec["chunk_start"]
                    accepted_count = 0

                    for segment in segments:
                        text = segment.text.strip()
                        if not text:
                            continue

                        global_start = float(segment.start) + chunk_start
                        global_end = float(segment.end) + chunk_start
                        midpoint = (global_start + global_end) / 2.0

                        # Keep only the primary interval for this chunk to remove overlap duplicates.
                        if midpoint < primary_start or midpoint >= primary_end:
                            continue

                        output_segments.append(
                            {
                                "start": round(global_start, 3),
                                "end": round(global_end, 3),
                                "text": text,
                            }
                        )
                        accepted_count += 1

                    print(f"✅ Chunk {index}/{total_chunks} done (accepted segments: {accepted_count})")
                except Exception as exc:
                    raise RuntimeError(
                        f"Chunk transcription failed at chunk {index}/{total_chunks} "
                        f"(start={spec['chunk_start']:.1f}s): {exc}"
                    ) from exc

        output_segments.sort(key=lambda item: item["start"])
        transcript = "\n".join(segment["text"] for segment in output_segments)
        detected_language = language_counter.most_common(1)[0][0] if language_counter else None
        return transcript, output_segments, detected_language

    def _build_chunk_specs(self, duration_seconds: float) -> list[dict[str, float]]:
        specs: list[dict[str, float]] = []
        chunk_count = int(math.ceil(duration_seconds / self.CHUNK_SECONDS))

        for i in range(chunk_count):
            primary_start = i * self.CHUNK_SECONDS
            primary_end = min(duration_seconds, primary_start + self.CHUNK_SECONDS)
            if primary_start >= primary_end:
                continue

            is_first = i == 0
            is_last = i == (chunk_count - 1)

            chunk_start = max(0.0, primary_start - (0.0 if is_first else self.OVERLAP_SECONDS))
            chunk_end = min(duration_seconds, primary_end + (0.0 if is_last else self.OVERLAP_SECONDS))
            chunk_duration = max(0.0, chunk_end - chunk_start)
            if chunk_duration <= 0.0:
                continue

            specs.append(
                {
                    "primary_start": primary_start,
                    "primary_end": primary_end,
                    "chunk_start": chunk_start,
                    "chunk_duration": chunk_duration,
                }
            )

        return specs

    def _extract_chunk(self, source_audio_path: str, output_path: Path, start_seconds: float, duration_seconds: float) -> None:
        ffmpeg_path = self._resolve_binary("ffmpeg")
        cmd = [
            ffmpeg_path,
            "-v", "error",
            "-ss", f"{start_seconds:.3f}",
            "-i", str(source_audio_path),
            "-t", f"{duration_seconds:.3f}",
            "-c", "copy",
            "-y",
            str(output_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise RuntimeError(f"Failed to split audio chunk via ffmpeg: {stderr}") from exc

    def _probe_duration_seconds(self, audio_path: str) -> float | None:
        ffprobe_path = self._resolve_binary("ffprobe")
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            raw = (result.stdout or "").strip()
            if not raw:
                return None
            value = float(raw)
            return value if value > 0 else None
        except Exception:
            return None

    @staticmethod
    def _resolve_binary(name: str) -> str:
        resolved = shutil.which(name)
        if resolved:
            return resolved

        if os.name == "nt":
            winget_links = Path(r"C:\Users\Dell\AppData\Local\Microsoft\WinGet\Links") / f"{name}.exe"
            if winget_links.exists():
                return str(winget_links)

            common = Path(r"C:\ffmpeg\bin") / f"{name}.exe"
            if common.exists():
                return str(common)

        return name

    def transcribe(self, audio_path: str) -> str:
        """Transcribe the given audio file to plain text.

        Returns the full transcript as a string.
        """
        transcript, _segments, _detected_language = self.transcribe_with_segments(audio_path)
        return transcript
