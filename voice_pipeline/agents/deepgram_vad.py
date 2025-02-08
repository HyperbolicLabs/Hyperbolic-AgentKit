import asyncio
import time
import numpy as np
from typing import Optional
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)

from ..core.vad import VAD, VADEvent, VADCapabilities
from ..types import AudioChunk

class DeepgramVADCapabilities(VADCapabilities):
    """Deepgram VAD capabilities."""
    @property
    def streaming(self) -> bool:
        return True

class DeepgramVAD(VAD):
    """Voice Activity Detection using Deepgram's API."""
    
    def __init__(self, api_key: str):
        super().__init__()
        self._capabilities = DeepgramVADCapabilities()
        
        # Initialize Deepgram client
        config = DeepgramClientOptions(verbose=False)
        self._client = DeepgramClient(api_key=api_key, config=config)
        
        # Connection state
        self._connection = None
        self._connection_ready = asyncio.Event()
        self._speech_probability = 0.0
        self._speech_start_time: Optional[float] = None
        self._last_activity_time = time.time()
        
    @property
    def capabilities(self) -> VADCapabilities:
        return self._capabilities
        
    async def process_chunk(self, chunk: AudioChunk) -> None:
        """Process an audio chunk for voice activity."""
        try:
            print(f"VAD: Processing chunk of type {type(chunk)}, length {len(chunk)}")
            
            if not self._connection:
                print("VAD: No connection, setting up new connection")
                await self._setup_connection()
            
            # Wait for connection to be ready
            if not self._connection_ready.is_set():
                print("VAD: Connection not ready, waiting for ready state")
                try:
                    await asyncio.wait_for(self._connection_ready.wait(), timeout=5.0)
                    print("VAD: Connection is now ready")
                except asyncio.TimeoutError:
                    print("VAD: Timeout waiting for connection ready")
                    await self._reset_connection()
                    return
                
            # Convert audio chunk to numpy array and then to bytes
            print("VAD: Converting audio chunk to numpy array")
            audio_array = np.array(chunk, dtype=np.float32)
            print(f"VAD: Audio array shape: {audio_array.shape}, dtype: {audio_array.dtype}")
            
            # Convert to 16-bit PCM
            print("VAD: Converting to 16-bit PCM")
            audio_array = (audio_array * 32767).astype(np.int16)
            print(f"VAD: PCM array shape: {audio_array.shape}, dtype: {audio_array.dtype}")
            
            audio_bytes = audio_array.tobytes()
            print(f"VAD: Converted to {len(audio_bytes)} bytes")
            
            # Only send if connection exists and is ready
            if self._connection and self._connection_ready.is_set():
                print("VAD: Sending audio bytes to Deepgram")
                try:
                    if hasattr(self._connection, 'socket') and self._connection.socket:
                        await self._connection.socket.send(audio_bytes)
                        print("VAD: Successfully sent audio bytes")
                    else:
                        print("VAD: Socket not available, resetting connection")
                        await self._reset_connection()
                except Exception as send_error:
                    print(f"VAD: Error sending audio bytes: {type(send_error).__name__}: {str(send_error)}")
                    await self._reset_connection()
            else:
                print("VAD: Connection not ready or not connected")
                await self._reset_connection()
                
        except Exception as e:
            print(f"VAD: Error in process_chunk: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"VAD: Traceback:\n{traceback.format_exc()}")
            await self._reset_connection()
        
    async def _setup_connection(self):
        """Setup the Deepgram WebSocket connection."""
        try:
            # Configure Deepgram streaming
            options = LiveOptions(
                model="nova-2",
                punctuate=False,
                language="en-US",
                encoding="linear16",
                channels=1,
                sample_rate=16000,
                smart_format=True,
                interim_results=False,
                vad_events=True
            )
            
            print("VAD: Creating new Deepgram connection")
            # Create connection
            self._connection = self._client.listen.websocket.v("1")
            
            # Clear any existing ready state
            self._connection_ready.clear()
            
            # Setup event handlers
            def on_speech_started(client, event):
                print("VAD: Speech started event received")
                self._handle_speech_started()
                
            def on_speech_ended(client, event):
                print("VAD: Speech ended event received")
                self._handle_speech_ended()
                
            def on_error(client, error):
                print(f"VAD: Deepgram error: {error}")
                
            def on_close(client, event):
                print(f"VAD: Connection closed: {event}")
                self._connection_ready.clear()
                
            def on_open(client, event):
                print(f"VAD: Connection opened: {event}")
                self._connection_ready.set()
                
            # Register handlers
            print("VAD: Registering event handlers")
            self._connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
            self._connection.on(LiveTranscriptionEvents.UtteranceEnd, on_speech_ended)
            self._connection.on(LiveTranscriptionEvents.Error, on_error)
            self._connection.on(LiveTranscriptionEvents.Close, on_close)
            self._connection.on(LiveTranscriptionEvents.Open, on_open)
            
            # Start connection
            print("VAD: Starting connection")
            self._connection.start(options)
            
            # Wait for connection to be ready
            print("VAD: Waiting for connection to be ready")
            try:
                # Wait for both connection ready and socket initialization
                max_retries = 5
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        # First wait for the open event
                        await asyncio.wait_for(self._connection_ready.wait(), timeout=1.0)
                        
                        # Then check for socket initialization
                        if hasattr(self._connection, 'socket') and self._connection.socket is not None:
                            print("VAD: Connection and socket successfully initialized")
                            return
                            
                        print(f"VAD: Attempt {retry_count + 1}/{max_retries} - Connection ready but waiting for socket")
                        await asyncio.sleep(0.5)
                        
                    except asyncio.TimeoutError:
                        print(f"VAD: Attempt {retry_count + 1}/{max_retries} - Timeout waiting for connection")
                        
                    retry_count += 1
                    
                    # Clear and restart connection if we haven't succeeded
                    if retry_count < max_retries:
                        print("VAD: Retrying connection setup")
                        await self._reset_connection()
                        self._connection = self._client.listen.websocket.v("1")
                        self._connection_ready.clear()
                        
                        # Re-register handlers
                        self._connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
                        self._connection.on(LiveTranscriptionEvents.UtteranceEnd, on_speech_ended)
                        self._connection.on(LiveTranscriptionEvents.Error, on_error)
                        self._connection.on(LiveTranscriptionEvents.Close, on_close)
                        self._connection.on(LiveTranscriptionEvents.Open, on_open)
                        
                        # Restart connection
                        self._connection.start(options)
                
                print("VAD: Failed to initialize socket after all retries")
                raise RuntimeError("Failed to initialize socket after multiple attempts")
                    
            except Exception as e:
                print(f"VAD: Error during connection setup: {str(e)}")
                await self._reset_connection()
                raise
                
        except Exception as e:
            print(f"VAD: Error in setup_connection: {str(e)}")
            await self._reset_connection()
            raise
        
    def _handle_speech_started(self):
        """Handle speech started event from Deepgram."""
        current_time = time.time()
        self._speech_start_time = current_time
        self._last_activity_time = current_time
        self._is_speaking = True
        
        event = VADEvent(
            speech_probability=1.0,
            speech_duration=0.0,
            silence_duration=current_time - (self._last_activity_time or current_time),
            raw_accumulated_speech=0.0,
            raw_accumulated_silence=0.0
        )
        self.emit("user_started_speaking", event)
        
    def _handle_speech_ended(self):
        """Handle speech ended event from Deepgram."""
        current_time = time.time()
        speech_duration = (
            current_time - self._speech_start_time 
            if self._speech_start_time is not None 
            else 0.0
        )
        self._last_activity_time = current_time
        self._is_speaking = False
        self._speech_start_time = None
        
        event = VADEvent(
            speech_probability=0.0,
            speech_duration=speech_duration,
            silence_duration=0.0,
            raw_accumulated_speech=speech_duration,
            raw_accumulated_silence=0.0
        )
        self.emit("user_stopped_speaking", event)
        
    async def _reset_connection(self):
        """Reset the Deepgram connection."""
        if self._connection:
            try:
                self._connection.finish()
            except:
                pass
            self._connection = None
            self._connection_ready.clear()
            
    async def reset(self) -> None:
        """Reset the VAD state."""
        await super().reset()
        await self._reset_connection()
        
    async def aclose(self) -> None:
        """Clean up resources."""
        await self._reset_connection() 