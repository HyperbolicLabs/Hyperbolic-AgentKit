from typing import Optional, Any, Dict, List
import os
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.messages import AIMessage
from mira_network.sync_client import MiraSyncClient
from mira_network.models import AiRequest
from pydantic import Field, model_validator
import json

class MiraLLM(BaseChatModel):
    """LangChain compatible wrapper for Mira's sync client."""
    
    base_url: str = Field(default="https://api.mira.network")
    api_key: Optional[str] = Field(default=None)
    model: str = Field(default="claude-3.5-sonnet")
    temperature: float = Field(default=0.7)
    client: MiraSyncClient = Field(default=None)
    
    @model_validator(mode='after')
    def initialize_client(self) -> 'MiraLLM':
        """Initialize the Mira client after all fields are set."""
        self.client = MiraSyncClient(base_url=self.base_url, api_key=self.api_key)
        return self
    
    def invoke(self, messages, **kwargs):
        """Invoke the chat model with messages."""
        formatted_messages = []
        for message in messages:
            # Map message types to roles
            if message.type == "human":
                role = "user"
            elif message.type == "ai":
                role = "assistant"
            elif message.type == "system":
                role = "system"
            else:
                role = "user"  # default to user for unknown types
                
            formatted_messages.append({
                "role": role,
                "content": message.content
            })
        
        request = AiRequest(
            model=self.model,
            messages=formatted_messages,
            temperature=self.temperature,
            stream=False,
            **kwargs
        )
        
        try:
            response = self.client.generate(request)
            
            # Handle response format where data is nested
            if isinstance(response, dict) and "data" in response:
                data = response["data"]
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                
            raise ValueError(f"Unexpected response format from Mira API: {response}")
        except Exception as e:
            raise

    def _generate(self, messages=None, stop=None, run_manager=None, **kwargs) -> ChatResult:
        """Required abstract method implementation for BaseChatModel."""
        response = self.invoke(messages, **kwargs)
        message = AIMessage(content=response)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        """Return identifier of the LLM."""
        return "mira"

def get_llm(
    model: str = "claude-3.5-sonnet",  # Only used for Anthropic if Mira is not available, also other models available for mira are "gpt-4o", "deepseek-r1", "llama-3.3-70b-instruct"
    temperature: float = 0.7,
    base_url: str = "https://api.mira.network",
    api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> BaseChatModel:
    """Get the appropriate LLM based on environment configuration.
    
    Args:
        model: Model name to use (only used when falling back to Anthropic, ignored for Mira)
        temperature: Temperature for generation
        base_url: Base URL for Mira API (only used if Mira is selected)
        api_key: Optional API key for Mira
        anthropic_api_key: Optional API key for Anthropic
    
    Returns:
        A LangChain compatible chat model
        
    Raises:
        ValueError: If neither Mira API key nor Anthropic API key is available
        
    Note:
        The model parameter is only used when falling back to Anthropic.
        When using Mira, the model is fixed to "claude-3.5-sonnet" as that's what Mira provides.
    """
    # Check for Mira API key in environment or passed directly
    mira_api_key = api_key or os.environ.get("MIRA_API_KEY")
    anthropic_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    if not mira_api_key and not anthropic_key:
        raise ValueError(
            "No API keys found. Please provide either a Mira API key (via MIRA_API_KEY "
            "environment variable or api_key parameter) or an Anthropic API key (via "
            "ANTHROPIC_API_KEY environment variable or anthropic_api_key parameter)"
        )
    
    if mira_api_key:
        # Use Mira if API key is available - model is fixed to claude-3.5-sonnet
        return MiraLLM(
            base_url=base_url,
            api_key=mira_api_key,
            model="claude-3.5-sonnet",  # Fixed for Mira, other models available for mira are "gpt-4o", "deepseek-r1", "llama-3.3-70b-instruct"
            temperature=temperature
        )
    else:
        # Use ChatAnthropic with specified model
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            anthropic_api_key=anthropic_key
        ) 