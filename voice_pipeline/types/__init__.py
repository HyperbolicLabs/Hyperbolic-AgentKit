from enum import Enum, auto
from typing import Literal, TypeAlias
from dataclasses import dataclass

# Agent state type
AgentState = Literal["initializing", "listening", "thinking", "speaking"]

class EventTypes(str, Enum):
    """Event types for the pipeline."""
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    VAD_DATA = "vad_data"
    AGENT_STARTED_SPEAKING = "agent_started_speaking"
    AGENT_STOPPED_SPEAKING = "agent_stopped_speaking"
    USER_SPEECH_COMMITTED = "user_speech_committed"
    AGENT_SPEECH_COMMITTED = "agent_speech_committed"
    AGENT_SPEECH_INTERRUPTED = "agent_speech_interrupted"
    FUNCTION_CALLS_COLLECTED = "function_calls_collected"
    FUNCTION_CALLS_FINISHED = "function_calls_finished"
    METRICS_COLLECTED = "metrics_collected"

class SpeechSource(Enum):
    """Source of speech in the pipeline"""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"

@dataclass
class AudioChunk:
    """A chunk of audio data with its sample rate."""
    audio_data: list[float]
    sample_rate: int
    
    def __len__(self) -> int:
        """Get the length of the audio data."""
        return len(self.audio_data)

# Type aliases for clarity
AudioSample: TypeAlias = float
TranscriptText: TypeAlias = str 