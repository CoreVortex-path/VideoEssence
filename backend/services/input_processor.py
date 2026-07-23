from __future__ import annotations

from pathlib import Path
from enum import Enum

from .input_sources.base import InputSource
from .input_sources.file_source import FileInputSource
from .input_sources.youtube_source import YouTubeInputSource


class InputSourceType(str, Enum):
    """Supported input source types."""
    FILE = "file"
    YOUTUBE = "youtube"


def get_input_source(source_type: InputSourceType) -> InputSource:
    """Factory function to get the appropriate input source.
    
    Args:
        source_type: The type of input source
        
    Returns:
        An instance of the appropriate InputSource subclass
        
    Raises:
        ValueError: If source_type is not supported
    """
    sources = {
        InputSourceType.FILE: FileInputSource,
        InputSourceType.YOUTUBE: YouTubeInputSource,
    }
    
    if source_type not in sources:
        raise ValueError(f"Unsupported input source: {source_type}")
    
    return sources[source_type]()


def detect_input_source(input_data: str | Path) -> InputSourceType:
    """Auto-detect the input source type based on input data.
    
    Args:
        input_data: Can be a file path or a URL string
        
    Returns:
        The detected InputSourceType
    """
    input_str = str(input_data).strip()
    
    # Check if it's a URL
    if input_str.startswith(("http://", "https://", "youtu.be/", "www.youtube.com")):
        return InputSourceType.YOUTUBE
    
    # Otherwise treat as file path
    return InputSourceType.FILE
