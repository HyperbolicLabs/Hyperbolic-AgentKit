from collections.abc import Callable
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command

RUN_FULL_ETHEREUM_NODE_PROMPT = """
Responsible for starting the execution client on the remote server. The execution client is one of two components that make up the Ethereum node. The execution client is responsible for processing transactions and executing smart contracts.

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).
- The prysm environment has been set up on the remote server (via `setup_ethereum_node_environment`).
- The Go Ethereum binary has been installed on the remote server (via `install_geth_binary`).
- A valid JWT token has been generated (via `generate_jwt_for_node`).

It does not take any inputs

Important notes:
- Requires an active SSH connection (use ssh_connect first)
- Use 'ssh_status' to check current connection status
- Commands are executed in the connected SSH session
- Returns command output as a string
"""


class StartExecutionClientInput(BaseModel):
    """Input argument schema for running the execution client."""


def run_full_ethereum_node() -> str:
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
    description: str = RUN_FULL_ETHEREUM_NODE_PROMPT
    args_schema: type[BaseModel] | None = None
    func: Callable[..., str] = run_full_ethereum_node
