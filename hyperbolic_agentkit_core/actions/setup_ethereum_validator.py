"""Setup Ethereum Validator action module."""

import base64
from typing import Callable

from pydantic import BaseModel

from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.remote_shell import execute_remote_command

SETUP_VALIDATOR_PROMPT = """Setup an Ethereum validator node by running the setup script. 
This will install and configure Nethermind and Lighthouse clients."""


class SetupValidatorInput(BaseModel):
    """Input argument schema for setting up Ethereum validator."""
    pass


def setup_ethereum_validator() -> str:
    """
    Runs the setup.sh script to configure an Ethereum validator node.
    
    Returns:
        str: A message indicating success or failure of the setup process.
    """
    try:
        # First, read the setup.sh script content
        with open("/Users/sagar/Projects/Personal/node/Hyperbolic-AgentKit/scripts/setup.sh", "r") as f:
            script_content = f.read()
        
        # Encode script content to base64 to handle special characters safely
        script_b64 = base64.b64encode(script_content.encode()).decode()
        
        # Create a temporary directory on remote server
        execute_remote_command("mkdir -p ~/ethereum_setup")
        
        # Write the script to the remote server, decoding from base64
        execute_remote_command(f'echo "{script_b64}" | base64 -d > ~/ethereum_setup/setup.sh')
        
        # Make the script executable
        execute_remote_command("chmod +x ~/ethereum_setup/setup.sh")
        
        # Run the setup script
        result = execute_remote_command("cd ~/ethereum_setup && ./setup.sh")
        
        # Check for any error messages in the output
        if "ERROR" in result:
            return f"Setup failed: {result}"
        
        # Verify services are running using the script's log command
        status = execute_remote_command("cd ~/ethereum_setup && ./setup.sh logs")
        
        # Check if all required services are running
        services = ["nethermind", "lighthouse-beacon", "lighthouse-validator"]
        for service in services:
            service_status = execute_remote_command(f"sudo supervisorctl status {service}")
            if "RUNNING" not in service_status:
                return f"Setup completed but {service} is not running properly. Please check logs with './setup.sh logs'"
        
        return "Ethereum Validator node has been setup successfully. All services are running."
            
    except Exception as e:
        return f"Unexpected error during setup: {str(e)}"


class SetupValidatorAction(HyperbolicAction):
    """Setup Ethereum validator action."""

    name: str = "setup_ethereum_validator"
    description: str = SETUP_VALIDATOR_PROMPT
    args_schema: type[BaseModel] | None = SetupValidatorInput
    func: Callable[..., str] = setup_ethereum_validator
