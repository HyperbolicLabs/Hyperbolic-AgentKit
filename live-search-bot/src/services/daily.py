import argparse
import os
from typing import Tuple

import aiohttp
from loguru import logger
from pipecat.transports.services.helpers.daily_rest import DailyRESTHelper


async def configure(session: aiohttp.ClientSession) -> Tuple[str, str]:
    """Configure Daily room and return URL and token.

    Args:
        session: aiohttp client session

    Returns:
        Tuple containing room URL and token
    """
    url, token, _ = await configure_with_args(session)
    return url, token


async def configure_with_args(
    session: aiohttp.ClientSession,
    parser: argparse.ArgumentParser | None = None
) -> Tuple[str, str, argparse.Namespace]:
    """Configure Daily room with command line arguments.

    Args:
        session: aiohttp client session
        parser: Optional argument parser to extend

    Returns:
        Tuple containing room URL, token and parsed args
    """
    if not parser:
        parser = argparse.ArgumentParser(description="Daily AI News Bot")
    parser.add_argument(
        "-u", "--url",
        type=str,
        required=False,
        help="URL of the Daily room to join"
    )
    parser.add_argument(
        "-k", "--apikey",
        type=str,
        required=False,
        help="Daily API Key (needed to create an owner token)"
    )

    args, _ = parser.parse_known_args()

    url = args.url or os.getenv("DAILY_SAMPLE_ROOM_URL")
    key = args.apikey or os.getenv("DAILY_API_KEY")

    if not url:
        raise ValueError(
            "No Daily room specified. Use -u/--url option or set "
            "DAILY_SAMPLE_ROOM_URL in your environment."
        )

    if not key:
        raise ValueError(
            "No Daily API key specified. Use -k/--apikey option or set "
            "DAILY_API_KEY in your environment."
        )

    daily_rest_helper = DailyRESTHelper(
        daily_api_key=key,
        daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
        aiohttp_session=session,
    )

    # Create token with 1 hour expiration
    expiry_time = 60 * 60
    token = await daily_rest_helper.get_token(url, expiry_time)
    logger.info(f"Created token for room: {url}")

    return url, token, args