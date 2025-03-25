#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

# Carl's note: we extended this code from the Daily SDK, which is licensed under the BSD 2-Clause License.
# # The Daily SDK is available at https://github.com/pipecat-ai/pipecat/tree/main

import asyncio
import os
import sys

import aiohttp
from dotenv import load_dotenv
from loguru import logger
from runner import configure

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.gemini_multimodal_live.gemini import (
    GeminiMultimodalLiveLLMService,
)
from pipecat.transports.services.daily import DailyParams, DailyTransport

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


async def main():
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")

    async with aiohttp.ClientSession() as session:
        (room_url, token) = await configure(session)

        transport = DailyTransport(
            room_url,
            token,
            "Respond bot",
            DailyParams(
                audio_out_enabled=True,
                vad_enabled=True,
                vad_audio_passthrough=True,
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.5)),
            ),
        )

        llm = GeminiMultimodalLiveLLMService(
            api_key=google_api_key,  # Use validated key
            voice_id="Aoede",  # Puck, Charon, Kore, Fenrir, Aoede
            system_instruction="Refer directly to screen elements when the user asks for help.",
            transcribe_user_audio=True,
            transcribe_model_audio=True,
            inference_on_context_initialization=False,
        )

        context = OpenAILLMContext(
            [
                {
                    "role": "user",
                    "content": "Welcome me to Hyperbolic Labs first. Tell me that I can see your camera feed, but tell me I have to click 'Share Screen' below first so I can help with your screen. Then I can tell you what's on your camera or where to click things!"
                },
            ],
        )
        context_aggregator = llm.create_context_aggregator(context)

        pipeline = Pipeline(
            [
                transport.input(),
                context_aggregator.user(),
                llm,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            # Enable both camera and screenshare. From the client side
            # send just one.
            await transport.capture_participant_video(
                participant["id"], framerate=1, video_source="screenVideo"
            )
            await transport.capture_participant_video(
                participant["id"], framerate=1, video_source="camera"
            )
            await task.queue_frames([context_aggregator.user().get_context_frame()])
            await asyncio.sleep(3)
            logger.debug("Unpausing audio and video")
            llm.set_audio_input_paused(False)
            llm.set_video_input_paused(False)

        runner = PipelineRunner()

        await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
