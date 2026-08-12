from __future__ import annotations

import hashlib
from pathlib import Path
from fastapi import UploadFile
import uuid

from ..config.settings import settings
from .extractors import SUPPORTED_DOCUMENT_FORMATS
from .input_sources.file_source import FileInputSource

CHUNK_SIZE = 1024 * 1024  # 1 MiB streaming chunks

ALLOWED_EXTENSIONS = (
    FileInputSource.SUPPORTED_AUDIO_FORMATS
    | FileInputSource.SUPPORTED_VIDEO_FORMATS
    | SUPPORTED_DOCUMENT_FORMATS
)


class UploadValidationError(ValueError):
    """Upload rejected: unsupported type or size limit exceeded.

    Carries the HTTP status the route should return (422 or 413).
    """

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


async def save_uploaded_file(upload_file: UploadFile, dest_dir: Path) -> tuple[str, str]:
    """Save an uploaded file to the destination directory.

    Validates the extension before writing, streams to disk in chunks
    (constant memory), enforces settings.max_upload_size_mb, and computes
    the sha256 of the content as it streams (used as the content identity
    for the knowledge layer, ADR-0006).

    Args:
        upload_file: The FastAPI UploadFile object
        dest_dir: Directory to save the file

    Returns:
        (path_to_saved_file, sha256_hexdigest)

    Raises:
        UploadValidationError: unsupported extension or size limit exceeded
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Validate type before anything touches disk.
    safe_name = Path(upload_file.filename or "upload.bin").name
    file_ext = Path(safe_name).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file format: {file_ext or '(none)'}. "
            f"Supported: {sorted(ALLOWED_EXTENSIONS)}",
            status_code=422,
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    # Save with a unique prefix to avoid collisions across parallel tasks.
    file_path = dest_dir / f"{uuid.uuid4()}_{safe_name}"

    written = 0
    hasher = hashlib.sha256()
    try:
        with open(file_path, "wb") as f:
            while chunk := await upload_file.read(CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise UploadValidationError(
                        f"File exceeds the maximum upload size of "
                        f"{settings.max_upload_size_mb} MB",
                        status_code=413,
                    )
                hasher.update(chunk)
                f.write(chunk)
    except Exception:
        # Never leave partial uploads on disk.
        file_path.unlink(missing_ok=True)
        raise

    print(f"✅ File uploaded: {file_path}")
    return str(file_path), hasher.hexdigest()
