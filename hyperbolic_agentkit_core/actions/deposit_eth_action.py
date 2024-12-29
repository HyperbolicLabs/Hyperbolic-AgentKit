from collections.abc import Callable
import os
from typing import Optional
from pydantic import BaseModel, Field
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.ssh_manager import ssh_manager
from hyperbolic_agentkit_core.actions.utils import run_remote_command

from web3 import Web3
import json


class ValidatorDeposit:
    # Holesky Deposit Contract Address
    DEPOSIT_CONTRACT_ADDRESS = "0x4242424242424242424242424242424242424242"

    # Amount required for deposit (32 ETH in Wei)
    DEPOSIT_AMOUNT = Web3.to_wei(32, "ether")

    # Deposit function ABI
    DEPOSIT_ABI = [
        {
            "name": "deposit",
            "type": "function",
            "stateMutability": "payable",
            "inputs": [
                {"name": "pubkey", "type": "bytes"},
                {"name": "withdrawal_credentials", "type": "bytes"},
                {"name": "signature", "type": "bytes"},
                {"name": "deposit_data_root", "type": "bytes32"},
            ],
            "outputs": [],
        }
    ]

    def __init__(self, rpc_url: str):
        """Initialize with RPC endpoint."""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Initialize contract with inline ABI
        self.deposit_contract = self.w3.eth.contract(
            address=self.DEPOSIT_CONTRACT_ADDRESS, abi=self.DEPOSIT_ABI
        )

    def read_remote_deposit_data(self, deposit_data_path: str) -> dict:
        """Read and validate deposit data file from remote SSH connection."""
        if not ssh_manager.is_connected:
            raise ValueError("SSH connection is not active")

        # Read the file content using ssh_manager
        cat_command = f"cat {deposit_data_path}"
        deposit_data_content = run_remote_command(cat_command)

        try:
            deposit_data = json.loads(deposit_data_content)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in deposit data file")

        if not isinstance(deposit_data, list) or len(deposit_data) == 0:
            raise ValueError("Invalid deposit data format")

        return deposit_data[0]  # Return first validator's data

    def submit_deposit(
        self,
        deposit_data_path: str,
        from_address: str,
        private_key: str,
    ) -> str:
        """
        Submit a validator deposit transaction.

        Args:
            deposit_data_path: Path to the deposit data file on remote server
            from_address: Address funding the deposit
            private_key: Private key for the funding address

        Returns:
            str: Transaction hash
        """
        # Check balance
        balance = self.w3.eth.get_balance(from_address)
        if balance < self.DEPOSIT_AMOUNT:
            raise ValueError(
                f"Insufficient balance. Need 32 ETH, have {Web3.from_wei(balance, 'ether')} ETH"
            )

        # Read deposit data from remote server
        deposit_data = self.read_remote_deposit_data(deposit_data_path)

        # Extract deposit input data
        pubkey = bytes.fromhex(deposit_data["pubkey"].replace("0x", ""))
        withdrawal_credentials = bytes.fromhex(
            deposit_data["withdrawal_credentials"].replace("0x", "")
        )
        signature = bytes.fromhex(deposit_data["signature"].replace("0x", ""))
        deposit_data_root = bytes.fromhex(
            deposit_data["deposit_data_root"].replace("0x", "")
        )

        # Get nonce
        nonce = self.w3.eth.get_transaction_count(from_address)

        # Prepare transaction
        deposit_tx = self.deposit_contract.functions.deposit(
            pubkey, withdrawal_credentials, signature, deposit_data_root
        ).build_transaction(
            {
                "from": from_address,
                "value": self.DEPOSIT_AMOUNT,
                "gas": 500000,  # Gas limit
                "gasPrice": self.w3.eth.gas_price,
                "nonce": nonce,
            }
        )

        # Sign transaction
        signed_txn = self.w3.eth.account.sign_transaction(deposit_tx, private_key)

        # Send transaction
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        # Wait for transaction receipt
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if tx_receipt["status"] != 1:
            raise Exception("Transaction failed")

        return tx_hash.hex()


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
        description="The path to the deposit data file that will be used to deposit 32 ETH into the Ethereum 2.0 deposit contract. This file was generated using the `setup_depositor` action. This is a sample value: /home/validator_keys/deposit_data-1735413397.json",
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


def get_rpc_url() -> str:
    if os.getenv("RPC_URL"):
        return os.getenv("RPC_URL")
    raise ValueError("RPC_URL environment variable is not set")


def deposit_eth(sender: str, private_key: str, deposit_data_path: str) -> str:
    """
    Start the Go Ethereum binary which will be used as the execution client on the remote server.

    Returns:
        str: Command output or error message
    """

    # Verify SSH is connected before executing
    if not ssh_manager.is_connected:
        return "Error: No active SSH connection. Please connect to a remote server first using ssh_connect."

    rpc_url = get_rpc_url()
    depositor = ValidatorDeposit(rpc_url)

    try:
        tx_hash = depositor.submit_deposit(
            deposit_data_path=deposit_data_path,
            from_address=sender,
            private_key=private_key,
        )
        output = f"Deposit transaction submitted: {tx_hash}"

    except Exception as e:
        output = f"Error submitting deposit: {str(e)}"

    return output


class DepositETHAction(HyperbolicAction):
    """Run steps necessary to deposit 32 ETH into the Ethereum 2.0 deposit contract."""

    name: str = "deposit_eth"
    description: str = DEPOSIT_ETH_PROMPT
    args_schema: type[BaseModel] | None = DepositEthInput
    func: Callable[..., str] = deposit_eth
