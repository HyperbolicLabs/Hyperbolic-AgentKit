from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command

import pexpect
from collections.abc import Callable
from typing import Optional
from pydantic import BaseModel, Field


class SetupDepositorInput(BaseModel):
    """Input argument schema for setting up Depositor CLI."""

    keystore_password: str = Field(
        ..., description="Password to secure the validator keystore"
    )


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


def extract_mnemonic(output: str) -> str:
    """
    Extracts the mnemonic phrase from the deposit CLI output.

    This function handles the specific format of the deposit CLI output, which includes:
    1. ANSI escape sequences for terminal control
    2. The mnemonic phrase between header and footer text
    3. Various whitespace and newline characters

    Args:
        output: Raw output string from the deposit CLI containing the mnemonic

    Returns:
        str: The extracted mnemonic phrase, or empty string if not found
    """
    # Split the output into lines and strip whitespace
    lines = output.split("\n")

    # Look for lines that contain actual words (not control sequences or prompts)
    for line in lines:
        # Clean the line of special characters and extra whitespace
        cleaned_line = line.strip()

        # Skip empty lines or lines containing prompt text
        if (
            not cleaned_line
            or "This is your mnemonic" in cleaned_line
            or "Press any key" in cleaned_line
        ):
            continue

        # Check if this line looks like a mnemonic (series of words)
        words = cleaned_line.split()

        # A valid mnemonic typically has 24 words
        if len(words) == 24:
            return cleaned_line

    return ""  # Return empty string if no mnemonic found


def extract_validator_keys_path(output: str) -> str:
    """
    Extracts the validator keys directory path from the deposit CLI output.

    This function searches for the specific output line that contains the validator
    keys path. The CLI outputs this information in a consistent format after
    successful key generation.

    Args:
        output: The complete output string from the deposit CLI

    Returns:
        str: The extracted validator keys path, or empty string if not found

    Example:
        >>> output = "Creating your keys.\nSuccess!\nYour keys can be found at: /validator_keys\nPress any key."
        >>> extract_validator_keys_path(output)
        '/home/validator_keys'
    """
    # Split the output into lines to process each separately
    lines = output.split("\n")

    # Look for the line containing the path information
    for line in lines:
        # Clean the line and check for the specific prefix
        line = line.strip()
        if "Your keys can be found at:" in line:
            # Extract the path portion after the prefix
            path = line.split("Your keys can be found at:", 1)[1].strip()
            return path

    return ""  # Return empty string if no path found


def setup_depositor_interactive(keystore_password: str) -> str:
    """
    Setup the deposit cli with interactive command handling.
    """
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect first."

    commands = [
        # download deposit cli
        "wget https://github.com/ethereum/staking-deposit-cli/releases/download/v2.8.0/staking_deposit-cli-948d3fc-linux-amd64.tar.gz",
        # verify checksum
        "sha256sum staking_deposit-cli-948d3fc-linux-amd64.tar.gz",
        # extract deposit cli
        "tar -xzf staking_deposit-cli-948d3fc-linux-amd64.tar.gz",
        "cd staking_deposit-cli-948d3fc-linux-amd64 && chmod +x deposit",
        "deposit --help",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))

    try:
        final_output = ""
        # Start the deposit command
        output, error = ssh_manager.interactive_command(
            command=f"./staking_deposit-cli-948d3fc-linux-amd64/deposit --language=English new-mnemonic --num_validators=1 --mnemonic_language=english --chain=holesky --keystore_password={keystore_password}"
        )
        output, error = ssh_manager.interactive_command(command="")
        if error:
            return f"Error starting deposit CLI: {error}"
        print(output)

        # Look for password confirmation prompt
        if "Repeat your keystore password for confirmation:" in output:
            output, error = ssh_manager.interactive_command(send_str=keystore_password)
            if error:
                return f"Error confirming password: {error}"
            print(output)

        # Capture and process mnemonic
        if "This is your mnemonic (seed phrase)" in output:
            # Extract mnemonic from output
            mnemonic = extract_mnemonic(output)  # You'd need to implement this

            final_output += f"Your mnemonic is: {mnemonic}\n"

            # Press any key to continue
            output, error = ssh_manager.interactive_command(send_str="\n")
            if error:
                return f"Error after mnemonic display: {error}"
            print(output)

        # Handle mnemonic confirmation
        if "Please type your mnemonic (separated by spaces)" in output:
            output, error = ssh_manager.interactive_command(send_str=mnemonic)
            # output, error = ssh_manager.interactive_command(send_str="")

            if error:
                return f"Error confirming mnemonic: {error}"
            print(output)

        if "Your keys can be found at:" in output:
            key_path = extract_validator_keys_path(output)
            final_output += f"Deposit CLI setup completed successfully. Deployer keys are saved at: {key_path}"
            return final_output

    finally:
        # Always close the interactive session when done
        ssh_manager.close_interactive_session()
        return final_output


class SetupDepositorAction(HyperbolicAction):
    name: str = "setup_depositor"
    description: str = SETUP_DEPOSITOR_PROMPT
    args_schema: type[BaseModel] | None = SetupDepositorInput
    func: Callable[..., str] = setup_depositor_interactive
