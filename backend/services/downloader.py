from __future__ import annotations

from pathlib import Path
import yt_dlp

from ..config.settings import settings


def download_audio(youtube_url: str, task_id: str) -> str:
    """Download audio from YouTube and return local file path."""

    out_dir = settings.audio_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    output_path = out_dir / f"{task_id}.wav"

    ytdl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / f"{task_id}.%(ext)s"),

        # 🍪 cookies (fix YouTube bot protection)
        "cookiefile": "cookies.txt",

        # 🎬 ffmpeg (Windows fix)
        "ffmpeg_location": r"C:\\ffmpeg\\bin",

        # 🧪 debug mode (важно для MVP)
        "quiet": False,
        "no_warnings": False,

        # 🔧 audio extraction
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        ydl.download([youtube_url])

    # 🔍 проверка результата
    if output_path.exists():
        return str(output_path)

    # fallback: ищем файл по task_id
    for f in out_dir.iterdir():
        if f.name.startswith(task_id):
            return str(f)

    raise FileNotFoundError("Downloaded audio not found")