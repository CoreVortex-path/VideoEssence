from __future__ import annotations

from pathlib import Path
import shutil
from .base import InputSource


class FileInputSource(InputSource):
    """Handle local audio/video file uploads.
    
    Copies the uploaded file to the audio directory or converts it
    to WAV format if needed.
    """

    SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"}
    SUPPORTED_VIDEO_FORMATS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".m4v"}

    def extract_audio(self, input_data: str | Path, task_id: str, output_dir: Path) -> str:
        """Extract audio from a local file.
        
        Args:
            input_data: Path to the local audio/video file
            task_id: Unique task identifier
            output_dir: Directory to save the audio file
            
        Returns:
            Path to the audio file
        """
        input_file = Path(input_data)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        file_ext = input_file.suffix.lower()
        
        # If it's already an audio file, copy it
        if file_ext in self.SUPPORTED_AUDIO_FORMATS:
            output_file = output_dir / f"{task_id}{file_ext}"
            shutil.copy2(input_file, output_file)
            print(f"✅ Audio file copied: {input_file} -> {output_file}")
            return str(output_file)
        
        # If it's a video file, we'll need ffmpeg to extract audio
        elif file_ext in self.SUPPORTED_VIDEO_FORMATS:
            output_file = output_dir / f"{task_id}.wav"
            self._extract_audio_from_video(input_file, output_file)
            print(f"✅ Audio extracted from video: {input_file} -> {output_file}")
            return str(output_file)
        
        else:
            raise ValueError(
                f"Unsupported file format: {file_ext}. "
                f"Supported: {self.SUPPORTED_AUDIO_FORMATS | self.SUPPORTED_VIDEO_FORMATS}"
            )

    def _extract_audio_from_video(self, video_file: Path, output_file: Path) -> None:
        """Extract audio from video using ffmpeg if available."""
        try:
            import subprocess
            import shutil
            
            # Try multiple locations to find ffmpeg
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
                common_path = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
                if common_path.exists():
                    ffmpeg_path = str(common_path)
            
            # 4. Fallback - just try "ffmpeg" and let system find it
            if not ffmpeg_path:
                ffmpeg_path = "ffmpeg"
            
            print(f"Using ffmpeg from: {ffmpeg_path}")
            
            cmd = [
                str(ffmpeg_path),
                "-i", str(video_file),
                "-q:a", "0",
                "-map", "a",
                str(output_file),
                "-y"  # Overwrite output file
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"✅ Audio extracted successfully: {output_file}")
            
        except FileNotFoundError as e:
            raise RuntimeError(
                "❌ ffmpeg not found\n"
                "To process video files, install ffmpeg:\n"
                "  Windows: winget install ffmpeg\n"
                "           OR download from https://ffmpeg.org/download.html\n"
                "  Mac: brew install ffmpeg\n"
                "  Linux: sudo apt-get install ffmpeg\n\n"
                "For now, extract audio manually:\n"
                "  ffmpeg -i video.mp4 audio.mp3\n"
                "  Then upload the audio file instead."
            )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            raise RuntimeError(f"Failed to extract audio from video: {error_msg}")
