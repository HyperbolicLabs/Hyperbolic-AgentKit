import json
import os
import time
from collections.abc import Callable
from typing import Optional

import requests
from pydantic import BaseModel, Field

from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import get_api_key

DEPLOY_VALIDATOR_PROMPT = """
This tool automates the deployment and management of an Ethereum validator node on the Holesky testnet.

Prerequisites:
- A Hyperbolic compute instance must be rented and SSH accessible (via `rent_compute` and `ssh_connect`).
- This node requires an execution client (e.g., Geth) and a consensus client (e.g., Prysm).
- Validator keys will be generated on the remote machine. IMPORTANT: The generated mnemonic phrase must be securely stored as it's required for key recovery.
- The deposit CLI tool will prompt for confirmation after displaying the mnemonic. The agent must respond appropriately to continue.
- 32 ETH must be deposited into the Holesky deposit contract to activate the validator (placeholder for integration with CDP).
- This action also provides basic monitoring and maintenance commands.

Actions:
- deploy: Install and start execution+consensus clients, generate validator keys, and start the validator client.
- stake: Stake 32 ETH to the Holesky deposit contract (placeholder, requires CDP integration).
- status: Check if the validator is running.
- monitor: Query basic metrics from the validator.
- upgrade: Upgrade clients on the remote machine.
- stop: Stop the validator and execution clients.

Input parameters:
- action: "deploy", "stake", "status", "monitor", "upgrade", "stop"
- execution_client: Which execution client to use (default: "geth")
- consensus_client: Which consensus client to use (default: "prysm")
- eth_deposit_contract_address: The Holesky deposit contract address for staking (required for "stake" action)
- validator_keys_path: Path to validator keys on remote server
- extra_flags: Additional command-line flags for customization
"""


class DeployValidatorNodeInput(BaseModel):
    action: str = Field(
        ..., description="One of: deploy, stake, status, monitor, upgrade, stop"
    )
    execution_client: Optional[str] = Field(
        "geth", description="Execution client to deploy (e.g., geth)"
    )
    consensus_client: Optional[str] = Field(
        "prysm", description="Consensus client to deploy (e.g., prysm)"
    )
    eth_deposit_contract_address: Optional[str] = Field(
        None, description="Holesky deposit contract address (for staking)"
    )
    validator_keys_path: Optional[str] = Field(
        "~/.ethvalidator/keys", description="Path to validator keys"
    )
    extra_flags: Optional[str] = Field(
        "", description="Extra flags to pass to commands"
    )


def run_remote_command(command: str) -> str:
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect first."
    return ssh_manager.execute(command)


