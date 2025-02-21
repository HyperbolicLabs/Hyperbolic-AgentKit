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
from browser_agent import BrowserToolkit

from coinbase_agentkit import (
    AgentKit,
    AgentKitConfig,
    CdpWalletProvider,
    CdpWalletProviderConfig,
    cdp_api_action_provider,
    cdp_wallet_action_provider,
    erc20_action_provider,
    pyth_action_provider,
    wallet_action_provider,
    weth_action_provider,
    twitter_action_provider,
)
from coinbase_agentkit_langchain import get_langchain_tools

from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper
from podcast_agent.podcast_knowledge_base import PodcastKnowledgeBase
from twitter_agent.twitter_state import TwitterState
from twitter_agent.custom_twitter_actions import (
    create_delete_tweet_tool,
    create_get_user_id_tool,
    create_get_user_tweets_tool,
    create_retweet_tool
)
wallet_data_file = "wallet_data.txt"

wallet_data = None
if os.path.exists(wallet_data_file):
    with open(wallet_data_file) as f:
        wallet_data = f.read()

wallet_provider = CdpWalletProvider(CdpWalletProviderConfig(
    api_key_name=os.getenv("CDP_API_KEY_NAME"),
    api_key_private=os.getenv("CDP_API_KEY_PRIVATE"),
    network_id=os.getenv("CDP_NETWORK_ID", "base-mainnet"),
    wallet_data=wallet_data if wallet_data else None
))


agent_kit = AgentKit(AgentKitConfig(
    wallet_provider=wallet_provider,
    action_providers=[
        cdp_api_action_provider(),
        cdp_wallet_action_provider(),
        erc20_action_provider(),
        pyth_action_provider(),
        wallet_action_provider(),
        weth_action_provider(),
        twitter_action_provider(),
    ]
))

from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper
from podcast_agent.podcast_knowledge_base import PodcastKnowledgeBase
from twitter_agent.custom_twitter_actions import (
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
hyperbolic_agentkit = HyperbolicAgentkitWrapper()

podcast_kb = PodcastKnowledgeBase()

@tool
def add(a: int, b: int):
    """Add two numbers. Please let the user know that you're adding the numbers BEFORE you call the tool"""
    return a + b

def create_tools(knowledge_base=None, podcast_knowledge_base=None, agentkit=agent_kit):
    """Create and return a list of tools."""
    tools = []
    # Add basic tools
    tools.append(add)

    # Add browser toolkit if enabled
    if os.getenv("USE_BROWSER_TOOLS", "true").lower() == "true":
        browser_toolkit = BrowserToolkit()
        tools.extend(browser_toolkit.get_tools())
    
    # Add Twitter State Management Tools if enabled
    if os.getenv("USE_TWEET_REPLY_TRACKING", "true").lower() == "true":
        twitter_state = TwitterState()
        tools.extend([
            Tool(
                name="has_replied_to",
                func=twitter_state.has_replied_to,
                description="""Check if we have already replied to a tweet. MUST be used before replying to any tweet.
                Input: tweet ID string.
                Rules:
                1. Always check this before replying to any tweet
                2. If returns True, do NOT reply and select a different tweet
                3. If returns False, proceed with reply_to_tweet then add_replied_to"""
            ),
            Tool(
                name="add_replied_to",
                func=twitter_state.add_replied_tweet,
                description="""Add a tweet ID to the database of replied tweets. 
                MUST be used after successfully replying to a tweet.
                Input: tweet ID string.
                Rules:
                1. Only use after successful reply_to_tweet
                2. Must verify with has_replied_to first
                3. Stores tweet ID permanently to prevent duplicate replies"""
            )
        ])

    if os.getenv("USE_TWEET_REPOST_TRACKING", "true").lower() == "true":
        if not 'twitter_state' in locals():
            twitter_state = TwitterState()
        tools.extend([
            Tool(
                name="has_reposted",
                func=twitter_state.has_reposted,
                description="Check if we have already reposted a tweet. Input should be a tweet ID string."
            ),
            Tool(
                name="add_reposted",
                func=twitter_state.add_reposted_tweet,
                description="Add a tweet ID to the database of reposted tweets."
            )
        ])

    # Add Custom Twitter Tools if enabled
    if os.getenv("USE_TWITTER_CORE", "true").lower() == "true":
        if os.getenv("USE_TWEET_DELETE", "true").lower() == "true":
            tools.append(create_delete_tweet_tool())
            
        if os.getenv("USE_USER_ID_LOOKUP", "true").lower() == "true":
            tools.append(create_get_user_id_tool())
            
        if os.getenv("USE_USER_TWEETS_LOOKUP", "true").lower() == "true":
            tools.append(create_get_user_tweets_tool())
            
        if os.getenv("USE_RETWEET", "true").lower() == "true":
            tools.append(create_retweet_tool())

    # Add Twitter Knowledge Base Tool if enabled
    if os.getenv("USE_TWITTER_KNOWLEDGE_BASE", "true").lower() == "true" and knowledge_base:
        tools.append(Tool(
            name="query_twitter_knowledge_base",
            func=lambda query: knowledge_base.format_query_results(
                knowledge_base.query_knowledge_base(query)
            ),
            description="""Query the Twitter knowledge base for relevant tweets about crypto/AI/tech trends.
            Input should be a search query string.
            Example: query_twitter_knowledge_base("latest developments in AI")"""
        ))

    # Add Podcast Knowledge Base Tools if enabled
    if os.getenv("USE_PODCAST_KNOWLEDGE_BASE", "true").lower() == "true" and podcast_knowledge_base:
        tools.append(Tool(
            name="query_podcast_knowledge_base",
            func=lambda query: podcast_knowledge_base.format_query_results(
                podcast_knowledge_base.query_knowledge_base(query)
            ),
            description="Query the podcast knowledge base for relevant podcast segments about crypto/Web3/gaming. Input should be a search query string."
        ))

    # Add Coinbase AgentKit tools if enabled
    if os.getenv("USE_COINBASE_TOOLS", "true").lower() == "true":
        coinbase_tools = get_langchain_tools(agentkit)
        tools.extend(coinbase_tools)

    # Add Hyperbolic tools if enabled
    if os.getenv("USE_HYPERBOLIC_TOOLS", "true").lower() == "true":
        hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic_agentkit)
        tools.extend(hyperbolic_toolkit.get_tools())

    # Add web search tools if enabled
    if os.getenv("USE_WEB_SEARCH", "true").lower() == "true":
        tools.append(tavily_tool)

    # Add requests toolkit if enabled
    if os.getenv("USE_REQUEST_TOOLS", "true").lower() == "true":
        toolkit = RequestsToolkit(
            requests_wrapper=TextRequestsWrapper(headers={}),
            allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
        )
        tools.extend(toolkit.get_tools())

    # Add podcast query tool if enabled
    if os.getenv("USE_PODCAST_KNOWLEDGE_BASE", "true").lower() == "true":
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
TOOLS = create_tools(knowledge_base=None, podcast_knowledge_base=podcast_kb, agentkit=agent_kit)
