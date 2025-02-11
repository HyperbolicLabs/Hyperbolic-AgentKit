import requests
import json
from typing import Optional

from collections.abc import Callable

from pydantic import BaseModel, Field

from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.utils import get_api_key

GET_AVAILABLE_GPUS_PROMPT = """
This tool will get all the available GPU machines on the Hyperbolic platform.

It does not take any following inputs

Important notes:
- Authorization key is required for this operation
- The GPU prices are in CENTS per hour
"""


class GetAvailableGpusInput(BaseModel):
  """Input argument schema for getting available GPU machines."""


def get_available_gpus() -> str:
    """
    Returns a formatted string representation of available GPUs from the Hyperbolic API.
    Returns:
        A formatted string describing available GPU options.
    """
    # Get API key from environment
    api_key = get_api_key()

    url = "https://api.hyperbolic.xyz/v1/marketplace"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {"filters": {}}
    response = requests.post(url, headers=headers, json=data)
    data = response.json()
    
    formatted_output = "Available GPU Options:\n\n"
    
    if "instances" in data:
        for instance in data["instances"]:
            # Skip if reserved
            if instance.get("reserved", True):
                continue
                
            cluster_name = instance.get("cluster_name", "Unknown Cluster")
            node_id = instance.get("id", "Unknown Node")
            
            # Get GPU information
            gpus = instance.get("hardware", {}).get("gpus", [])
            if gpus:
                gpu_model = gpus[0].get("model", "Unknown Model")
            else:
                gpu_model = "Unknown Model"
            
            # Get pricing (convert cents to dollars)
            price_amount = instance.get("pricing", {}).get("price", {}).get("amount", 0) / 100
            
            # Get GPU availability
            gpus_total = instance.get("gpus_total", 0)
            gpus_reserved = instance.get("gpus_reserved", 0)
            gpus_available = gpus_total - gpus_reserved
            
            if gpus_available > 0:
                formatted_output += f"Cluster: {cluster_name}\n"
                formatted_output += f"Node ID: {node_id}\n"
                formatted_output += f"GPU Model: {gpu_model}\n"
                formatted_output += f"Available GPUs: {gpus_available}/{gpus_total}\n"
                formatted_output += f"Price: ${price_amount:.2f}/hour per GPU\n"
                formatted_output += "-" * 40 + "\n\n"
    
    if formatted_output == "Available GPU Options:\n\n":
        return "No available GPU instances found."
    
    return formatted_output


class GetAvailableGpusAction(HyperbolicAction):
  """Get available GPUs action."""

  name: str = "get_available_gpus"
  description: str = GET_AVAILABLE_GPUS_PROMPT
  args_schema: type[BaseModel] | None = GetAvailableGpusInput
  func: Callable[..., str] = get_available_gpus