def deploy_execution_client(execution_client: str) -> str:
    commands = [
        "sudo apt-get update -y",
        "sudo apt-get install -y software-properties-common",
        "sudo add-apt-repository -y ppa:ethereum/ethereum",
        "sudo apt-get update -y",
        "sudo apt-get install -y ethereum",
        "nohup geth --goerli --syncmode 'snap' --http --http.addr '0.0.0.0' --http.port 8545 --datadir /var/lib/geth &> geth.log &",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


def deploy_consensus_client(consensus_client: str) -> str:
    commands = [
        "sudo apt-get install -y curl",
        "curl https://raw.githubusercontent.com/prysmaticlabs/prysm/master/prysm.sh --output prysm.sh",
        "chmod +x prysm.sh",
        "./prysm.sh beacon-chain --datadir=/var/lib/prysm --accept-terms-of-use --network=holesky &> beacon.log &",
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)

def generate_validator_keys(validator_keys_path: str) -> str:
    """
    Generates validator keys on the remote machine.
    IMPORTANT: The ./deposit command will output a mnemonic phrase that must be saved securely as it's required for key recovery.
    After the mnemonic is displayed, follow the system prompts to complete the key generation process.
    The generated mnemonic phrase must be securely stored as it's required for key recovery.
    Returns:
        str: The output of running the validator key generation commands, including:
            - Installation of dependencies (jq, curl)
            - Creation of validator keys directory
            - Download and extraction of staking deposit CLI
            - Generation of validator keys and mnemonic phrase
            
        Note: The mnemonic phrase output must be securely stored as it's required for key recovery.
    """
    commands = [
        "sudo apt-get install jq curl -y",
        f"mkdir -p {validator_keys_path}",
        "cd $HOME",
        "wget https://github.com/ethereum/staking-deposit-cli/releases/download/v2.8.0/staking_deposit-cli-948d3fc-linux-amd64.tar.gz",
        "tar -xzvf staking_deposit-cli-948d3fc-linux-amd64.tar.gz -C $HOME",
        "cd staking_deposit-cli*amd64",
        f"./deposit --language=english new-mnemonic --num_validators=1 --mnemonic_language=english --chain=holesky --folder={validator_keys_path} --keystore_password=aaaaaaaa"
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)

def extract_and_verify_mnemonic(output: str) -> str:
    """
    Extracts mnemonic from the output and returns the first letters.
    Example: If mnemonic is "abandon better call down", returns "abcd"
    """
    # Find the mnemonic in the output (usually preceded by a specific prompt)
    mnemonic_lines = [line for line in output.split('\n') if "word #" in line.lower()]
    if not mnemonic_lines:
        return ""
    
    # Extract the first letter of each of the first 4 words
    words = []
    for line in mnemonic_lines[:4]:
        # Extract word from format like "word #1: abandon"
        word = line.split(":")[-1].strip()
        if word:
            words.append(word[0])
    
    return "".join(words)

def start_validator_client(validator_keys_path: str) -> str:
    commands = [
        f"./prysm.sh validator --datadir=/var/lib/prysm --accept-terms-of-use --wallet-dir={validator_keys_path} --wallet-password-file={validator_keys_path}/password.txt --network=holesky &> validator.log &"
    ]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


def stake_eth(eth_deposit_contract_address: str, validator_keys_path: str) -> str:
    if not eth_deposit_contract_address:
        return "Error: deposit contract address required for staking."
    return f"Attempting to stake 32 ETH to {eth_deposit_contract_address} (placeholder)"


def get_status() -> str:
    out = run_remote_command("pgrep -a prysm")
    return f"Validator status:\n{out}"


def monitor_node() -> str:
    out = run_remote_command(
        "curl -s http://localhost:8080/metrics || echo 'Metrics endpoint not reachable'"
    )
    return f"Monitoring data:\n{out}"


def upgrade_clients() -> str:
    commands = ["sudo apt-get update -y", "sudo apt-get upgrade -y"]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


def stop_validator() -> str:
    commands = ["pkill -f prysm", "pkill -f geth"]
    output = []
    for cmd in commands:
        output.append(run_remote_command(cmd))
    return "\n".join(output)


def deploy_validator_node(
    action: str,
    execution_client: str = "geth",
    consensus_client: str = "prysm",
    eth_deposit_contract_address: Optional[str] = None,
    validator_keys_path: str = "/home/ubuntu/.ethvalidator/keys",
    extra_flags: str = "",
) -> str:
    if action == "deploy":
        exec_out = deploy_execution_client(execution_client)
        cons_out = deploy_consensus_client(consensus_client)
        key_out = generate_validator_keys(validator_keys_path)
        val_out = start_validator_client(validator_keys_path)
        return f"Deployment complete.\n\nExecution client:\n{exec_out}\n\nConsensus client:\n{cons_out}\n\nKeys:\n{key_out}\n\nValidator:\n{val_out}"

    elif action == "stake":
        return stake_eth(eth_deposit_contract_address, validator_keys_path)

    elif action == "status":
        return get_status()

    elif action == "monitor":
        return monitor_node()

    elif action == "upgrade":
        return upgrade_clients()

    elif action == "stop":
        return stop_validator()

    else:
        return f"Unknown action: {action}. Supported: deploy, stake, status, monitor, upgrade, stop"


class DeployValidatorNodeAction(HyperbolicAction):
    name: str = "deploy_validator_node"
    description: str = DEPLOY_VALIDATOR_PROMPT
    args_schema: type[BaseModel] = DeployValidatorNodeInput
    func: Callable[..., str] = deploy_validator_node
