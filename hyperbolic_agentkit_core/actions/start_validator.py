from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager


class StartValidatorInput(BaseModel):
    """Input schema for starting the validator client."""

    consensus_dir: str = Field(
        ...,
        description="Full path to your consensus folder containing the validator wallet",
    )
    fee_recipient: str = Field(
        ...,
        description="Ethereum wallet address to receive priority fees/tips from block proposals",
    )


START_VALIDATOR_PROMPT = """
This action starts the Prysm validator client, connecting it to your beacon node and configuring 
it to receive priority fees (tips) when proposing blocks.

The validator client is responsible for:
1. Managing your validator keys securely
2. Signing attestations and block proposals
3. Collecting priority fees when proposing blocks
4. Maintaining connection with the beacon node

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`)
- The Prysm environment has been set up (via `setup_ethereum_node_environment`)
- The validator keys have been imported (via `configure_validator`)
- A functioning beacon node is running (via `run_full_ethereum_node`)
- A minimum of 32 ETH per validator has been deposited into the Ethereum 2.0 deposit contract (via `deposit_eth`)

Input parameters:
- consensus_dir: The full path to your consensus folder containing the validator wallet
- fee_recipient: Ethereum wallet address that will receive priority fees from block proposals

Important notes:
- The fee_recipient address must be set to receive priority fees/tips
- If fee_recipient is not set, tips will be sent to the burn address and lost
- The validator client must maintain a connection to your beacon node
- Requires an active SSH connection (use ssh_connect first)
"""


def start_validator(consensus_dir: str, fee_recipient: str) -> str:
    """
    Starts the Prysm validator client with the specified wallet directory and fee recipient.

    This function launches the validator client which will:
    - Connect to your beacon node
    - Load validator keys from the wallet directory
    - Sign attestations and blocks
    - Collect priority fees using the specified fee recipient address

    Args:
        consensus_dir: Full path to the consensus directory containing validator wallet
        fee_recipient: Ethereum address to receive priority fees from block proposals

    Returns:
        str: Command output or error message
    """
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect first."

    try:
        # Build the validator start command with all necessary parameters
        start_cmd = (
            f"$HOME/ethereum/consensus/prysm.sh validator "
            f"--wallet-dir={consensus_dir} "
            f"--holesky "
            f"--suggested-fee-recipient={fee_recipient}"
        )

        # Start the validator client
        output, error = ssh_manager.interactive_command(command=start_cmd)

        # Check for common error indicators
        if error:
            return f"Error starting validator client: {error}"

        # Look for successful startup indicators in output
        if "Starting validator client" in output:
            return (
                f"Validator client started successfully\n"
                f"Wallet Directory: {consensus_dir}\n"
                f"Fee Recipient: {fee_recipient}\n"
                f"Full output: {output}"
            )

        return output

    finally:
        # Clean up the interactive session
        ssh_manager.close_interactive_session()


class StartValidatorAction(HyperbolicAction):
    """Action to start the Prysm validator client with proper configuration."""

    name: str = "start_validator"
    description: str = START_VALIDATOR_PROMPT
    args_schema: type[BaseModel] | None = StartValidatorInput
    func: Callable[..., str] = start_validator
