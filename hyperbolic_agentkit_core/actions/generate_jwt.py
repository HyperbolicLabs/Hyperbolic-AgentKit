from collections.abc import Callable
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command

GENERATE_JWT_PROMPT = """
Generates a JWT token and places it in the correct location. The JWT is used to authenticate between the ethereum execution and consensus nodes.

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


class SetupEthNodeEnvironmentInput(BaseModel):
    """Input argument schema for setting up Ethereum node environment."""


def generate_jwt() -> str:
    """
    Execute a command on the remote server.

    Returns:
        str: Command output or error message
    """

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    commands = [
        "./prysm.sh beacon-chain generate-auth-secret",
        "mv jwt.hex ethereum/",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


class GenerateJWTAction(HyperbolicAction):
    """Generate JWT token action."""

    name: str = "generate_jwt_for_node"
    description: str = GENERATE_JWT_PROMPT
    args_schema: type[BaseModel] | None = None
    func: Callable[..., str] = generate_jwt
