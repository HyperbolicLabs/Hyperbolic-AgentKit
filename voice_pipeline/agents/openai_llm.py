from typing import AsyncGenerator
from openai import AsyncOpenAI

from ..core.llm import LLM, LLMCapabilities, ChatContext, Message
from ..types import EventTypes

class OpenAILLMCapabilities(LLMCapabilities):
    """OpenAI LLM capabilities."""
    def __init__(self):
        super().__init__(
            streaming=True,
            function_calling=True,
            system_messages=True,
            message_history=True
        )

class OpenAILLM(LLM):
    """Language Model using OpenAI's API."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini-2024-07-18"):
        super().__init__()
        self._capabilities = OpenAILLMCapabilities()
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        
    @property
    def capabilities(self) -> LLMCapabilities:
        return self._capabilities
        
    async def chat(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """Generate chat responses."""
        try:
            await self.emit("agent_started_speaking")
            
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "name": msg.name,
                    "function_call": msg.function_call
                }
                for msg in context.messages
            ]
            
            response = await self._client.chat.completions.create(
                messages=messages,
                model=self._model,
                stream=True,
                temperature=0.7
            )
            
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"Error in chat: {e}")
            raise
            
        finally:
            await self.emit("agent_stopped_speaking")
            
    async def reset(self) -> None:
        """Reset the LLM state."""
        await super().reset()
        
    async def aclose(self) -> None:
        """Clean up resources."""
        pass 