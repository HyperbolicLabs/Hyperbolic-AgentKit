from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command


class SetupEthereumNodeInput(BaseModel):
    """Input argument schema for setting up Ethereum node environment."""

    instructions: Optional[str] = Field(
        default="", description="Optional instructions for the action"
    )


MONITOR_VALIDATOR_PROMPT = """
This tool is responsible for monitoring the Ethereum validator node on the Holesky testnet.
It can run any shell command on the remote server via SSH.
It should be used to check the status of the execution and consensus clients, as well as the validator itself.

Below are common debugging techniques that can be used to check the health of the node:
- You can check your Geth execution node's sync status by running geth attach (IPC) or geth attach http://localhost:8545 (HTTP) from a separate terminal. Then type eth.syncing. A sync status of false indicates that your node is fully synced.

If not sure what command to run use the Go Ethereum help command (geth --help) or the Prysm help command (prysm.sh --help).

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).
- The prysm environment has been set up on the remote server (via `setup_ethereum_node_environment`).
- The Go Ethereum binary has been installed on the remote server (via `install_geth_binary`).

It does not take any inputs

Important notes:
- Requires an active SSH connection (use ssh_connect first)
- Use 'ssh_status' to check current connection status
- Commands are executed in the connected SSH session
- Returns command output as a string

Input parameters:
- command: The shell command to execute on the remote server

"""


class StartExecutionClientInput(BaseModel):
    """Input argument schema for running the execution client."""


class BaseHyperbolicInput(BaseModel):
    """Base input schema for all Hyperbolic actions."""

    instructions: Optional[str] = Field(
        default="", description="Optional instructions for the action"
    )


def run_full_ethereum_node(instructions: Optional[str] = "") -> str:
    """
    Start the Go Ethereum binary which will be used as the execution client on the remote server.

    Returns:
        str: Command output or error message
    """

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    commands = [
        "cd ethereum/execution",
        "geth --holesky --http --http.api eth,net,engine,admin --authrpc.jwtsecret=../jwt.hex",
        "cd ../",
        "./prysm.sh beacon-chain --execution-endpoint=http://localhost:8551 --holesky --jwt-secret=./jwt.hex  --checkpoint-sync-url=https://holesky.beaconstate.info --genesis-beacon-api-url=https://holesky.beaconstate.info",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


class RunFullEthereumNodeAction(HyperbolicAction):
    """Run steps necesarry to start a full ethereum node"""

    name: str = "run_full_ethereum_node"
    description: str = MONITOR_VALIDATOR_PROMPT
    args_schema: type[BaseModel] | None = SetupEthereumNodeInput
    func: Callable[..., str] = run_full_ethereum_node
