import asyncio
import os

import aiohttp
from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.gemini_multimodal_live.gemini import (
    GeminiMultimodalLiveLLMService,
)
from pipecat.transports.services.daily import DailyParams, DailyTransport

from config.settings import SYSTEM_INSTRUCTION, TOOLS
from services.daily import configure
from utils.logger import setup_logger


load_dotenv(override=True)
setup_logger()


async def main():
    """Main application entry point."""
    async with aiohttp.ClientSession() as session:
        # Configure Daily room
        room_url, token = await configure(session)

        # Set up Daily transport
        transport = DailyTransport(
            room_url,
            token,
            "Latest news!",
            DailyParams(
                audio_out_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
                vad_audio_passthrough=True,
            ),
        )

        # Initialize Gemini model
        llm = GeminiMultimodalLiveLLMService(
            api_key=os.getenv("GEMINI_API_KEY"),
            voice_id="Puck",  # Available voices: Aoede, Charon, Fenrir, Kore, Puck
            transcribe_user_audio=True,
            transcribe_model_audio=True,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=TOOLS,
        )

        # Set up conversation context
        context = OpenAILLMContext(
            [
                {
                    "role": "user",
                    "content": (
                        "Start by greeting the user warmly, introducing yourself, "
                        "and mentioning the current day. Be friendly and engaging "
                        "to set a positive tone for the interaction."
                    ),
                }
            ],
        )
        context_aggregator = llm.create_context_aggregator(context)

        # Create pipeline
        pipeline = Pipeline(
            [
                transport.input(),  # Transport user input
                context_aggregator.user(),  # User responses
                llm,  # LLM processing
                transport.output(),  # Transport bot output
                context_aggregator.assistant(),  # Assistant responses
            ]
        )

        # Set up pipeline task
        task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            """Handle first participant joining the room."""
            await transport.capture_participant_transcription(participant["id"])
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        # Run the pipeline
        runner = PipelineRunner()
        await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
