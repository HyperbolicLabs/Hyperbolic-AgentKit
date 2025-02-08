from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Protocol
from ..types import EventTypes
from .event_emitter import EventEmitter

@dataclass
class Message:
    """A chat message."""
    role: str
    content: str
    name: str | None = None
    function_call: Dict | None = None

@dataclass
class FunctionCall:
    """A function call from the LLM."""
    name: str
    arguments: Dict
    
@dataclass
class ChatContext:
    """Context for a chat conversation."""
    messages: List[Message]
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None

@dataclass
class LLMCapabilities:
    """LLM capabilities configuration."""
    streaming: bool = False
    function_calling: bool = False
    system_messages: bool = False
    message_history: bool = False

class LLM(EventEmitter[EventTypes]):
    """Base class for Language Model interactions."""
    
    def __init__(self):
        super().__init__()
        self._is_processing = False
        
    @property
    def capabilities(self) -> LLMCapabilities:
        """Get the LLM capabilities."""
        raise NotImplementedError
        
    @property
    def is_processing(self) -> bool:
        """Whether the LLM is currently processing a request."""
        return self._is_processing
        
    async def chat(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Generate a chat response.
        
        Args:
            context: The chat context
            
        Yields:
            Generated text chunks
        """
        raise NotImplementedError
        
    async def reset(self) -> None:
        """Reset the LLM state."""
        self._is_processing = False
        
    async def aclose(self) -> None:
        """Clean up resources."""
        pass 