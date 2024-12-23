from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command


class RemoteShellInput(BaseModel):
    """Input argument schema for remote shell commands."""

    command: str = Field(
        ..., description="The shell command to execute on the remote server"
    )


START_VALIDATOR_PROMPT = """
IMPORTANT: ANY OPERATION INVOLVING GENERATION OF PRIVATE KEYS SHOULD BE INVOLVE APPROVAL BY THE USER. before performing this action, ask for permission from the user. This action involves sensitive operations and if done incorrectly can lead to loss of funds. 

This action is responsible for importing your keystores into your validatoor and starting the validator client.

Below is the command to import your keystores and start the validator client:

./prysm.sh validator accounts import --keys-dir=<YOUR_FOLDER_PATH> --holesky && ./prysm.sh validator --wallet-dir=<YOUR_FOLDER_PATH> --holesky --suggested-fee-recipient=<YOUR_WALLET_ADDRESS>> 

IMPORTANT: Make sure to replace <YOUR_FOLDER_PATH> with the path to your keystore folder and <YOUR_WALLET_ADDRESS> with your wallet address.

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).
- The prysm environment has been set up on the remote server (via `setup_ethereum_node_environment`).
- The Go Ethereum binary has been installed on the remote server (via `install_geth_binary`).
- A valid JWT token has been generated (via `generate_jwt_for_node`).
- A functioning execution client has been started (via `run_full_ethereum_node`).
- Private keys are have been generated, are accessible, are backed up, and are accessible (via `setup_depositor`).

Input parameters:
- command: The shell command to execute on the remote server

Important notes:
- Requires an active SSH connection (use ssh_connect first)
- Use 'ssh_status' to check current connection status
- Commands are executed in the connected SSH session
- Returns command output as a string
"""


def execute_remote_command(command: str) -> str:
    """
    Execute a command on the remote server.

    Args:
        command: The shell command to execute

    Returns:
        str: Command output or error message
    """
    # Special command to check SSH status
    if command.strip().lower() == "ssh_status":
        return ssh_manager.get_connection_info()

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    # Execute command remotely
    return ssh_manager.execute(command)


class StartValidatorAction(HyperbolicAction):
    """Run steps necesarry to start a full ethereum node"""

    name: str = "run_full_ethereum_node"
    description: str = START_VALIDATOR_PROMPT
    args_schema: type[BaseModel] | None = RemoteShellInput
    func: Callable[..., str] = execute_remote_command
