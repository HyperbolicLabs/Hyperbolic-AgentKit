import asyncio
import numpy as np
from typing import Protocol, List, Optional, Callable, Any, Dict
import backoff
import websockets
import json
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)

from ..core.stt import STT, STTCapabilities, TranscriptionAlternative, SpeechEvent
from ..types import AudioChunk
from ..core.event_emitter import EventEmitter

# Constants
KEEPALIVE_MSG = json.dumps({"type": "KeepAlive"})
CLOSE_MSG = json.dumps({"type": "CloseStream"})
FINALIZE_MSG = json.dumps({"type": "Finalize"})

class DeepgramSTTCapabilities(STTCapabilities):
    """Deepgram STT capabilities."""
    @property
    def streaming(self) -> bool:
        return True
        
    @property
    def interim_results(self) -> bool:
        return True
        
    @property
    def language_detection(self) -> bool:
        return True

class DeepgramSTT(STT, EventEmitter):
    """Speech-to-Text using Deepgram's API."""
    
    def __init__(self, api_key: str):
        STT.__init__(self)
        EventEmitter.__init__(self)
        self._capabilities = DeepgramSTTCapabilities()
        self._api_key = api_key
        
        # Connection state
        self._websocket = None
        self._connection_ready = asyncio.Event()
        self._speaking = False
        self._request_id = ""
        
        # Keepalive task
        self._keepalive_task = None
        
    @property
    def capabilities(self) -> STTCapabilities:
        return self._capabilities
        
    def _convert_to_bytes(self, chunk: AudioChunk) -> bytes:
        """Convert audio chunk to bytes in the format expected by Deepgram."""
        # Convert to numpy array if not already
        if isinstance(chunk.audio_data, np.ndarray):
            audio_array = chunk.audio_data
        else:
            audio_array = np.array(chunk.audio_data)
            
        # Ensure float32
        if audio_array.dtype != np.float32:
            audio_array = audio_array.astype(np.float32)
            
        # Normalize if needed
        if np.abs(audio_array).max() > 1.0:
            audio_array = audio_array / np.abs(audio_array).max()
            
        # Convert to 16-bit PCM
        audio_array = (audio_array * 32767).astype(np.int16)
        
        # Convert to bytes
        return audio_array.tobytes()
        
    async def process_chunk(self, chunk: AudioChunk) -> None:
        """Process an audio chunk for speech recognition."""
        try:
            if not self._websocket or not self._connection_ready.is_set():
                await self._setup_connection()
                
            if self._websocket and self._connection_ready.is_set():
                audio_data = self._convert_to_bytes(chunk)
                await self._websocket.send(audio_data)
            else:
                print("STT: Connection not ready, skipping chunk")
                
        except Exception as e:
            print(f"STT: Error processing chunk: {str(e)}")
            await self._reset_connection()
            
    async def _setup_connection(self):
        """Set up the Deepgram WebSocket connection."""
        if self._websocket:
            await self._reset_connection()
            
        self._connection_ready.clear()
        
        try:
            print("STT: Setting up new connection...")
            
            # Prepare connection parameters
            url = "wss://api.deepgram.com/v1/listen"
            params = {
                "encoding": "linear16",
                "sample_rate": 16000,
                "channels": 1,
                "language": "en",
                "model": "nova-2",
                "interim_results": "true",
                "punctuate": "true",
                "smart_format": "true",
                "vad_events": "true",
                "endpointing": "25",
                "filler_words": "true"
            }
            
            # Add parameters to URL
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query_string}"
            
            # Prepare headers with API key
            headers = {
                "Authorization": f"Token {self._api_key}"
            }
            
            # Connect to WebSocket
            self._websocket = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=None  # Disable automatic ping to handle manually
            )
            print("STT: WebSocket connected")
            
            # Start message handler and keepalive
            asyncio.create_task(self._handle_messages())
            self._keepalive_task = asyncio.create_task(self._keepalive())
            
            # Wait for connection to be ready
            self._connection_ready.set()
            print("STT: Connection ready")
            
        except Exception as e:
            print(f"STT: Error setting up connection: {str(e)}")
            await self._reset_connection()
            raise
            
    async def _keepalive(self):
        """Send keepalive messages to maintain the connection."""
        try:
            while True:
                if self._websocket and not self._websocket.closed:
                    await self._websocket.send(KEEPALIVE_MSG)
                await asyncio.sleep(5)
        except Exception as e:
            print(f"STT: Keepalive error: {str(e)}")
            
    async def _handle_messages(self):
        """Handle incoming WebSocket messages."""
        try:
            async for message in self._websocket:
                try:
                    result = json.loads(message)
                    print(f"STT: Received message type: {result.get('type')}")
                    
                    if result["type"] == "SpeechStarted":
                        print(f"STT: Speech started event at timestamp {result.get('timestamp', 0)}")
                        if not self._speaking:
                            self._speaking = True
                            print("STT: Emitting speech_started event")
                            # Create start event without transcript
                            start_event = SpeechEvent(
                                alternatives=[],
                                is_final=False
                            )
                            await self.emit("speech_start", start_event)
                            
                    elif result["type"] == "Results":
                        if "channel" in result and "alternatives" in result["channel"]:
                            alternatives = []
                            for alt in result["channel"]["alternatives"]:
                                transcript = alt.get("transcript", "")
                                confidence = alt.get("confidence", 0.0)
                                # Only add non-empty transcripts
                                if transcript.strip():
                                    alternatives.append(
                                        TranscriptionAlternative(
                                            text=transcript,
                                            confidence=confidence
                                        )
                                    )
                            
                            # Only process if we have alternatives
                            if alternatives:
                                is_final = result.get("is_final", False)
                                is_endpoint = result.get("speech_final", False)
                                
                                # Update request ID
                                if "metadata" in result:
                                    self._request_id = result["metadata"].get("request_id", "")
                                    print(f"STT: Updated request_id to {self._request_id}")
                                
                                # Create event with just the required parameters
                                event = SpeechEvent(
                                    alternatives=alternatives,
                                    is_final=is_final
                                )
                                
                                # Emit appropriate events
                                if is_final:
                                    print(f"STT: Emitting final transcript: {alternatives[0].text}")
                                    await self.emit("final_transcript", event)
                                else:
                                    print(f"STT: Emitting interim transcript: {alternatives[0].text}")
                                    await self.emit("interim_transcript", event)
                                    
                                # Handle speech endpoint
                                if is_endpoint and self._speaking:
                                    print("STT: Speech endpoint detected, emitting speech_ended")
                                    self._speaking = False
                                    end_event = SpeechEvent(
                                        alternatives=[],
                                        is_final=True
                                    )
                                    await self.emit("speech_end", end_event)
                            
                except Exception as e:
                    print(f"STT: Error processing message: {str(e)}")
                    import traceback
                    print(f"STT: Error traceback: {traceback.format_exc()}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("STT: WebSocket connection closed")
            self._connection_ready.clear()
            await self._reset_connection()
            
        except Exception as e:
            print(f"STT: Error in message handler: {str(e)}")
            import traceback
            print(f"STT: Error traceback: {traceback.format_exc()}")
            await self._reset_connection()

    async def _reset_connection(self):
        """Reset the connection state."""
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
            
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                print(f"STT: Error closing connection: {str(e)}")
            finally:
                self._websocket = None
                self._connection_ready.clear()
                self._speaking = False

    async def reset(self) -> None:
        """Reset the STT component."""
        await self._reset_connection()

    async def aclose(self) -> None:
        """Close the STT component."""
        # Send CloseStream message if connection is active
        if self._websocket and not self._websocket.closed:
            try:
                await self._websocket.send_str(CLOSE_MSG)
                await self._websocket.send_str(FINALIZE_MSG)
            except:
                pass
        await self._reset_connection() 