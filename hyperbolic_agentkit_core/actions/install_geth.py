from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command


class SetupEthereumNodeInput(BaseModel):
    """Input argument schema for setting up Ethereum node environment."""


INSTALL_GETH_PROMPT = """
Installs the Go Ethereum binary on the remote server.

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).
- The prysm environment has been set up on the remote server (via `setup_ethereum_node_environment`).

It does not take any inputs

Important notes:
- Requires an active SSH connection (use ssh_connect first)
- Use 'ssh_status' to check current connection status
- Commands are executed in the connected SSH session
- Returns command output as a string
"""


def install_geth_binary() -> str:
    """
    Install the Go Ethereum binary on a remote server.

    Returns:
        str: JSON string containing installation results

    Raises:
        SSHConnectionError: If SSH connection is not active
    """

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    commands = [
        "sudo add-apt-repository -y ppa:ethereum/ethereum",
        "sudo apt-get update -y",
        "sudo apt-get install ethereum -y",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


class InstallGETHAction(HyperbolicAction):
    """Generate JWT token action."""

    name: str = "install_geth_binary"
    description: str = INSTALL_GETH_PROMPT
    args_schema: type[BaseModel] | None = SetupEthereumNodeInput
    func: Callable[..., str] = install_geth_binary
