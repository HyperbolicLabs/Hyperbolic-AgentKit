"""Hyperbolic Toolkit."""

from langchain_core.tools import BaseTool
from langchain_core.tools.base import BaseToolkit

from hyperbolic_agentkit_core.actions import HYPERBOLIC_ACTIONS
from hyperbolic_langchain.tools import HyperbolicTool
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper


class HyperbolicToolkit(BaseToolkit):
    """Hyperbolic Platform Toolkit.

    *Security Note*: This toolkit contains tools that can read and modify
        the state of a service; e.g., by creating, deleting, or updating,
        reading underlying data.

        For example, this toolkit can be used to rent compute, check GPU status,
        and manage compute resources on Hyperbolic supported infrastructure.

        See [Security](https://python.langchain.com/docs/security) for more information.

    Setup:
        See detailed installation instructions here:
        https://python.langchain.com/docs/integrations/tools/hyperbolic/#installation

        You will need to set the following environment
        variables:

        .. code-block:: bash

            export HYPERBOLIC_API_KEY="your-api-key"

    Instantiate:
        .. code-block:: python

            from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
            from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper

            hyperbolic = HyperbolicAgentkitWrapper()
            hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic)

    Tools:
        .. code-block:: python

            tools = hyperbolic_toolkit.get_tools()
            for tool in tools:
                print(tool.name)

        .. code-block:: none

            rent_compute
            get_available_gpus
            terminate_compute
            get_gpu_status
            get_spend_history
            get_current_balance
            ssh_access
            link_wallet_address
    Use within an agent:
        .. code-block:: python

            from langchain_openai import ChatOpenAI
            from langgraph.prebuilt import create_react_agent

            # Select example tool
            tools = [tool for tool in toolkit.get_tools() if tool.name == "get_gpu_status"]
            assert len(tools) == 1

            llm = ChatOpenAI(model="gpt-4o-mini")
            agent_executor = create_react_agent(llm, tools)

            example_query = "Tell me about available GPUs"

            events = agent_executor.stream(
                {"messages": [("user", example_query)]},
                stream_mode="values",
            )
            for event in events:
                event["messages"][-1].pretty_print()

        .. code-block:: none

             ================================[1m Human Message [0m=================================

            Tell me about available GPUs
            ==================================[1m Ai Message [0m==================================
            Tool Calls:
            get_gpu_status (call_iSYJVaM7uchfNHOMJoVPQsOi)
            Call ID: call_iSYJVaM7uchfNHOMJoVPQsOi
            Args:
                no_input: ""
            =================================[1m Tool Message [0m=================================
            Name: get_gpu_status

            ...
            ==================================[1m Ai Message [0m==================================

            Here are the available GPUs and their status...

    Parameters
    ----------
        tools: List[BaseTool]. The tools in the toolkit. Default is an empty list.

    """

    tools: list[BaseTool] = []  # noqa: RUF012

    @classmethod
    def from_hyperbolic_agentkit_wrapper(
            cls, hyperbolic_agentkit_wrapper: HyperbolicAgentkitWrapper) -> "HyperbolicToolkit":
        """Create a HyperbolicToolkit from a HyperbolicAgentkitWrapper.

        Args:
            hyperbolic_agentkit_wrapper: HyperbolicAgentkitWrapper. The Hyperbolic Agentkit wrapper.

        Returns:
            HyperbolicToolkit. The Hyperbolic toolkit.

        """
        actions = HYPERBOLIC_ACTIONS

        tools = [
            HyperbolicTool(
                name=action.name,
                description=action.description,
                hyperbolic_agentkit_wrapper=hyperbolic_agentkit_wrapper,
                args_schema=action.args_schema,
                func=action.func,
            ) for action in actions
        ]

        return cls(tools=tools)  # type: ignore[arg-type]

    def get_tools(self) -> list[BaseTool]:
        """Get the tools in the toolkit."""
        return self.tools
