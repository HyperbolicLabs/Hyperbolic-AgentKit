import requests
import json
from typing import Optional
from collections.abc import Callable
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.utils import get_api_key

LINK_WALLET_ADDRESS_PROMPT = """
This tool will allow you to link a wallet address to your Hyperbolic account. 

It takes the following inputs:
- wallet_address: The wallet address to link to your Hyperbolic account

Important notes:        
- All inputs must be recognized in order to process the linking
- The user is identified by the bearer token in the request header
- If the wallet address is not provided, use your own wallet address
- After you link the wallet address, tell the user that they should send either USDC, USDT, or DAI on Base network to Hyperbolic address: 0xd3cB24E0Ba20865C530831C85Bd6EbC25f6f3B60
"""


class LinkWalletAddressInput(BaseModel):
    """Input argument schema for wallet linking action."""

    wallet_address: str = Field(
        ..., description="The wallet address to link to your Hyperbolic account")


def link_wallet_address(wallet_address: str) -> str:
    """
   Links a wallet address to your Hyperbolic account and returns the response as a formatted string.

   Args:
       wallet_address (str): The wallet address to link to your Hyperbolic account

   Returns:
       str: A formatted string representation of the API response

   Raises:
       requests.exceptions.RequestException: If the API request fails
       ValueError: If required parameters are invalid
   """
    # Input validation
    if not wallet_address:
        raise ValueError("wallet_address is required")

    # Get API key from environment
    api_key = get_api_key()

    # Prepare the request
    endpoint = "https://api.hyperbolic.xyz/settings/crypto-address"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "address": wallet_address
    }

    try:
        # Make the request
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()

        # Get the response content
        response_data = response.json()

        # Convert the response to a formatted string
        # We use json.dumps with indent=2 for pretty printing
        formatted_response = json.dumps(response_data, indent=2)

        return formatted_response

    except requests.exceptions.RequestException as e:
        # For HTTP errors, we want to include the status code and response content if available
        error_message = f"Error linking wallet address to your Hyperbolic account: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                # Try to get JSON error message if available
                error_content = e.response.json()
                error_message += f"\nResponse: {json.dumps(error_content, indent=2)}"
            except json.JSONDecodeError:
                # If response isn't JSON, include the raw text
                error_message += f"\nResponse: {e.response.text}"

        raise requests.exceptions.RequestException(error_message)


class LinkWalletAddressAction(HyperbolicAction):
    """Link wallet address action."""

    name: str = "link_wallet_address"
    description: str = LINK_WALLET_ADDRESS_PROMPT
    args_schema: type[BaseModel] | None = LinkWalletAddressInput
    func: Callable[..., str] = link_wallet_address 