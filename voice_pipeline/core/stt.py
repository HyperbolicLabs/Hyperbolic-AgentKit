from dataclasses import dataclass
from typing import List, Protocol
from ..types import AudioChunk, EventTypes, TranscriptText
from .event_emitter import EventEmitter

@dataclass
class TranscriptionAlternative:
    """A single transcription alternative."""
    text: TranscriptText
    confidence: float
    language: str | None = None

@dataclass
class SpeechEvent:
    """Speech transcription event data."""
    alternatives: List[TranscriptionAlternative]
    is_final: bool

class STTCapabilities(Protocol):
    """Protocol defining STT capabilities."""
    @property
    def streaming(self) -> bool:
        """Whether the STT supports streaming audio."""
        ...
        
    @property
    def interim_results(self) -> bool:
        """Whether the STT provides interim results."""
        ...
        
    @property
    def language_detection(self) -> bool:
        """Whether the STT supports language detection."""
        ...

class STT(EventEmitter[EventTypes]):
    """Base class for Speech-to-Text conversion."""
    
    def __init__(self):
        super().__init__()
        self._current_text = ""
        self._is_processing = False
        
    @property
    def capabilities(self) -> STTCapabilities:
        """Get the STT capabilities."""
        raise NotImplementedError
        
    @property
    def current_text(self) -> TranscriptText:
        """Get the current transcription text."""
        return self._current_text
        
    @property
    def is_processing(self) -> bool:
        """Whether the STT is currently processing audio."""
        return self._is_processing
        
    async def process_chunk(self, chunk: AudioChunk) -> None:
        """Process an audio chunk for transcription.
        
        Args:
            chunk: The audio chunk to process
        """
        raise NotImplementedError
        
    async def reset(self) -> None:
        """Reset the STT state."""
        self._current_text = ""
        self._is_processing = False
        
    async def aclose(self) -> None:
        """Clean up resources."""
        pass 