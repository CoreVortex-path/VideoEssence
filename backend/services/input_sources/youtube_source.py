from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse
import yt_dlp
from .base import InputSource

# Файлы субтитров/метаданных — не аудио, Whisper их не обрабатывает.
_NON_AUDIO_EXTS = {".vtt", ".srt", ".json3", ".srv1", ".srv2", ".srv3", ".ttml", ".part"}


def _cookies_path() -> Path:
    return Path(__file__).parent.parent.parent.parent / "cookies.txt"


def extract_youtube_video_id(url: str) -> str | None:
    """Извлечь video id из URL YouTube без yt-dlp (чистый парсинг строки).

    Поддерживаются формы watch?v=ID, youtu.be/ID, /shorts/ID, /embed/ID.
    Нужен до скачивания: дедупликация библиотеки по ключу "youtube:{id}".
    None — URL не распознан как YouTube.
    """
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return None
    host = parsed.netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]

    video_id: str | None = None
    if host in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        else:
            for prefix in ("/shorts/", "/embed/", "/v/"):
                if parsed.path.startswith(prefix):
                    video_id = parsed.path[len(prefix):].split("/")[0]
                    break
    elif host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]

    return video_id or None


def fetch_youtube_title(youtube_url: str) -> str | None:
    """Best-effort video title via yt-dlp metadata (no download).

    Returns None on any failure — title is cosmetic and must never
    break the processing pipeline.
    """
    cookies = _cookies_path()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "cookiefile": str(cookies) if cookies.exists() else None,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
        title = (info or {}).get("title")
        return title.strip() if isinstance(title, str) and title.strip() else None
    except Exception as exc:
        print(f"⚠️ YouTube title fetch failed: {exc}")
        return None


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
        cookies_path = _cookies_path()

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
