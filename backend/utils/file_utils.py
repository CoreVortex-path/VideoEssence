from __future__ import annotations

from pathlib import Path
from ..config.settings import settings


def make_task_paths(task_id: str) -> tuple[Path, Path]:
    """Return (transcript_path, summary_path) for a given task id."""
    tpath = settings.transcripts_dir / f"{task_id}.txt"
    spath = settings.summaries_dir / f"{task_id}.txt"
    return tpath, spath


def save_transcript(path: Path | str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def save_summary(path: Path | str, text: str) -> None:
    save_transcript(path, text)


def load_text(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")
