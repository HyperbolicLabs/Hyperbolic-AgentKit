from typing import List
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from .browser_tool import BrowserTool

class BrowserToolkit:
    """Toolkit for browser automation capabilities."""

    def __init__(self, llm: ChatOpenAI = None):
        """Initialize the browser toolkit."""
        self.llm = llm

    def get_tools(self) -> List[BaseTool]:
        """Get the list of tools in the toolkit."""
        return [BrowserTool(llm=self.llm)]

    @classmethod
    def from_llm(cls, llm: ChatOpenAI = None) -> "BrowserToolkit":
        """Create a BrowserToolkit from an LLM."""
        return cls(llm=llm) 