from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from eth_account import Account
import secrets


class GenerateEthKeyOutput(BaseModel):
    """Output schema for the Ethereum key generation."""


GENERATE_ETH_KEY_PROMPT = """
IMPORTANT: ANY OPERATION INVOLVING GENERATION OF PRIVATE KEYS SHOULD INVOLVE APPROVAL BY THE USER. Before performing this action, ask for permission from the user. This action involves sensitive operations and if done incorrectly can lead to loss of funds.

This action is responsible for generating a new Ethereum account by creating a secure random private key and deriving its corresponding public address. This account can be used to fund staking deposits.

Prerequisites:
- None. This action can be run independently.

It does not take any inputs.

Important notes:
- The private key will be returned with '0x' prefix
- The address will be returned with '0x' prefix
- THE PRIVATE KEY SHOULD BE STORED SECURELY AND NEVER SHARED
- Make sure to save both the address and private key as they cannot be recovered if lost

Returns:
- A dictionary containing:
  - address: The Ethereum public address
  - private_key: The private key for the account
"""


def generate_eth_key() -> str:
    """
    Generate a new Ethereum public/private key pair.

    Returns:
        str: JSON string containing the address and private key
    """
    # Generate a random private key using secrets
    priv = secrets.token_bytes(32)
    private_key = "0x" + priv.hex()

    # Create an account from the private key
    account = Account.from_key(private_key)

    return f"""Generated new Ethereum account:
Address: {account.address}
Private Key: {private_key}

IMPORTANT: Save this private key securely. It cannot be recovered if lost."""


class GenerateEthKeyAction(HyperbolicAction):
    """Action to generate a new Ethereum key pair."""

    name: str = "generate_eth_key"
    description: str = GENERATE_ETH_KEY_PROMPT
    args_schema: type[BaseModel] = GenerateEthKeyOutput
    func: Callable[..., str] = generate_eth_key
