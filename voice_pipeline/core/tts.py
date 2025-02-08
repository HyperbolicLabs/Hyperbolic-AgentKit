from dataclasses import dataclass
from typing import AsyncGenerator, Protocol
from ..types import AudioChunk, EventTypes
from .event_emitter import EventEmitter

@dataclass
class TTSCapabilities:
    """TTS capabilities configuration."""
    streaming: bool = False
    voice_selection: bool = False
    ssml: bool = False
    word_timing: bool = False

class TTSConfig(Protocol):
    """Protocol defining TTS configuration."""
    @property
    def sample_rate(self) -> int:
        """Get the sample rate in Hz."""
        ...
        
    @property
    def num_channels(self) -> int:
        """Get the number of audio channels."""
        ...

class TTS(EventEmitter[EventTypes]):
    """Base class for Text-to-Speech synthesis."""
    
    def __init__(self, config: TTSConfig):
        super().__init__()
        self._config = config
        self._is_synthesizing = False
        
    @property
    def capabilities(self) -> TTSCapabilities:
        """Get the TTS capabilities."""
        raise NotImplementedError
        
    @property
    def config(self) -> TTSConfig:
        """Get the TTS configuration."""
        return self._config
        
    @property
    def is_synthesizing(self) -> bool:
        """Whether the TTS is currently synthesizing audio."""
        return self._is_synthesizing
        
    async def synthesize(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text to speech.
        
        Args:
            text: The text to synthesize
            
        Yields:
            Audio chunks of synthesized speech
        """
        raise NotImplementedError
        
    async def reset(self) -> None:
        """Reset the TTS state."""
        self._is_synthesizing = False
        
    async def aclose(self) -> None:
        """Clean up resources."""
        pass 