from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command


class SetupDepositorInput(BaseModel):
    """Input argument schema for setting up Depositor CLI."""


SETUP_DEPOSITOR_PROMPT = """
IMPORTANT: ANY OPERATION INVOLVING GENERATION OF PRIVATE KEYS SHOULD BE INVOLVE APPROVAL BY THE USER. before performing this action, ask for permission from the user. This action involves sensitive operations and if done incorrectly can lead to loss of funds. 

This action is responsible for downloading and installing the `deposit` cli. The deposit cli is responsible for generating a public / private key pare responsible for securing your validator as well as the deposit data necessary for `deposit_eth_action` tool. 

Once the deposit cli is installed, you can use it to generate a deposit data file which is used to deposit 32 ETH into the Ethereum 2.0 deposit contract. This is the command for reference: ./deposit new-mnemonic --num_validators=1 --mnemonic_language=english --chain=holesky

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


def setup_depositor() -> str:
    """
    Setup the deposit cli on the remote server.

    Returns:
        str: Command output or error message
    """

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    commands = [
        # download deposit cli
        "wget https://github.com/ethereum/staking-deposit-cli/releases/download/v2.7.0/staking_deposit-cli-948d3fc-linux-amd64.tar.gz",
        # verify checksum
        "sha256sum staking_deposit-cli-948d3fc-linux-amd64.tar.gz",
        # extract deposit cli
        "tar -xzf staking_deposit-cli-948d3fc-linux-amd64.tar.gz",
        "cd staking_deposit-cli-948d3fc-linux-amd64",
        "chmod +x deposit",
        "deposit --help",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


class SetupDepositorAction(HyperbolicAction):
    """Run steps necesarry to start a full ethereum node"""

    name: str = "setup_depositor"
    description: str = SETUP_DEPOSITOR_PROMPT
    args_schema: type[BaseModel] | None = SetupDepositorInput
    func: Callable[..., str] = setup_depositor
