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
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"

    # Upload guardrails
    max_upload_size_mb: int = 2048

    # Task persistence backend selection (composition-root concern only;
    # the application layer never branches on this).
    task_store_backend: str = "json"  # "json" | "sqlite"
    tasks_db_path: Path = Path("data/videobrain.db")  # holds tasks + knowledge tables (ADR-0005)

    # Read-flip (ADR-0008): serve the status endpoint from the knowledge
    # layer when possible, with automatic fallback to the task record.
    knowledge_read_enabled: bool = True

    # Formula vision (Этап 6F): after a document is ingested, transcribe
    # formula chunk images into LaTeX enrichments via a vision-capable AI
    # profile. Off by default; failures never affect ingestion.
    formula_vision_enabled: bool = False
    formula_vision_ai_profile: str | None = None  # None = default profile

    class Config:
        env_file = ".env"

    def ensure_dirs(self) -> None:
        """Ensure the expected data directories exist."""
        for p in (self.data_dir, self.audio_dir, self.transcripts_dir, self.summaries_dir, self.tasks_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
