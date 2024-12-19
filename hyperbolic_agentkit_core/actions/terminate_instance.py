import requests
import json
from typing import Optional

from collections.abc import Callable

from pydantic import BaseModel, Field

from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.utils import get_api_key

TERMINATE_INSTANCE_PROMPT = """
Terminates a marketplace instance using the Hyperbolic API.

This function sends a termination request to the API for a specified cluster.
It includes comprehensive error handling and returns a formatted string response
to make it easier to understand the outcome of the termination request.

Args:
    instance_name (str): Name of the instance to terminate. This should be the
        exact name used when creating the instance.

Returns:
    str: A formatted string representation of the API response, typically
        containing information about the termination status.
    
Raises:
    ValueError: If the required parameters (instance_name) are
        missing or invalid.
    requests.exceptions.RequestException: If there's any issue with the API
        request, including network errors, authentication failures, or invalid
        responses.
"""


class InstanceTerminationInput(BaseModel):
    """Input argument schema for instance termination action."""

    instance_name: str = Field(
        ..., description="The instance name that the user wants terminate")

def terminate_instance(instance_name: str) -> str:
    """
   Terminates a marketplace instance using the Hyperbolic API and returns the response as a formatted string.

   Args:
       instance_name (str): Name of the instance to terminate

   Returns:
       str: A formatted string representation of the API response

   Raises:
       requests.exceptions.RequestException: If the API request fails
       ValueError: If required parameters are invalid
   """
    # Input validation
    if not instance_name:
        raise ValueError("instance_name is required")

    # Get API key from environment
    api_key = get_api_key()

    # Prepare the request
    endpoint = f"https://api.hyperbolic.xyz/v1/marketplace/instances/terminate"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "id": instance_name,
    }

    try:
        # Make the request
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()

        # Get the response content
        response_data = response.json()

        # Convert the response to a formatted string
        # We use json.dumps with indent=2 for pretty printing
        formatted_response = json.dumps(response_data, indent=2)

        return formatted_response

    except requests.exceptions.RequestException as e:
        # For HTTP errors, we want to include the status code and response content if available
        error_message = f"Error renting compute from Hyperbolic marketplace: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                # Try to get JSON error message if available
                error_content = e.response.json()
                error_message += f"\nResponse: {json.dumps(error_content, indent=2)}"
            except json.JSONDecodeError:
                # If response isn't JSON, include the raw text
                error_message += f"\nResponse: {e.response.text}"

        raise requests.exceptions.RequestException(error_message)


class TerminateInstanceAction(HyperbolicAction):
    """Terminate instance action."""

    name: str = "terminate_instance"
    description: str = TERMINATE_INSTANCE_PROMPT
    args_schema: type[BaseModel] | None = InstanceTerminationInput
    func: Callable[..., str] = terminate_instance
