from collections.abc import Callable
import time
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager


class ConfigureValidatorInput(BaseModel):
    """Input argument schema for remote shell commands."""

    keystore_path: str = Field(
        ...,
        description="The absolute path to the directory containing the validator keystores. You may need to use `ls` to find this directory. It should have been generated in the $HOME directory, but confirm before using.",
    )

    keystore_password: str = Field(
        ...,
        description="The password used to secure the account used for your validator",
    )


CONFIGURE_VALIDATOR_PROMPT = """
This action is responsible for importing your keystores into your validator and starting the validator client. When this tool is called import your validator keystores and start the validator client. 

Below is the command to import your keystores and start the validator client:

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).
- The prysm environment has been set up on the remote server (via `setup_ethereum_node_environment`).
- The Go Ethereum binary has been installed on the remote server (via `install_geth_binary`).
- A valid JWT token has been generated (via `generate_jwt_for_node`).
- A functioning execution client has been started (via `run_full_ethereum_node`).
- Private keystore have been generated, are accessible, are backed up, and are accessible (via `setup_depositor`).

Input parameters:
- keystore_path: The absolute path to the directory containing the validator keystores
- keystore_password: The password that will be used secure the account used for your validator

Important notes:
- Requires an active SSH connection (use ssh_connect first)
- Use 'ssh_status' to check current connection status
- Commands are executed in the connected SSH session
- Returns command output as a string
"""


def configure_validator(keystore_path: str, keystore_password: str) -> str:
    """
    Import the validator keystores and start the validator client.

    Args:
        command: The shell command to execute

    Returns:
        str: Command output or error message
    """
    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect first."

    final_output = ""

    try:
        # Start the deposit command
        output, error = ssh_manager.interactive_command(
            command=f"$HOME/ethereum/consensus/prysm.sh validator accounts import --keys-dir={keystore_path} --holesky"
        )
        final_output += output
        output, error = ssh_manager.interactive_command(command="")
        final_output += output

        if "Enter a wallet directory" in output:
            # You’ll be prompted to specify a wallet directory twice. Provide the path to your consensus folder for both prompts. You should see Imported accounts [...] view all of them by running accounts list when your account has been successfully imported into Prysm.
            output, error = ssh_manager.interactive_command(
                command="$HOME/ethereum/consensus"
            )
            final_output += output

        if "New wallet password" in output:

            output, error = ssh_manager.interactive_command(command=keystore_password)
            final_output += output

        if "Confirm password" in output:
            output, error = ssh_manager.interactive_command(command=keystore_password)
            final_output += output

        if "Enter the password for your imported accounts" in output:
            output, error = ssh_manager.interactive_command(command=keystore_password)
            final_output += output
            # Wait for import to complete
            time.sleep(10)
            # check that the import was successful
            output, error = ssh_manager.interactive_command(command="")
            final_output += output

        if "Imported accounts" in output:
            final_output += "Imported accounts successfully"

    finally:
        # Always close the interactive session when done
        ssh_manager.close_interactive_session()

    return final_output


class ConfigureValidatorAction(HyperbolicAction):
    """Run steps necessary to start a full ethereum node"""

    name: str = "configure_validator"
    description: str = CONFIGURE_VALIDATOR_PROMPT
    args_schema: type[BaseModel] | None = ConfigureValidatorInput
    func: Callable[..., str] = configure_validator
