import logging
import subprocess
from typing import Type

from pydantic import BaseModel

from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction

logger = logging.getLogger(__name__)

SETUP_ETHEREUM_VALIDATOR_PROMPT: str = """
Runs the 'setup.sh' script to provision an Ethereum validator node (Nethermind + Lighthouse).
Expects no user arguments. If the script runs successfully, it returns a success message.
"""


class SetupEthereumValidatorInput(BaseModel):
    """
    Input model for setting up Ethereum validator node.

    Currently no input parameters required.`
    """

    pass


def setup_ethereum_validator() -> str:
    """
    Invokes the 'setup.sh' script to configure Ethereum validator node.

    Returns:
        str: Success message if the script runs without errors.

    Raises:
        subprocess.CalledProcessError: If the script fails to execute properly.
    """
    script_path: str = "scripts/setup.sh"
    logger.info("Starting Ethereum validator node setup via '%s'...", script_path)

    try:
        # Run setup.sh in a blocking manner, checking for errors
        subprocess.run(
            ["/bin/bash", script_path], check=True, capture_output=True, text=True
        )
        logger.info("Ethereum Validator node has been setup successfully.")
        return "Ethereum Validator node has been setup successfully."
    except subprocess.CalledProcessError as error:
        # Log the stderr for debugging
        logger.error("Error running '%s': %s", script_path, error.stderr)
        raise


class SetupEthereumValidatorAction(HyperbolicAction):
    """
    Action class to integrate with the LangChain-based agent.
    Mimics the style of rent_compute.py, get_gpu_status.py, etc.
    """

    name: str = "setup_ethereum_validator"
    description: str = SETUP_ETHEREUM_VALIDATOR_PROMPT
    args_schema: Type[BaseModel] | None = SetupEthereumValidatorInput
    func = setup_ethereum_validator
