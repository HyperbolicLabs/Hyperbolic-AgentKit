from dataclasses import dataclass
from typing import Optional

from .voice_pipeline_agent import VoicePipelineAgent, PipelineConfig
from .silero_vad import SileroVAD
from .deepgram_stt import DeepgramSTT
from .cartesia_tts import CartesiaTTS, CartesiaTTSConfig
from .openai_llm import OpenAILLM

@dataclass
class PipelineCredentials:
    """API credentials for the pipeline components."""
    deepgram_api_key: str
    cartesia_api_key: str
    openai_api_key: str

class VoicePipelineFactory:
    """Factory for creating voice pipeline instances."""
    
    @staticmethod
    def create_pipeline(
        credentials: PipelineCredentials,
        config: Optional[PipelineConfig] = None,
        tts_config: Optional[CartesiaTTSConfig] = None,
        openai_model: str = "gpt-4o-mini-2024-07-18",
        vad_threshold: float = 0.5
    ) -> VoicePipelineAgent:
        """Create a new voice pipeline instance.
        
        Args:
            credentials: API credentials for the components
            config: Optional pipeline configuration
            tts_config: Optional TTS configuration
            openai_model: OpenAI model to use
            vad_threshold: Threshold for Silero VAD (0.0 to 1.0)
            
        Returns:
            A configured voice pipeline agent
        """
        # Create VAD component
        vad = SileroVAD(threshold=vad_threshold)
        
        # Create STT component
        stt = DeepgramSTT(api_key=credentials.deepgram_api_key)
        
        # Create TTS component
        if tts_config is None:
            tts_config = CartesiaTTSConfig()
        tts = CartesiaTTS(
            api_key=credentials.cartesia_api_key,
            config=tts_config
        )
        
        # Create LLM component
        llm = OpenAILLM(
            api_key=credentials.openai_api_key,
            model=openai_model
        )
        
        # Create pipeline configuration
        if config is None:
            config = PipelineConfig()
            
        # Create and return pipeline agent
        return VoicePipelineAgent(
            vad=vad,
            stt=stt,
            llm=llm,
            tts=tts,
            config=config
        ) 