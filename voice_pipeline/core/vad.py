from dataclasses import dataclass
from typing import Protocol
import asyncio
from ..types import AudioChunk, EventTypes
from .event_emitter import EventEmitter

@dataclass
class VADEvent:
    """Voice Activity Detection event data."""
    speech_probability: float
    speech_duration: float
    silence_duration: float
    raw_accumulated_speech: float
    raw_accumulated_silence: float

class VADCapabilities(Protocol):
    """Protocol defining VAD capabilities."""
    @property
    def streaming(self) -> bool:
        """Whether the VAD supports streaming audio."""
        ...

class VAD(EventEmitter[EventTypes]):
    """Base class for Voice Activity Detection."""
    
    def __init__(self):
        super().__init__()
        self._is_speaking = False
        self._speech_start_time = 0.0
        self._last_vad_time = 0.0
        
    @property
    def capabilities(self) -> VADCapabilities:
        """Get the VAD capabilities."""
        raise NotImplementedError
        
    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently detected."""
        return self._is_speaking
        
    async def process_chunk(self, chunk: AudioChunk) -> None:
        """Process an audio chunk for voice activity.
        
        Args:
            chunk: The audio chunk to process
        """
        raise NotImplementedError
        
    async def reset(self) -> None:
        """Reset the VAD state."""
        self._is_speaking = False
        self._speech_start_time = 0.0
        self._last_vad_time = 0.0
        
    async def aclose(self) -> None:
        """Clean up resources."""
        pass 