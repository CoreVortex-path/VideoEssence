from __future__ import annotations

from pathlib import Path
from fastapi import UploadFile
import uuid


async def save_uploaded_file(upload_file: UploadFile, dest_dir: Path) -> str:
    """Save an uploaded file to the destination directory.
    
    Args:
        upload_file: The FastAPI UploadFile object
        dest_dir: Directory to save the file
        
    Returns:
        Path to the saved file as a string
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with a unique prefix to avoid collisions across parallel tasks.
    safe_name = Path(upload_file.filename or "upload.bin").name
    file_path = dest_dir / f"{uuid.uuid4()}_{safe_name}"
    
    # Read and save the file
    content = await upload_file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    print(f"✅ File uploaded: {file_path}")
    return str(file_path)
