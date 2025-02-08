import torch
import torchaudio
import numpy as np
import logging
from dataclasses import dataclass
from ..core.vad import VAD, VADCapabilities, VADEvent
from ..types import AudioChunk, EventTypes

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dataclass
class SileroVADCapabilities(VADCapabilities):
    """Silero VAD capabilities."""
    streaming: bool = True

class SileroVAD(VAD):
    """Voice Activity Detection using Silero VAD."""
    
    def __init__(self, threshold: float = 0.5, sampling_rate: int = 16000):
        super().__init__()
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.model = None
        self._accumulated_speech = 0.0
        self._accumulated_silence = 0.0
        self._audio_buffer = []
        logger.info("Initializing SileroVAD with threshold=%f, sampling_rate=%d", threshold, sampling_rate)
        self._load_model()
        
    def _load_model(self):
        """Load the Silero VAD model."""
        try:
            logger.info("Loading Silero VAD model...")
            self.model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=True,
                onnx=False
            )
            self.model.eval()
            logger.info("Silero VAD model loaded successfully")
        except Exception as e:
            logger.error("Failed to load Silero VAD model: %s", str(e))
            raise
        
    @property
    def capabilities(self) -> VADCapabilities:
        """Get the VAD capabilities."""
        return SileroVADCapabilities()
        
    async def process_chunk(self, chunk: AudioChunk) -> None:
        """Process an audio chunk for voice activity.
        
        Args:
            chunk: The audio chunk to process
        """
        try:
            if self.model is None:
                logger.error("Model is None in process_chunk")
                return
                
            logger.debug("Processing audio chunk of length %d", len(chunk.audio_data))
            
            # Convert the audio chunk to the correct format for Silero VAD
            audio_tensor = torch.FloatTensor(chunk.audio_data)
            
            # Ensure audio is mono
            if len(audio_tensor.shape) > 1:
                audio_tensor = audio_tensor.mean(dim=0)
                
            # Resample if necessary
            if chunk.sample_rate != self.sampling_rate:
                logger.debug("Resampling from %d to %d", chunk.sample_rate, self.sampling_rate)
                resampler = torchaudio.transforms.Resample(
                    orig_freq=chunk.sample_rate,
                    new_freq=self.sampling_rate
                )
                audio_tensor = resampler(audio_tensor)
            
            # Add to buffer
            self._audio_buffer.extend(audio_tensor.tolist())
            logger.debug("Buffer size after adding chunk: %d", len(self._audio_buffer))
            
            # Process complete chunks
            chunk_size = 512 if self.sampling_rate == 16000 else 256
            while len(self._audio_buffer) >= chunk_size:
                # Get a chunk of the right size
                current_chunk = self._audio_buffer[:chunk_size]
                self._audio_buffer = self._audio_buffer[chunk_size:]
                
                # Process the chunk
                audio_tensor = torch.FloatTensor(current_chunk).unsqueeze(0)
                speech_prob = self.model(audio_tensor, self.sampling_rate).item()
                logger.debug("Speech probability: %f", speech_prob)
                
                # Update speech/silence accumulation
                chunk_duration = chunk_size / self.sampling_rate
                if speech_prob >= self.threshold:
                    self._accumulated_speech += chunk_duration
                    self._accumulated_silence = 0
                    logger.debug("Accumulated speech: %f", self._accumulated_speech)
                else:
                    self._accumulated_silence += chunk_duration
                    self._accumulated_speech = 0
                    logger.debug("Accumulated silence: %f", self._accumulated_silence)
                    
                # Update speaking state
                was_speaking = self._is_speaking
                self._is_speaking = speech_prob >= self.threshold
                
                # Calculate durations
                speech_duration = self._accumulated_speech if self._is_speaking else 0
                silence_duration = self._accumulated_silence if not self._is_speaking else 0
                
                # Create VAD event
                event = VADEvent(
                    speech_probability=speech_prob,
                    speech_duration=speech_duration,
                    silence_duration=silence_duration,
                    raw_accumulated_speech=self._accumulated_speech,
                    raw_accumulated_silence=self._accumulated_silence
                )
                
                # Emit appropriate events
                try:
                    if self._is_speaking and not was_speaking:
                        logger.info("Speech start detected")
                        await self.emit(EventTypes.SPEECH_START.value, event)
                    elif not self._is_speaking and was_speaking:
                        logger.info("Speech end detected")
                        await self.emit(EventTypes.SPEECH_END.value, event)
                    
                    await self.emit(EventTypes.VAD_DATA.value, event)
                except Exception as e:
                    logger.error("Error emitting VAD event: %s", str(e))
                    raise
                    
        except Exception as e:
            logger.error("Error in process_chunk: %s", str(e))
            raise
        
    async def reset(self) -> None:
        """Reset the VAD state."""
        logger.info("Resetting VAD state")
        await super().reset()
        self._accumulated_speech = 0.0
        self._accumulated_silence = 0.0
        self._audio_buffer = []
        
    async def aclose(self) -> None:
        """Clean up resources."""
        logger.info("Closing VAD")
        self.model = None
        self._audio_buffer = []
        await super().aclose() 