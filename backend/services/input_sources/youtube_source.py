from __future__ import annotations

from pathlib import Path
import yt_dlp
from .base import InputSource

# Файлы субтитров/метаданных — не аудио, Whisper их не обрабатывает.
_NON_AUDIO_EXTS = {".vtt", ".srt", ".json3", ".srv1", ".srv2", ".srv3", ".ttml", ".part"}


class YouTubeInputSource(InputSource):
    """Handle YouTube URL downloads.

    This source can be added to the pipeline without changing the core
    processing flow. It's kept separate to support future modularization.
    """

    def extract_audio(self, input_data: str, task_id: str, output_dir: Path) -> str:
        """Download audio from a YouTube URL.

        Args:
            input_data: YouTube URL
            task_id: Unique task identifier
            output_dir: Directory to save the audio file

        Returns:
            Path to the extracted audio file
        """
        youtube_url = input_data

        # Resolve cookies path
        cookies_path = Path(__file__).parent.parent.parent.parent / "cookies.txt"

        # Без конвертации в WAV: faster-whisper сам декодирует opus/m4a
        # через PyAV, а конвертация тратила десятки секунд и место на диске.
        ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(output_dir / f"{task_id}.%(ext)s"),
            "cookiefile": str(cookies_path) if cookies_path.exists() else None,
            "quiet": False,
            "no_warnings": False,
        }

        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                ydl.download([youtube_url])
        except Exception as e:
            raise RuntimeError(f"Failed to download YouTube audio: {e}")

        # Find file by task_id, пропуская субтитры и недокачанные .part
        for f in sorted(output_dir.iterdir()):
            if f.name.startswith(task_id) and f.suffix.lower() not in _NON_AUDIO_EXTS:
                return str(f)

        raise FileNotFoundError(f"Downloaded audio not found for task {task_id}")
