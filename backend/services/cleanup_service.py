from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable


class CleanupService:
    """Centralized cleanup for task-owned temporary artifacts."""

    def cleanup(self, *paths: str | Path | None) -> None:
        for path in paths:
            self._remove_path(path)

    def cleanup_many(self, paths: Iterable[str | Path | None]) -> None:
        for path in paths:
            self._remove_path(path)

    def cleanup_prefixed_files(self, directory: str | Path, prefix: str) -> None:
        target_dir = Path(directory)
        if not target_dir.exists():
            print(f"🧹 Cleanup skipped (missing directory): {target_dir}")
            return

        pattern = f"{prefix}*"
        print(f"🧹 Cleanup prefix in {target_dir}: {pattern}")
        for child in target_dir.iterdir():
            if fnmatch.fnmatch(child.name, pattern):
                self._remove_path(child)

    def _remove_path(self, path: str | Path | None) -> None:
        if not path:
            return

        target = Path(path)
        try:
            if not target.exists():
                print(f"🧹 Cleanup skipped (missing): {target}")
                return

            if target.is_dir():
                print(f"🧹 Removing directory: {target}")
                for child in target.iterdir():
                    self._remove_path(child)
                try:
                    target.rmdir()
                except OSError:
                    # Directory may remain if it is not empty or is managed elsewhere.
                    print(f"🧹 Directory not removed (not empty or in use): {target}")
                return

            print(f"🧹 Removing file: {target}")
            target.unlink()
        except Exception as exc:
            print(f"🧹 Cleanup error for {target}: {exc}")


cleanup_service = CleanupService()