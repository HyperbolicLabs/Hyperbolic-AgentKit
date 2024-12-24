from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command


class DepositEthInput(BaseModel):
    """Input argument schema for setting up Ethereum node environment."""

    sender: str = Field(
        default="",
        description="The public ethereum address that that will be used to sign the deposit transaction",
    )

    private_key: str = Field(
        default="",
        description="The ethereum private key that will be used to sign the deposit transaction",
    )

    deposit_data_path: str = Field(
        default="",
        description="The path to the deposit data file that will be used to deposit 32 ETH into the Ethereum 2.0 deposit contract.",
    )


DEPOSIT_ETH_PROMPT = """
This action is responsible for depositing 32 ETH into the Ethereum 2.0 deposit contract. It uses the ethereal cli to facilitate and sign the ethereum transaction. 

IMPORTANT:
- The ethereum address and corresponding deposit data must be already generated using the deposit cli.
- The ethereum address must have at least 32 ETH to deposit.

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).
- The prysm environment has been set up on the remote server (via `setup_ethereum_node_environment`).
- The Go Ethereum binary has been installed on the remote server (via `install_geth_binary`).
- A valid JWT token has been generated (via `generate_jwt_for_node`).
- You must have access to and have already generated a deposit public / private key pair that was generated using the deposit cli.
- You must have access to and have already generated a deposit data file that was generated using the deposit cli.

It takes the following inputs:
- sender: The ethereum address that will be used to sign the deposit transaction
- private_key: The ethereum private key that will be used to sign the deposit transaction
- deposit_data_path: The path to the deposit data file that will be used to deposit 32 ETH into the Ethereum 2.0 deposit contract.

Important notes:
- Requires an active SSH connection (use ssh_connect first)
- Use 'ssh_status' to check current connection status
- Commands are executed in the connected SSH session
- Returns command output as a string
"""


def deposit_eth(sender: str, private_key: str, deposit_data_path: str) -> str:
    """
    Start the Go Ethereum binary which will be used as the execution client on the remote server.

    Returns:
        str: Command output or error message
    """

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    commands = [
        "sudo apt install golang-go",
        "echo 'export PATH=$PATH:$HOME/go/bin' >> $HOME/.profile",
        "source $HOME/.profile",
        "GO111MODULE=on go install github.com/wealdtech/ethereal@latest",
        f"""ethereal beacon deposit \
        --network=goerli \
        --data="$(cat {deposit_data_path})" \
        --privatekey={private_key} \
        --from={sender} \
        --value="32 Ether" """,
    ]

    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


class DepositETHAction(HyperbolicAction):
    """Run steps necessary to deposit 32 ETH into the Ethereum 2.0 deposit contract."""

    name: str = "deposit_eth"
    description: str = DEPOSIT_ETH_PROMPT
    args_schema: type[BaseModel] | None = DepositEthInput
    func: Callable[..., str] = deposit_eth
