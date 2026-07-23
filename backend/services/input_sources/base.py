from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class InputSource(ABC):
    """Abstract base class for input sources.
    
    Different input sources (file upload, YouTube, etc.) implement this
    to provide audio extraction to a local file.
    """

    @abstractmethod
    def extract_audio(self, input_data: any, task_id: str, output_dir: Path) -> str:
        """Extract audio from input and save to local file.
        
        Args:
            input_data: Source-specific data (file path, URL, etc.)
            task_id: Unique task identifier for this processing
            output_dir: Directory to save the extracted audio file
            
        Returns:
            Path to the extracted audio file as a string
            
        Raises:
            ValueError: If input_data is invalid
            FileNotFoundError: If the audio file cannot be extracted
        """
        raise NotImplementedError()
