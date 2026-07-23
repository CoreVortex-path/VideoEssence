from __future__ import annotations

from pathlib import Path
import yt_dlp
from .base import InputSource


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
        output_path = output_dir / f"{task_id}.wav"

        # Resolve cookies path
        cookies_path = Path(__file__).parent.parent.parent.parent / "cookies.txt"
        
        ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(output_dir / f"{task_id}.%(ext)s"),
            "cookiefile": str(cookies_path) if cookies_path.exists() else None,
            "quiet": False,
            "no_warnings": False,
        }

        # Add ffmpeg post-processor if available
        import shutil
        
        ffmpeg_path = None
        
        # 1. Check system PATH
        ffmpeg_path = shutil.which("ffmpeg")
        
        # 2. Check WinGet installation (Windows)
        if not ffmpeg_path:
            winget_path = Path(r"C:\Users\Dell\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe")
            if winget_path.exists():
                ffmpeg_path = str(winget_path)
        
        # 3. Check common Windows installation
        if not ffmpeg_path:
            common_path = Path(r"C:\ffmpeg\bin")
            if common_path.exists():
                ffmpeg_path = str(common_path)
        
        postprocessors = []
        
        if ffmpeg_path:
            if isinstance(ffmpeg_path, str) and ffmpeg_path.endswith(".exe"):
                # Extract directory from full path
                ffmpeg_dir = str(Path(ffmpeg_path).parent)
            else:
                ffmpeg_dir = ffmpeg_path
            
            ytdl_opts["ffmpeg_location"] = ffmpeg_dir
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            })
            print(f"✅ Using ffmpeg from: {ffmpeg_dir}")
        else:
            print("⚠️  ffmpeg not found - will use default audio format")
        
        if postprocessors:
            ytdl_opts["postprocessors"] = postprocessors

        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                ydl.download([youtube_url])
        except Exception as e:
            raise RuntimeError(f"Failed to download YouTube audio: {e}")

        # Check for result
        if output_path.exists():
            return str(output_path)

        # Fallback: find file by task_id
        for f in output_dir.iterdir():
            if f.name.startswith(task_id):
                return str(f)

        raise FileNotFoundError(f"Downloaded audio not found for task {task_id}")
