import os
import sys
from pathlib import Path

# Add the root directory to Python path
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from langchain_core.tools import tool
from langchain_community.tools import TavilySearchResults
from langchain.tools import Tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool

from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper
from podcast_agent.podcast_knowledge_base import PodcastKnowledgeBase
from twitter_langchain import TwitterApiWrapper, TwitterToolkit
from custom_twitter_actions import (
    create_delete_tweet_tool,
    create_get_user_id_tool,
    create_get_user_tweets_tool,
    create_retweet_tool
)

# Load environment variables
load_dotenv(override=True)

ALLOW_DANGEROUS_REQUEST = True

# Initialize base components
llm = ChatAnthropic(model="claude-3-sonnet-20240229")

# Initialize config
config = {
    "configurable": {
        "thread_id": "Voice Agent",
        "character": "Voice Assistant",
        "recursion_limit": 100,
    },
    "character": {
        "name": "Voice Assistant",
        "bio": ["You are a helpful voice assistant."],
    }
}

# Initialize wrappers
twitter_api_wrapper = TwitterApiWrapper(config=config)
agentkit = CdpAgentkitWrapper()
hyperbolic_agentkit = HyperbolicAgentkitWrapper()

podcast_kb = PodcastKnowledgeBase()

@tool
def add(a: int, b: int):
    """Add two numbers. Please let the user know that you're adding the numbers BEFORE you call the tool"""
    return a + b

@tool
def enhance_result(initial_query: str, query_result: str, llm):
    """Analyze the initial query and its results to generate an enhanced follow-up query."""
    return llm.invoke(f"Based on the initial query '{initial_query}' and results '{query_result}', suggest an enhanced follow-up query.")

def create_tools(llm=None, twitter_api_wrapper=None, knowledge_base=None, podcast_knowledge_base=None, agentkit=None):
    """Create and return a list of tools."""
    tools = []

    # Use default LLM if none provided
    if llm is None:
        llm = ChatAnthropic(model="claude-3-sonnet-20240229")

    # Add basic tools
    tools.append(add)
    
    # Add enhance query tool
    tools.append(Tool(
        name="enhance_query",
        func=lambda initial_query, query_result: enhance_result(initial_query, query_result, llm),
        description="Analyze the initial query and its results to generate an enhanced follow-up query. Takes two parameters: initial_query (the original query string) and query_result (the results obtained from that query)."
    ))

    # Initialize toolkits if wrappers are provided
    if twitter_api_wrapper:
        twitter_toolkit = TwitterToolkit.from_twitter_api_wrapper(twitter_api_wrapper)
        if os.getenv("USE_TWITTER_CORE", "true").lower() == "true":
            tools.extend(twitter_toolkit.get_tools())
        
        # Add Twitter-specific tools based on environment variables
        if os.getenv("USE_TWEET_DELETE", "true").lower() == "true":
            tools.append(create_delete_tweet_tool(twitter_api_wrapper))
        if os.getenv("USE_USER_ID_LOOKUP", "true").lower() == "true":
            tools.append(create_get_user_id_tool(twitter_api_wrapper))
        if os.getenv("USE_USER_TWEETS_LOOKUP", "true").lower() == "true":
            tools.append(create_get_user_tweets_tool(twitter_api_wrapper))
        if os.getenv("USE_RETWEET", "true").lower() == "true":
            tools.append(create_retweet_tool(twitter_api_wrapper))

    if agentkit and os.getenv("USE_CDP_TOOLS", "true").lower() == "true":
        cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
        tools.extend(cdp_toolkit.get_tools())

    # Initialize Hyperbolic tools if enabled
    if os.getenv("USE_HYPERBOLIC_TOOLS", "true").lower() == "true":
        hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic_agentkit)
        tools.extend(hyperbolic_toolkit.get_tools())

    # Add Knowledge Base Tools if provided and enabled
    if os.getenv("USE_TWITTER_KNOWLEDGE_BASE", "true").lower() == "true" and knowledge_base:
        tools.append(Tool(
            name="query_knowledge_base",
            description="Query the knowledge base for relevant tweets about crypto/AI/tech trends.",
            func=lambda query: knowledge_base.query_knowledge_base(query)
        ))

    if os.getenv("USE_PODCAST_KNOWLEDGE_BASE", "true").lower() == "true" and podcast_knowledge_base:
        tools.append(Tool(
            name="query_podcast_knowledge_base",
            func=lambda query: podcast_knowledge_base.format_query_results(
                podcast_knowledge_base.query_knowledge_base(query)
            ),
            description="Query the podcast knowledge base for relevant podcast segments about crypto/Web3/gaming. Input should be a search query string."
        ))

    # Add web search tools if enabled
    if os.getenv("USE_WEB_SEARCH", "true").lower() == "true":
        tools.append(DuckDuckGoSearchRun(
            name="web_search",
            description="Search the internet for current information."
        ))
        tools.append(tavily_tool)

    # Add requests toolkit if enabled
    if os.getenv("USE_REQUEST_TOOLS", "true").lower() == "true":
        toolkit = RequestsToolkit(
            requests_wrapper=TextRequestsWrapper(headers={}),
            allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
        )
        tools.extend(toolkit.get_tools())

    podcast_query_tool = Tool(
        name="query_podcast_knowledge",
        description="Query the podcast knowledge base for relevant information about crypto, gaming, and Web3 topics",
        func=lambda query: podcast_kb.format_query_results(podcast_kb.query_knowledge_base(query))
    )
    tools.append(podcast_query_tool)

    return tools

tavily_tool = TavilySearchResults(
    max_results=5,
    include_answer=True,
    description=(
        "This is a search tool for accessing the internet.\n\n"
        "Let the user know you're asking your friend Tavily for help before you call the tool."
    ),

)

# Initialize all tools with default wrappers
TOOLS = create_tools(
    llm=llm,
    twitter_api_wrapper=twitter_api_wrapper,
    agentkit=agentkit
)  # Initialize with all available tools
