import asyncio
import time
import sounddevice as sd
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

from ..core.vad import VAD, VADEvent
from ..core.stt import STT, SpeechEvent
from ..core.tts import TTS
from ..core.llm import LLM, ChatContext, Message
from ..types import EventTypes, AgentState, AudioChunk
from ..core.event_emitter import EventEmitter

@dataclass
class PipelineConfig:
    """Configuration for the voice pipeline."""
    allow_interruptions: bool = True
    interrupt_speech_duration: float = 0.5
    interrupt_min_words: int = 0
    min_endpointing_delay: float = 0.5
    max_endpointing_delay: float = 6.0
    max_nested_fnc_calls: int = 1
    preemptive_synthesis: bool = False
    sample_rate: int = 24000  # Changed back to match Cartesia's default
    channels: int = 1
    dtype: str = 'int16'  # PCM 16-bit format for Cartesia
    blocksize: int = 1024

class VoicePipelineAgent(EventEmitter[EventTypes]):
    """A pipeline agent that coordinates VAD, STT, LLM, and TTS components."""
    
    MIN_TIME_PLAYED_FOR_COMMIT = 1.5
    
    def __init__(
        self,
        vad: VAD,
        stt: STT,
        llm: LLM,
        tts: TTS,
        config: PipelineConfig = PipelineConfig()
    ):
        super().__init__()
        self._vad = vad
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._config = config
        
        self._state: AgentState = "initializing"
        self._chat_context = ChatContext(messages=[])
        
        # Speech tracking
        self._current_speech_text = ""
        self._last_speech_time: Optional[float] = None
        self._last_transcript_time: Optional[float] = None
        
        # Interruption handling
        self._is_speaking = False
        self._can_be_interrupted = True
        self._was_interrupted = False
        
        # Audio processing
        self._audio_queue = Queue()
        self._audio_stream = None
        self._stream_active = False
        self._audio_task = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        
        # Setup event handlers
        self._setup_vad_handlers()
        self._setup_stt_handlers()
        
    def _setup_vad_handlers(self):
        """Setup VAD event handlers."""
        @self._vad.on(EventTypes.SPEECH_START.value)
        async def on_speech_start(event: VADEvent):
            await self._handle_speech_start(event)
            
        @self._vad.on(EventTypes.SPEECH_END.value)
        async def on_speech_end(event: VADEvent):
            await self._handle_speech_end(event)
            
        @self._vad.on(EventTypes.VAD_DATA.value)
        async def on_vad_data(event: VADEvent):
            await self.emit(EventTypes.VAD_DATA.value, event)
            
    def _setup_stt_handlers(self):
        """Setup STT event handlers."""
        @self._stt.on("interim_transcript")
        def on_interim(event: SpeechEvent):
            self._handle_interim_transcript(event)
            
        @self._stt.on("final_transcript")
        def on_final(event: SpeechEvent):
            self._handle_final_transcript(event)
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: Dict, status: int) -> None:
        """Handle incoming audio data."""
        if status:
            print(f"Audio callback status: {status}")
            return
            
        # Convert to mono if needed
        if indata.shape[1] > 1:
            audio_data = indata.mean(axis=1)
        else:
            audio_data = indata.flatten()
            
        # Convert to list for AudioChunk type
        audio_data = audio_data.tolist()
        
        # Add to queue for processing
        self._audio_queue.put((audio_data, self._config.sample_rate))
        
    async def _process_audio_queue(self):
        """Process audio chunks from the queue."""
        while self._stream_active:
            try:
                # Get audio chunk from queue
                while not self._audio_queue.empty():
                    audio_data, sample_rate = self._audio_queue.get_nowait()
                    # Create AudioChunk
                    chunk = AudioChunk(
                        audio_data=audio_data,
                        sample_rate=sample_rate
                    )
                    # Process through VAD and STT
                    await self._vad.process_chunk(chunk)
                    if self._state == "listening":
                        await self._stt.process_chunk(chunk)
                    self._audio_queue.task_done()
                
                # Small sleep to prevent busy waiting
                await asyncio.sleep(0.001)
                
            except Exception as e:
                print(f"Error processing audio: {e}")
                continue
    
    async def start(self):
        """Start the voice pipeline agent."""
        try:
            # Initialize audio stream
            self._stream_active = True
            self._audio_stream = sd.InputStream(
                channels=self._config.channels,
                samplerate=self._config.sample_rate,
                dtype=self._config.dtype,
                blocksize=self._config.blocksize,
                callback=self._audio_callback
            )
            
            # Start audio processing task
            self._audio_task = asyncio.create_task(self._process_audio_queue())
            
            # Start audio stream
            self._audio_stream.start()
            
            self._state = "listening"
            await self.emit(EventTypes.AGENT_STARTED_SPEAKING.value)
            
        except Exception as e:
            print(f"Error starting audio stream: {e}")
            self._stream_active = False
            if self._audio_task:
                self._audio_task.cancel()
            raise
        
    async def stop(self):
        """Stop the voice pipeline agent."""
        self._stream_active = False
        
        if self._audio_task:
            self._audio_task.cancel()
            try:
                await self._audio_task
            except asyncio.CancelledError:
                pass
            
        if self._audio_stream:
            self._audio_stream.stop()
            self._audio_stream.close()
            self._audio_stream = None
            
        # Clean up executor
        self._executor.shutdown(wait=False)
            
        await self._vad.aclose()
        await self._stt.aclose()
        await self._llm.aclose()
        await self._tts.aclose()
        
    async def _handle_speech_start(self, event: VADEvent):
        """Handle start of speech event."""
        # Only consider it speech if probability is high enough
        if not hasattr(event, 'speech_probability') or event.speech_probability < 0.8:
            return
        
        await self.emit(EventTypes.SPEECH_START.value, event)
        if self._is_speaking and self._config.allow_interruptions:
            # Add a small delay to avoid false triggers
            await asyncio.sleep(0.2)
            await self._handle_interruption()
            
    async def _handle_speech_end(self, event: VADEvent):
        """Handle end of speech event."""
        await self.emit(EventTypes.SPEECH_END.value, event)
        if self._config.preemptive_synthesis:
            asyncio.create_task(self._generate_response())
            
    def _handle_interim_transcript(self, event: SpeechEvent):
        """Handle interim transcript event."""
        if not event.alternatives:
            return
        text = event.alternatives[0].text
        
        # Only allow interruption if we have meaningful speech
        if self._is_speaking and self._config.allow_interruptions:
            words = text.split()
            if len(words) >= max(2, self._config.interrupt_min_words):
                # Create a task to handle the interruption asynchronously
                asyncio.create_task(self._handle_interruption())
                
    def _handle_final_transcript(self, event: SpeechEvent):
        """Handle final transcript event."""
        if not event.alternatives:
            return
        text = event.alternatives[0].text
        self._current_speech_text += (" " if self._current_speech_text else "") + text
        self._last_transcript_time = time.time()
        
        if not self._is_speaking or self._config.preemptive_synthesis:
            # Get the current event loop or create one if needed
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.create_task(self._generate_response())
            
    async def _handle_interruption(self):
        """Handle user interruption of agent speech."""
        if not self._can_be_interrupted:
            return
        self._was_interrupted = True
        
        # Create an interruption message
        interrupt_message = Message(
            role="system",
            content="Speech interrupted by user"
        )
        
        # Emit interruption event with the message
        await self.emit(EventTypes.AGENT_SPEECH_INTERRUPTED.value, interrupt_message)
        
        # Stop any ongoing audio playback
        sd.stop()
        
        # Reset state
        self._is_speaking = False
        self._can_be_interrupted = True
        self._current_speech_text = ""
        self._state = "listening"
        await self.emit("agent_stopped_speaking")
        
    async def _play_audio(self, audio_data: np.ndarray, sample_rate: int):
        """Play audio data non-blocking with proper cleanup."""
        try:
            print(f"Playing audio chunk - Shape: {audio_data.shape}, Sample rate: {sample_rate}, Dtype: {audio_data.dtype}")
            
            # Ensure audio data is in the correct format
            if audio_data.dtype != np.int16:
                if audio_data.dtype == np.float32:
                    # Scale to full int16 range and convert
                    max_val = np.abs(audio_data).max()
                    if max_val > 0:
                        audio_data = (audio_data / max_val * 32767).astype(np.int16)
                    else:
                        audio_data = audio_data.astype(np.int16)
                else:
                    audio_data = audio_data.astype(np.int16)
            
            # Ensure we have valid audio data
            if len(audio_data) == 0:
                print("Warning: Empty audio data received")
                return
            
            # Check if audio is completely silent
            rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
            print(f"Audio RMS level: {rms}")
            
            if rms < 100:  # Increased threshold for better detection
                print(f"Warning: Audio data too quiet (RMS: {rms})")
                # Try to amplify if too quiet
                gain = 50.0  # Increased gain for better audibility
                audio_data = np.clip(audio_data * gain, -32768, 32767).astype(np.int16)
                new_rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
                print(f"Amplified audio RMS: {new_rms}")
            
            # Configure sounddevice
            sd.default.samplerate = sample_rate
            sd.default.dtype = np.int16
            sd.default.channels = 1
            
            # Play audio non-blocking
            print(f"Starting playback of {len(audio_data)} samples")
            sd.play(audio_data, sample_rate, blocking=False)
            
            # Wait for audio to finish without blocking the event loop
            duration = len(audio_data) / sample_rate
            print(f"Waiting {duration:.2f} seconds for audio to complete")
            await asyncio.sleep(duration + 0.2)  # Added more buffer time
            
            # Ensure playback is complete
            sd.wait()
            
        except Exception as e:
            print(f"Error playing audio: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            sd.stop()

    async def _generate_response(self):
        """Generate and speak agent response."""
        if not self._current_speech_text.strip():
            return
            
        self._state = "thinking"
        await self.emit("agent_thinking")
        
        print(f"\nUser said: {self._current_speech_text}")
        
        # Add user message to context
        self._chat_context.messages.append(
            Message(role="user", content=self._current_speech_text)
        )
        
        try:
            # Generate response
            self._is_speaking = True
            self._can_be_interrupted = self._config.allow_interruptions
            self._was_interrupted = False
            
            self._state = "speaking"
            await self.emit("agent_started_speaking")
            
            # Buffer to accumulate text until we have a meaningful chunk
            text_buffer = ""
            response_text = ""
            audio_buffer = []
            
            print("\nLLM response chunks:")
            async for response_chunk in self._llm.chat(self._chat_context):
                if self._was_interrupted:
                    break
                    
                # Add chunk to buffer and full response
                text_buffer += response_chunk
                response_text += response_chunk
                print(f"Chunk: {response_chunk}", end="", flush=True)
                
                # Check if we have enough meaningful text to synthesize
                # Look for natural break points like punctuation or sufficient words
                words = text_buffer.split()
                if (any(c in text_buffer for c in ".!?,;") or len(words) >= 5) and any(c.isalnum() for c in text_buffer):
                    print(f"\nSynthesizing text chunk: {text_buffer}")
                    # Synthesize speech
                    try:
                        async for audio_chunk in self._tts.synthesize(text_buffer):
                            if self._was_interrupted:
                                break
                            # Process audio chunk
                            if isinstance(audio_chunk, AudioChunk):
                                audio_data = audio_chunk.audio_data
                                sample_rate = audio_chunk.sample_rate
                            else:
                                audio_data = audio_chunk
                                sample_rate = self._config.sample_rate
                            
                            # Convert to numpy array if needed
                            if isinstance(audio_data, list):
                                audio_data = np.array(audio_data)
                            
                            # Ensure correct dtype (int16 for PCM 16-bit)
                            if audio_data.dtype != np.int16:
                                if audio_data.dtype == np.float32:
                                    # Convert float32 [-1, 1] to int16 [-32768, 32767]
                                    audio_data = (audio_data * 32767).astype(np.int16)
                                else:
                                    audio_data = audio_data.astype(np.int16)
                            
                            # Add to buffer
                            audio_buffer.append((audio_data, sample_rate))
                            
                        # Play accumulated audio
                        if audio_buffer:
                            # Concatenate audio chunks
                            audio_data = np.concatenate([chunk[0] for chunk in audio_buffer])
                            sample_rate = audio_buffer[0][1]  # Use sample rate from first chunk
                            
                            # Play audio non-blocking with proper cleanup
                            await self._play_audio(audio_data, sample_rate)
                            
                            # Clear buffers
                            audio_buffer = []
                            text_buffer = ""
                            
                    except ValueError as e:
                        if "invalid transcript" in str(e):
                            # Skip this chunk and continue accumulating
                            continue
                        else:
                            raise
                    
            # Handle any remaining text in buffer
            if text_buffer and any(c.isalnum() for c in text_buffer):
                try:
                    async for audio_chunk in self._tts.synthesize(text_buffer):
                        if self._was_interrupted:
                            break
                        # Process audio chunk
                        if isinstance(audio_chunk, AudioChunk):
                            audio_data = audio_chunk.audio_data
                            sample_rate = audio_chunk.sample_rate
                        else:
                            audio_data = audio_chunk
                            sample_rate = self._config.sample_rate
                        
                        # Convert to numpy array if needed
                        if isinstance(audio_data, list):
                            audio_data = np.array(audio_data)
                        
                        # Ensure correct dtype (int16 for PCM 16-bit)
                        if audio_data.dtype != np.int16:
                            if audio_data.dtype == np.float32:
                                # Convert float32 [-1, 1] to int16 [-32768, 32767]
                                audio_data = (audio_data * 32767).astype(np.int16)
                            else:
                                audio_data = audio_data.astype(np.int16)
                        
                        # Add to buffer
                        audio_buffer.append((audio_data, sample_rate))
                    
                    # Play any remaining audio
                    if audio_buffer:
                        # Concatenate audio chunks
                        audio_data = np.concatenate([chunk[0] for chunk in audio_buffer])
                        sample_rate = audio_buffer[0][1]  # Use sample rate from first chunk
                        
                        # Play the final chunk
                        sd.play(audio_data, sample_rate, blocking=False)
                        await asyncio.sleep(len(audio_data) / sample_rate)
                        
                except ValueError as e:
                    if not "invalid transcript" in str(e):
                        raise
                    
            if not self._was_interrupted:
                # Add assistant's response to chat context
                self._chat_context.messages.append(
                    Message(role="assistant", content=response_text)
                )
                await self.emit("agent_speech_committed", Message(role="assistant", content=response_text))
                
        finally:
            self._is_speaking = False
            self._can_be_interrupted = True
            self._current_speech_text = ""
            self._state = "listening"
            await self.emit("agent_stopped_speaking")
            
    @property
    def state(self) -> AgentState:
        """Get the current agent state."""
        return self._state 