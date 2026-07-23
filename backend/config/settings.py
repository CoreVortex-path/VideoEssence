from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment or .env.

    Keeps paths and feature flags centralized.
    """

    # Data directories
    base_dir: Path = Path(os.getcwd())
    data_dir: Path = Path("data")
    audio_dir: Path = Path("data/audio")
    transcripts_dir: Path = Path("data/transcripts")
    summaries_dir: Path = Path("data/summaries")
    tasks_dir: Path = Path("data/tasks")

    # AI provider settings
    google_api_key: str | None = None

    class Config:
        env_file = ".env"

    def ensure_dirs(self) -> None:
        """Ensure the expected data directories exist."""
        for p in (self.data_dir, self.audio_dir, self.transcripts_dir, self.summaries_dir, self.tasks_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
