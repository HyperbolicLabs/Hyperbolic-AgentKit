"""Tool allows agents to interact with the hyperbolic-sdk library.

To use this tool, you must first set as environment variables:
    HYPERBOLIC_API_KEY

"""

from collections.abc import Callable
from typing import Any
import threading
import functools

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from hyperbolic_langchain.utils.hyperbolic_agentkit_wrapper import HyperbolicAgentkitWrapper


class CommandTimeout(Exception):
    """Exception raised when a command execution times out."""
    pass


def timeout_decorator(timeout_seconds=30):
    """Decorator to add timeout to functions."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            error = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    error[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout_seconds)
            
            if thread.is_alive():
                raise CommandTimeout(f"Command timed out after {timeout_seconds} seconds")
            
            if error[0] is not None:
                raise error[0]
                
            return result[0]
        return wrapper
    return decorator


class HyperbolicTool(BaseTool):  # type: ignore[override]
    """Tool for interacting with the Hyperbolic SDK."""

    hyperbolic_agentkit_wrapper: HyperbolicAgentkitWrapper
    name: str = ""
    description: str = ""
    args_schema: type[BaseModel] | None = None
    func: Callable[..., str]

    @timeout_decorator(timeout_seconds=1000)
    def _run(
        self,
        instructions: str | None = "",
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> str:
        """Use the Hyperbolic SDK to run an operation."""
        if not instructions or instructions == "{}":
            # Catch other forms of empty input that GPT-4 likes to send.
            instructions = ""
        if self.args_schema is not None:
            validated_input_data = self.args_schema(**kwargs)
            parsed_input_args = validated_input_data.model_dump()
        else:
            parsed_input_args = {"instructions": instructions}
        return self.hyperbolic_agentkit_wrapper.run_action(self.func, **parsed_input_args)
