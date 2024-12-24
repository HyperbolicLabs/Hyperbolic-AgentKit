from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command


class SetupEthereumNodeInput(BaseModel):
    """Input argument schema for setting up Ethereum node environment."""


SETUP_ETH_ENV_PROMPT = """
Install necessary requirements to run an Ethereum node.

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).

This tool does not take any inputs.

Important notes:
- Requires an active SSH connection (use ssh_connect first)
- Use 'ssh_status' to check current connection status
- Commands are executed in the connected SSH session
- Returns command output as a string
"""


def setup_ethereum_node_environment() -> str:
    """
    Execute a command on the remote server.

    Returns:
        str: Command output or error message
    """

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    commands = [
        "mkdir ethereum",
        "mkdir ethereum/consensus",
        "mkdir ethereum/execution",
        "curl https://raw.githubusercontent.com/prysmaticlabs/prysm/master/prysm.sh --output prysm.sh && chmod +x prysm.sh",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


class SetupEthereumNodeAction(HyperbolicAction):
    """Setup Ethereum node environment action."""

    name: str = "setup_ethereum_node_environment"
    description: str = SETUP_ETH_ENV_PROMPT
    args_schema: type[BaseModel] | None = SetupEthereumNodeInput
    func: Callable[..., str] = setup_ethereum_node_environment
