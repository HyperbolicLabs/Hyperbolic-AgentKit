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
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.hyperbolic.xyz/v1/marketplace"
            headers = {"Content-Type": "application/json"}
            filters = {} if args["filter_type"] == "all" else {"available": True}
            data = {"filters": filters}

            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    marketplace_data = await response.json()
                    available_instances = [
                        {
                            "quantity": f"{instance.get('gpus_total', 1)} X",
                            "gpu_type": instance["hardware"]["gpus"][0]["model"],
                            "gpu_ram": f"GPU RAM: {instance['hardware']['gpus'][0]['ram']}GB",
                            "storage": (
                                f"{instance['hardware']['storage'][0]['capacity']} TB"
                                if instance["hardware"].get("storage")
                                else "N/A"
                            ),
                            "system_ram": (
                                f"RAM:\n{instance['hardware']['ram'][0]['capacity'] / 1024:.1f} TB"
                                if instance["hardware"].get("ram")
                                else "N/A"
                            ),
                            "price": (
                                f"${float(instance['pricing']['price']['amount']):.2f}/hr"
                                if float(instance["pricing"]["price"]["amount"]) >= 1.00
                                else f"{int(float(instance['pricing']['price']['amount']) * 100)}¢/hr"
                            ),
                            "price_float": float(
                                instance["pricing"]["price"]["amount"]
                            ),  # For sorting
                            "status": (
                                "Reserved" if instance["reserved"] else "Buy Credits"
                            ),
                            "available": not instance["reserved"]
                            and instance["gpus_reserved"] < instance["gpus_total"],
                        }
                        for instance in marketplace_data["instances"]
                        if "gpus" in instance["hardware"]
                        and instance["hardware"]["gpus"]
                    ]

                    # Sort by price if requested
                    if args.get("sort_by") == "price_low_to_high":
                        available_instances.sort(key=lambda x: x["price_float"])

                    # Filter by price range if specified
                    price_range = args.get("price_range")
                    if price_range:
                        if price_range == "budget":
                            available_instances = [
                                i for i in available_instances if i["price_float"] < 0.5
                            ]
                        elif price_range == "mid":
                            available_instances = [
                                i
                                for i in available_instances
                                if 0.5 <= i["price_float"] < 1.0
                            ]
                        elif price_range == "high":
                            available_instances = [
                                i
                                for i in available_instances
                                if i["price_float"] >= 1.0
                            ]

                    # Apply filters
                    filtered_instances = available_instances

                    # Quantity filter
                    if args.get("quantity"):
                        if args["quantity"] == "8X+":
                            filtered_instances = [
                                i
                                for i in filtered_instances
                                if int(i["quantity"].split(" ")[0]) >= 8
                            ]
                        else:
                            target_quantity = int(args["quantity"].replace("X", ""))
                            filtered_instances = [
                                i
                                for i in filtered_instances
                                if int(i["quantity"].split(" ")[0]) == target_quantity
                            ]

                    # Storage filter
                    if args.get("storage"):
                        if args["storage"] == "0-500GB":
                            filtered_instances = [
                                i
                                for i in filtered_instances
                                if i["storage"] != "N/A"
                                and float(i["storage"].split(" ")[0]) <= 500
                            ]
                        elif args["storage"] == "500GB-1TB":
                            filtered_instances = [
                                i
                                for i in filtered_instances
                                if i["storage"] != "N/A"
                                and 500 < float(i["storage"].split(" ")[0]) <= 1000
                            ]

                    # Sort instances
                    if args.get("sort_by"):
                        if args["sort_by"] == "price_low_to_high":
                            filtered_instances.sort(key=lambda x: x["price_float"])
                        elif args["sort_by"] == "price_high_to_low":
                            filtered_instances.sort(
                                key=lambda x: x["price_float"], reverse=True
                            )

                    return await result_callback(
                        {"tool_call_id": tool_call_id, "instances": filtered_instances}
                    )
                else:
                    return await result_callback(
                        {
                            "tool_call_id": tool_call_id,
                            "error": f"API request failed with status {response.status}",
                        }
                    )
    except Exception as e:
        return await result_callback({"tool_call_id": tool_call_id, "error": str(e)})


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
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["price_low_to_high", "price_high_to_low"],
                            "description": "Sort instances by price",
                        },
                        "quantity": {
                            "type": "string",
                            "enum": [
                                "Any",
                                "1X",
                                "2X",
                                "3X",
                                "4X",
                                "5X",
                                "6X",
                                "7X",
                                "8X",
                                "8X+",
                            ],
                            "description": "Filter by GPU quantity",
                        },
                        "storage": {
                            "type": "string",
                            "enum": ["Any", "0-500GB", "500GB-1TB"],
                            "description": "Filter by storage capacity",
                        },
                        "location": {
                            "type": "string",
                            "enum": ["Any", "US, North America"],
                            "description": "Filter by location",
                        },
                    },
                    "required": ["filter_type"],
                },
            }
        ]
    }
]

system_instruction = """
You are a friendly GPU marketplace assistant. Keep responses concise and natural.

After greeting, immediately call `get_available_gpus` to fetch the list of available GPUs.

Available sorting and filtering options:
- Price: Low to High or High to Low
- Quantity: 1X to 8X+ GPUs
- Storage: 0-500GB or 500GB-1TB
- Location: Currently all in US, North America

Price formatting rules:
- Under $1: Use cents (e.g., "13¢/hr")
- $1 and above: Use dollars (e.g., "$2.(POINT)30/hr")
- There are no GPUs for rent that are HUNDREDS of dollars per hour.
- If you see a price like $100/hr, it's likely a bug. Read it again and check if you mistook the PERIOD for a COMMA.
- If hundreds, divide by 100 so you revert it to cents.
- If you say hundred dollars again, you will be punished.

Start by greeting and showing available GPUs sorted by price (low to high). Help users filter using any combination of:
- Quantity (e.g., "show me 8X GPUs")
- Storage (e.g., "GPUs with 500GB+ storage")
- Price sorting (e.g., "show highest price first")

When filtering, still call `get_available_gpus` with the appropriate filters.
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
