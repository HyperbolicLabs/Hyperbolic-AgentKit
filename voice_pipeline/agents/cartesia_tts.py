import numpy as np
from cartesia import Cartesia
from dataclasses import dataclass
from typing import AsyncGenerator
import asyncio

from ..core.tts import TTS, TTSCapabilities, TTSConfig
from ..types import AudioChunk

@dataclass
class CartesiaTTSConfig(TTSConfig):
    """Cartesia TTS configuration."""
    sample_rate: int = 44100
    num_channels: int = 1
    voice_id: str = ""
    model_id: str = "sonic-2024-12-12"

class CartesiaTTSCapabilities(TTSCapabilities):
    """Cartesia TTS capabilities."""
    def __init__(self):
        super().__init__(
            streaming=True,
            voice_selection=True,
            ssml=False,
            word_timing=False
        )

class CartesiaTTS(TTS):
    """Text-to-Speech using Cartesia's API."""
    
    CHUNK_SIZE = 1024  # Process audio in 1KB chunks
    
    def __init__(self, api_key: str, config: CartesiaTTSConfig):
        super().__init__(config)
        self._capabilities = CartesiaTTSCapabilities()
        
        # Initialize Cartesia client
        self._client = Cartesia(api_key=api_key)
        
    @property
    def capabilities(self) -> TTSCapabilities:
        return self._capabilities
        
    async def synthesize(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text to speech.
        
        Args:
            text: The text to synthesize
            
        Yields:
            Audio chunks of synthesized speech
        """
        if not text.strip():
            return
            
        try:
            self._is_synthesizing = True
            
            # Generate audio using Cartesia
            audio_data = self._client.tts.bytes(
                model_id=self._config.model_id,
                transcript=text,
                voice_id=self._config.voice_id,
                output_format={
                    "container": "wav",
                    "encoding": "pcm_f32le",
                    "sample_rate": self._config.sample_rate,
                }
            )
            
            # Find data chunk in WAV header
            offset = 12  # Skip RIFF header and chunk size
            while offset < len(audio_data):
                chunk_id = audio_data[offset:offset + 4]
                chunk_size = int.from_bytes(audio_data[offset + 4:offset + 8], 'little')
                
                if chunk_id == b'data':
                    data_offset = offset + 8  # Skip chunk ID and size
                    break
                    
                offset += 8 + chunk_size
            else:
                raise ValueError("Could not find data chunk in WAV file")
                
            # Convert audio data to numpy array, skipping WAV header
            audio_array = np.frombuffer(audio_data[data_offset:], dtype=np.float32)
            
            # Process audio in chunks
            total_samples = len(audio_array)
            for i in range(0, total_samples, self.CHUNK_SIZE):
                chunk = audio_array[i:min(i + self.CHUNK_SIZE, total_samples)]
                
                # Ensure chunk size is a multiple of 4 (float32)
                if len(chunk) % 4 != 0:
                    pad_size = 4 - (len(chunk) % 4)
                    chunk = np.pad(chunk, (0, pad_size), 'constant')
                
                yield chunk.tolist()
                await asyncio.sleep(0)  # Allow other tasks to run
                
        finally:
            self._is_synthesizing = False
            
    async def reset(self) -> None:
        """Reset the TTS state."""
        await super().reset()
        
    async def aclose(self) -> None:
        """Clean up resources."""
        pass 