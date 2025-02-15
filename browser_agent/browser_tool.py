from typing import Optional, Any, Literal
from langchain_core.tools import BaseTool
from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import Field

class BrowserTool(BaseTool):
    """Tool for autonomous web browsing and research."""
    
    name: Literal["browser_agent"] = "browser_agent"
    description: str = """Use this tool for any web-based tasks that require browser interaction and automation.
    Input should be a clear description of what you want to accomplish online.
    The tool will autonomously browse websites and perform actions on your behalf.
    FOR ALL ONLINE ORDERS, THE BILLING AND SHIPPING INFORMATION IS ALREADY SAVED ON THE WEBSITE, DO NOT ASK FOR IT.
    Examples:
    - "Order a large pepperoni pizza from Domino's for delivery to my address"
    - "Browse Amazon and add a Nintendo Switch to my cart"
    - "Research and summarize the key points of World War II for my history homework"
    - "Compare prices of flight tickets from NYC to London for next month"
    - "Sign up for a gym membership at Planet Fitness"
    - "Schedule a grocery delivery from Whole Foods"
    """
    llm: ChatAnthropic = Field(default_factory=lambda: ChatAnthropic(model="claude-3-5-sonnet-latest"))
    browser: Browser = Field(default_factory=lambda: Browser(
        config=BrowserConfig(
            chrome_instance_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        )
    ))

    def __init__(self, llm: Optional[ChatAnthropic] = None, browser: Optional[Browser] = None):
        """Initialize the browser tool with an optional LLM and browser instance."""
        super().__init__()
        if llm is not None:
            self.llm = llm
        if browser is not None:
            self.browser = browser

    async def _arun(self, task: str) -> str:
        """Run the browser agent asynchronously."""
        agent = Agent(
            task=task,
            llm=self.llm,
            browser=self.browser
        )
        try:
            result = await agent.run()
            return result
        finally:
            await self.browser.close()

    def _run(self, task: str) -> str:
        """Run the browser agent synchronously."""
        import asyncio
        return asyncio.run(self._arun(task)) 