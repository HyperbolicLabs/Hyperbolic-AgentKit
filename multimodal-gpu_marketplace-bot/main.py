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
from datetime import datetime

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


async def fetch_marketplace_data(
    function_name, tool_call_id, args, llm, context, result_callback
):
    async with aiohttp.ClientSession() as session:
        try:
            url = "https://api.hyperbolic.xyz/v1/marketplace"
            headers = {"Content-Type": "application/json"}
            filters = {} if args["filter_type"] == "all" else {"available": True}
            data = {"filters": filters}

            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    marketplace_data = await response.json()
                    available_instances = [
                        {
                            "id": instance["id"],
                            "gpu_model": instance["hardware"]["gpus"][0]["model"],
                            "gpu_memory": instance["hardware"]["gpus"][0]["ram"],
                            "price_per_hour": instance["pricing"]["price"]["amount"],
                            "location": instance["location"]["region"],
                            "available": not instance["reserved"]
                            and instance["gpus_reserved"] < instance["gpus_total"],
                        }
                        for instance in marketplace_data["instances"]
                        if "gpus" in instance["hardware"]
                        and instance["hardware"]["gpus"]
                    ]
                    await result_callback({"instances": available_instances})
                else:
                    await result_callback(
                        {"error": f"API request failed with status {response.status}"}
                    )
        except Exception as e:
            await result_callback({"error": str(e)})


tools = [
    {
        "function_declarations": [
            {
                "name": "get_available_gpus",
                "description": "Get the list of available GPU instances in the marketplace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter_type": {
                            "type": "string",
                            "enum": ["all", "available_only"],
                            "description": "Filter type for GPU instances",
                        }
                    },
                    "required": ["filter_type"],
                },
            }
        ]
    }
]

system_instruction = """
You are a helpful assistant for Hyperbolic Labs' GPU Marketplace. You can help users find and understand available GPU instances for rent.

You have access to the marketplace data through the get_available_gpus tool. When users ask about available GPUs, pricing,
or specifications, use this tool to get the most current information.

Always be professional and helpful. When listing GPUs:
1. Mention the GPU model, memory, and hourly price
2. Indicate if the instance is currently available
3. Include the location/region

If users ask about specific GPU models or price ranges, filter and highlight the relevant options from the data.
"""


async def main():
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
                # set stop_secs to something roughly similar to the internal setting
                # of the Multimodal Live api, just to align events. This doesn't really
                # matter because we can only use the Multimodal Live API's phrase
                # endpointing, for now.
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.5)),
            ),
        )

        llm = GeminiMultimodalLiveLLMService(
            api_key=os.getenv("GOOGLE_API_KEY"),
            system_instruction=system_instruction,
            tools=tools,
        )

        llm.register_function("get_available_gpus", fetch_marketplace_data)

        context = OpenAILLMContext(
            [
                {
                    "role": "user",
                    "content": "Start by greeting me warmly and introducing me to GPU Rentals by Hyperbolic Labs and mention that you can do everything verbally. Encourage me to start by asking available GPU.",
                }
            ],
        )
        context_aggregator = llm.create_context_aggregator(context)

        pipeline = Pipeline(
            [
                transport.input(),
                context_aggregator.user(),
                llm,
                context_aggregator.assistant(),
                transport.output(),
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
            await task.queue_frames([context_aggregator.user().get_context_frame()])

        runner = PipelineRunner()

        await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
