import os
import sys
from dotenv import load_dotenv
from datetime import datetime
import json
from typing import List, Dict, Any, Optional
import random
import asyncio
import warnings


# Load environment variables from .env file
load_dotenv(override=True)

os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from langchain_core.messages import HumanMessage
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain.tools import Tool
from langchain_core.runnables import RunnableConfig
from browser_agent import BrowserToolkit

# Import Coinbase AgentKit related modules
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
from pydantic import BaseModel, Field

# Import Hyperbolic related modules
from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper

# Import Twitter-related modules
from twitter_agent.custom_twitter_actions import (
    TwitterClient,
    create_delete_tweet_tool,
    create_get_user_id_tool,
    create_get_user_tweets_tool,
    create_retweet_tool
)
from twitter_agent.twitter_state import TwitterState, MENTION_CHECK_INTERVAL, MAX_MENTIONS_PER_INTERVAL
from twitter_agent.twitter_knowledge_base import TweetKnowledgeBase, update_knowledge_base

from github_agent.custom_github_actions import GitHubAPIWrapper, create_evaluate_profiles_tool

# Import local modules
from utils import (
    Colors, 
    print_ai, 
    print_system, 
    print_error, 
    ProgressIndicator, 
    run_with_progress, 
    format_ai_message_content
)
from podcast_agent.podcast_knowledge_base import PodcastKnowledgeBase

async def generate_llm_podcast_query(llm: ChatAnthropic = None) -> str:
    """
    Generates a dynamic, contextually-aware query for the podcast knowledge base using an LLM.
    Uses various prompting techniques to create unique and insightful queries.
    
    Args:
        llm: ChatAnthropic instance. If None, creates a new one.
        
    Returns:
        str: A generated query string
    """
    llm = ChatAnthropic(model="claude-3-5-haiku-20241022")
    
    # Define topic areas and aspects to consider
    topics = [
        # Scaling & Infrastructure
        "horizontal scaling challenges", "decentralization vs scalability tradeoffs",
        "infrastructure evolution", "restaking models and implementation",
        
        # Technical Architecture  
        "layer 2 solutions and rollups", "node operations", "geographic distribution",
        "decentralized service deployment",
        
        # Ecosystem Development
        "market coordination mechanisms", "operator and staker dynamics", 
        "blockchain platform evolution", "community bootstrapping",
        
        # Future Trends
        "ecosystem maturation", "market maker emergence",
        "strategy optimization", "service coordination",
        
        # Web3 Infrastructure
        "decentralized vs centralized solutions", "cloud provider comparisons",
        "resilience and reliability", "infrastructure distribution",
        
        # Market Dynamics
        "marketplace design", "coordination mechanisms",
        "efficient frontier development", "ecosystem player roles"
    ]
    
    aspects = [
        # Technical
        "infrastructure scalability", "technical implementation challenges",
        "architectural tradeoffs", "system reliability",
        
        # Market & Economics
        "market efficiency", "economic incentives",
        "stakeholder dynamics", "value capture mechanisms",
        
        # Development
        "platform evolution", "ecosystem growth",
        "adoption patterns", "integration challenges",
        
        # Strategy
        "optimization approaches", "competitive dynamics",
        "strategic positioning", "risk management"
    ]
    
    
    prompt = f"""
    Generate ONE focused query about Web3 technology to search crypto podcast transcripts.

    Consider these elements (but focus on just ONE):
    - Core Topics: {random.sample(topics, 3)}
    - Key Aspects: {random.sample(aspects, 2)}

    Requirements for the query:
    1. Focus on just ONE specific technical aspect or challenge from the above
    2. Keep the scope narrow and focused
    3. Use simple, clear language
    4. Aim for 10-15 words
    5. Ask about concrete technical details rather than abstract concepts
    
    Example good queries:
    - "What are the main challenges operators face when running rollup nodes?"
    - "How do layer 2 solutions handle data availability?"
    - "What infrastructure requirements do validators need for running nodes?"

    Generate exactly ONE query that meets these criteria. Return ONLY the query text, nothing else.
    """
    # Get response from LLM
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    query = response.content.strip()
    
    # Clean up the query if needed
    query = query.replace('"', '').replace('Query:', '').strip()
    
    return query

# Legacy function for fallback
def generate_basic_podcast_query() -> str:
    """Legacy function that returns a basic template query as fallback."""
    query_templates = [
        "What are the key insights from recent podcast discussions?",
        "What emerging trends were highlighted in recent episodes?",
        "What expert predictions were made about the crypto market?",
        "What innovative blockchain use cases were discussed recently?",
        "What regulatory developments were analyzed in recent episodes?"
    ]
    return random.choice(query_templates)

async def generate_podcast_query() -> str:
    """
    Main query generation function that attempts to use LLM-based generation
    with fallback to basic templates.
    
    Returns:
        str: A query string for the podcast knowledge base
    """
    try:
        # Create LLM instance
        llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
        # Get LLM-generated query
        query = await generate_llm_podcast_query(llm)
        return query
    except Exception as e:
        print_error(f"Error generating LLM query: {e}")
        # Fallback to basic template
        return generate_basic_podcast_query()

async def enhance_result(initial_query: str, query_result: str, llm: ChatAnthropic = None) -> str:
    """
    Analyzes the initial query and its results to generate an enhanced follow-up query.
    
    Args:
        initial_query: The original query used to get podcast insights
        query_result: The result/response obtained from the knowledge base
        llm: ChatAnthropic instance. If None, creates a new one.
        
    Returns:
        str: An enhanced follow-up query
    """
    if llm is None:
        llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
    
    analysis_prompt = f"""
    As an AI specializing in podcast content analysis, analyze this query and its results to generate a more focused follow-up query.

    <initial_query>
    {initial_query}
    </initial_query>

    <query_result>
    {query_result}
    </query_result>

    Your task:
    1. Analyze the relationship between the query and its results
    2. Identify any:
       - Unexplored angles
       - Interesting tangents
       - Deeper technical aspects
       - Missing context
       - Potential contradictions
       - Novel connections
    3. Generate a follow-up query that:
       - Builds upon the most interesting insights
       - Explores identified gaps
       - Dives deeper into promising areas
       - Connects different concepts
       - Challenges assumptions
       - Seeks practical applications

    Requirements for the enhanced query:
    1. Must be more specific than the initial query
    2. Should target unexplored aspects revealed in the results
    3. Must maintain relevance to blockchain/crypto
    4. Should encourage detailed technical or analytical responses
    5. Must be a single, clear question
    6. Should lead to actionable insights

    Return ONLY the enhanced follow-up query, nothing else.
    Make it unique and substantially different from the initial query.
    """
    
    try:
        # Get response from LLM
        response = await llm.ainvoke([HumanMessage(content=analysis_prompt)])
        enhanced_query = response.content.strip()
        
        # Clean up the query
        enhanced_query = enhanced_query.replace('"', '').replace('Query:', '').strip()
        
        print_system(f"Enhanced query generated: {enhanced_query}")
        return enhanced_query
        
    except Exception as e:
        print_error(f"Error generating enhanced query: {e}")
        # Return a modified version of the original query as fallback
        return f"Regarding {initial_query.split()[0:3].join(' ')}, what are the deeper technical implications?"

# Constants
ALLOW_DANGEROUS_REQUEST = True  # Set to False in production for security
wallet_data_file = "wallet_data.txt"


# Create TwitterState instance
twitter_state = TwitterState()

# Create tools for Twitter state management
check_replied_tool = Tool(
    name="has_replied_to",
    func=twitter_state.has_replied_to,
    description="""Check if we have already replied to a tweet. MUST be used before replying to any tweet.
    Input: tweet ID string.
    Rules:
    1. Always check this before replying to any tweet
    2. If returns True, do NOT reply and select a different tweet
    3. If returns False, proceed with reply_to_tweet then add_replied_to"""
)

add_replied_tool = Tool(
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

check_reposted_tool = Tool(
    name="has_reposted",
    func=twitter_state.has_reposted,
    description="Check if we have already reposted a tweet. Input should be a tweet ID string."
)

add_reposted_tool = Tool(
    name="add_reposted",
    func=twitter_state.add_reposted_tweet,
    description="Add a tweet ID to the database of reposted tweets."
)

def loadCharacters(charactersArg: str) -> List[Dict[str, Any]]:
    """Load character files and return their configurations."""
    characterPaths = charactersArg.split(",") if charactersArg else []
    loadedCharacters = []

    if not characterPaths:
        # Load default chainyoda character
        default_path = os.path.join(os.path.dirname(__file__), "characters/chainyoda.json")
        characterPaths.append(default_path)

    for characterPath in characterPaths:
        try:
            # Search in common locations
            searchPaths = [
                characterPath,
                os.path.join("characters", characterPath),
                os.path.join(os.path.dirname(__file__), "characters", characterPath)
            ]

            for path in searchPaths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        character = json.load(f)
                        loadedCharacters.append(character)
                        print(f"Successfully loaded character from: {path}")
                        break
            else:
                raise FileNotFoundError(f"Could not find character file: {characterPath}")

        except Exception as e:
            print(f"Error loading character from {characterPath}: {e}")
            raise

    return loadedCharacters

def process_character_config(character: Dict[str, Any]) -> str:
    """Process character configuration into agent personality."""
    # Extract core character elements
    bio = "\n".join([f"- {item}" for item in character.get('bio', [])])
    lore = "\n".join([f"- {item}" for item in character.get('lore', [])])
    knowledge = "\n".join([f"- {item}" for item in character.get('knowledge', [])])

    topics = "\n".join([f"- {item}" for item in character.get('topics', [])])

    kol_list = "\n".join([f"- {item}" for item in character.get('kol_list', [])])
    
    # Format style guidelines
    style_all = "\n".join([f"- {item}" for item in character.get('style', {}).get('all', [])])

    adjectives = "\n".join([f"- {item}" for item in character.get('adjectives', [])])
    # style_chat = "\n".join([f"- {item}" for item in character.get('style', {}).get('chat', [])])
    # style_post = "\n".join([f"- {item}" for item in character.get('style', {}).get('post', [])])

    # Select and format post examples
    all_posts = character.get('postExamples', [])
    selected_posts = random.sample(all_posts, min(10, len(all_posts)))
    post_examples = "\n".join([
        f"Example {i+1}: {post}"
        for i, post in enumerate(selected_posts)
        if isinstance(post, str) and post.strip()
    ])

    personality = f"""
    Here are examples of your previous posts:
    <post_examples>
    {post_examples}
    </post_examples>

    You are an AI character designed to interact on social media with this configuration:

    <character_bio>
    {bio}
    </character_bio>

    <character_lore>
    {lore}
    </character_lore>

    <character_knowledge>
    {knowledge}
    </character_knowledge>

    <character_adjectives>
    {adjectives}
    </character_adjectives>

    <kol_list>
    {kol_list}
    </kol_list>

    <style_guidelines>
    {style_all}
    </style_guidelines>

    <topics>
    {topics}
    </topics>
    """

    return personality

def create_agent_tools(llm, knowledge_base, podcast_knowledge_base, agent_kit, config):
    """Create and return a list of tools for the agent to use."""
    tools = []

        # Add browser toolkit if enabled
    if os.getenv("USE_BROWSER_TOOLS", "true").lower() == "true":
        browser_toolkit = BrowserToolkit.from_llm(llm)
        tools.extend(browser_toolkit.get_tools())

    # Add enhance query tool
    tools.append(Tool(
        name="enhance_query",
        func=lambda initial_query, query_result: enhance_result(initial_query, query_result, llm),
        description="Analyze the initial query and its results to generate an enhanced follow-up query. Takes two parameters: initial_query (the original query string) and query_result (the results obtained from that query)."
    ))

    # Add Twitter Knowledge Base Tools if enabled
    if os.getenv("USE_TWITTER_KNOWLEDGE_BASE", "true").lower() == "true" and knowledge_base is not None:
        tools.append(Tool(
            name="query_twitter_knowledge_base",
            description="Query the Twitter knowledge base for relevant tweets about crypto/AI/tech trends.",
            func=lambda query: knowledge_base.query_knowledge_base(query)
        ))

    # Add Twitter State Management Tools
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
        ),
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

    # Initialize Twitter client
    twitter_client = TwitterClient()

    # Add Custom Twitter Tools
    print_system("Adding custom Twitter tools...")
    tools.extend([
        create_delete_tweet_tool(),
        create_get_user_id_tool(),
        create_get_user_tweets_tool(),
        create_retweet_tool()
    ])
    print_system("Added custom Twitter tools")

    # Add Twitter Knowledge Base Tool if enabled
    if os.getenv("USE_TWITTER_KNOWLEDGE_BASE", "true").lower() == "true" and knowledge_base is not None:
        print_system("Adding Twitter knowledge base tool...")
        tools.append(Tool(
            name="query_twitter_knowledge_base",
            func=lambda query: knowledge_base.format_query_results(
                knowledge_base.query_knowledge_base(query)
            ),
            description="""Query the Twitter knowledge base for relevant tweets about crypto/AI/tech trends.
            Input should be a search query string.
            Example: query_twitter_knowledge_base("latest developments in AI")"""
        ))
        print_system("Added Twitter knowledge base tool")

    # Add Podcast Knowledge Base Tools if enabled
    if os.getenv("USE_PODCAST_KNOWLEDGE_BASE", "true").lower() == "true" and podcast_knowledge_base is not None:
        tools.append(Tool(
            name="query_podcast_knowledge_base",
            func=lambda query: podcast_knowledge_base.format_query_results(
                podcast_knowledge_base.query_knowledge_base(query)
            ),
            description="Query the podcast knowledge base for relevant podcast segments about crypto/Web3/gaming. Input should be a search query string."
        ))
    

    # Add Coinbase AgentKit tools (blockchain/wallet/twitter operations)
    if os.getenv("USE_COINBASE_TOOLS", "true").lower() == "true":
        print_system("Adding Coinbase AgentKit tools...")
        coinbase_tools = get_langchain_tools(agent_kit)
        tools.extend(coinbase_tools)
        print_system(f"Added {len(coinbase_tools)} Coinbase tools")

    # Add Hyperbolic tools
    if os.getenv("USE_HYPERBOLIC_TOOLS", "false").lower() == "true":
        hyperbolic_agentkit = HyperbolicAgentkitWrapper()
        hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic_agentkit)
        tools.extend(hyperbolic_toolkit.get_tools())

    # Add additional tools
    if os.getenv("USE_WEB_SEARCH", "false").lower() == "true":
        tools.append(DuckDuckGoSearchRun(
            name="web_search",
            description="Search the internet for current information."
        ))

    if os.getenv("USE_REQUEST_TOOLS", "false").lower() == "true":
        toolkit = RequestsToolkit(
            requests_wrapper=TextRequestsWrapper(headers={}),
            allow_dangerous_requests=os.getenv("ALLOW_DANGEROUS_REQUEST", "true").lower() == "true",
        )
        tools.extend(toolkit.get_tools())

    return tools

async def initialize_agent():
    """Initialize the agent with tools and configuration."""
    try:
        print_system("Initializing LLM...")
        llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

        print_system("Loading character configuration...")
        try:
            characters = loadCharacters(os.getenv("CHARACTER_FILE", "chainyoda.json"))
            character = characters[0]  # Use first character if multiple loaded
        except Exception as e:
            print_error(f"Error loading character: {e}")
            raise

        print_system("Processing character configuration...")
        personality = process_character_config(character)

        # Create config first before using 
        config = {
            "configurable": {
                "thread_id": f"{character['name']} Agent",
                "character": character["name"],
                "recursion_limit": 100,
            },
            "character": {
                "name": character["name"],
                "bio": character.get("bio", []),
                "lore": character.get("lore", []),
                "knowledge": character.get("knowledge", []),
                "style": character.get("style", {}),
                "messageExamples": character.get("messageExamples", []),
                "postExamples": character.get("postExamples", []),
                "kol_list": character.get("kol_list", []),
                "accountid": character.get("accountid")
            }
        }

        print_system("Initializing knowledge bases...")
        knowledge_base = None
        podcast_knowledge_base = None

        # Configure Coinbase AgentKit first
        print_system("Initializing Coinbase AgentKit...")
        wallet_data = None
        if os.path.exists(wallet_data_file):
            with open(wallet_data_file) as f:
                wallet_data = f.read()

        # Configure wallet provider with all available action providers
        wallet_provider = CdpWalletProvider(CdpWalletProviderConfig(
            api_key_name=os.getenv("CDP_API_KEY_NAME"),
            api_key_private=os.getenv("CDP_API_KEY_PRIVATE"),
            network_id=os.getenv("CDP_NETWORK_ID", "base-mainnet"),
            wallet_data=wallet_data if wallet_data else None
        ))

        # Initialize AgentKit with all action providers
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
        
        # Save wallet data
        if not wallet_data:
            wallet_data = json.dumps(wallet_provider.export_wallet().to_dict())
            with open(wallet_data_file, "w") as f:
                f.write(wallet_data)

        # Twitter Knowledge Base initialization
        while True:
            init_twitter_kb = input("\nDo you want to initialize the Twitter knowledge base? (y/n): ").lower().strip()
            if init_twitter_kb in ['y', 'n']:
                break
            print("Invalid choice. Please enter 'y' or 'n'.")

        if init_twitter_kb == 'y':
            try:
                knowledge_base = TweetKnowledgeBase()
                stats = knowledge_base.get_collection_stats()
                print_system(f"Initial Twitter knowledge base stats: {stats}")
                
                # Initialize Twitter client here, before we need it
                print_system("\n=== Initializing Twitter Client ===")
                twitter_client = TwitterClient()
                print_system("Twitter client initialized successfully")
                
                while True:
                    clear_choice = input("\nDo you want to clear the existing Twitter knowledge base? (y/n): ").lower().strip()
                    if clear_choice in ['y', 'n']:
                        break
                    print("Invalid choice. Please enter 'y' or 'n'.")

                if clear_choice == 'y':
                    knowledge_base.clear_collection()
                    print_system("Knowledge base cleared")

                while True:
                    update_choice = input("\nDo you want to update the Twitter knowledge base with KOL tweets? (y/n): ").lower().strip()
                    if update_choice in ['y', 'n']:
                        break
                    print("Invalid choice. Please enter 'y' or 'n'.")

                if update_choice == 'y':
                    print_system("\n=== Starting Twitter Knowledge Base Update ===")
                    
                    # Debug the character config
                    print_system("Character config structure:")
                    print_system(f"Config keys: {list(config.keys())}")
                    print_system(f"Character config keys: {list(config['character'].keys())}")
                    
                    # Get and validate KOL list
                    print_system("\n=== Extracting KOL List ===")
                    kol_list = config['character'].get('kol_list', [])
                    
                    print_system(f"Raw KOL list type: {type(kol_list)}")
                    print_system(f"Raw KOL list length: {len(kol_list)}")
                    
                    if len(kol_list) > 0:
                        print_system("First KOL entry:")
                        print_system(json.dumps(kol_list[0], indent=2))
                    
                    # Validate the KOL list structure
                    if not isinstance(kol_list, list):
                        print_error("KOL list in character config is not a list")
                        return
                    
                    print_system(f"Found {len(kol_list)} KOLs in character config")
                    
                    try:
                        print_system("\n=== Updating Knowledge Base ===")
                        await update_knowledge_base(
                            twitter_client=twitter_client,
                            knowledge_base=knowledge_base,
                            kol_list=kol_list
                        )
                        stats = knowledge_base.get_collection_stats()
                        print_system(f"Updated knowledge base stats: {stats}")
                    except Exception as e:
                        print_error(f"Error updating knowledge base: {str(e)}")
                        print_error("Debug information:")
                        print_error(f"KOL list type: {type(kol_list)}")
                        print_error(f"KOL list length: {len(kol_list)}")
                        if len(kol_list) > 0:
                            print_error(f"First two KOL entries:")
                            print_error(json.dumps(kol_list[:2], indent=2))
                        import traceback
                        print_error(f"Full error traceback:\n{traceback.format_exc()}")
            except Exception as e:
                print_error(f"Error initializing Twitter knowledge base: {e}")

        # Podcast Knowledge Base initialization
        while True:
            init_podcast_kb = input("\nDo you want to initialize the Podcast knowledge base? (y/n): ").lower().strip()
            if init_podcast_kb in ['y', 'n']:
                break
            print("Invalid choice. Please enter 'y' or 'n'.")

        if init_podcast_kb == 'y':
            try:
                podcast_knowledge_base = PodcastKnowledgeBase()
                print_system("Podcast knowledge base initialized successfully")
                
                while True:
                    clear_choice = input("\nDo you want to clear the existing podcast knowledge base? (y/n): ").lower().strip()
                    if clear_choice in ['y', 'n']:
                        break
                    print("Invalid choice. Please enter 'y' or 'n'.")

                if clear_choice == 'y':
                    podcast_knowledge_base.clear_collection()
                    print_system("Podcast knowledge base cleared")

                print_system("Processing podcast transcripts...")
                podcast_knowledge_base.process_all_json_files()
                stats = podcast_knowledge_base.get_collection_stats()
                print_system(f"Podcast knowledge base stats: {stats}")
            except Exception as e:
                print_error(f"Error initializing Podcast knowledge base: {e}")

        # Create tools using the helper function
        tools = create_agent_tools(llm, knowledge_base, podcast_knowledge_base, agent_kit, config)

        # Add GitHub profile evaluation tool
        if os.getenv("USE_GITHUB_TOOLS", "true").lower() == "true":
            try:
                github_token = os.getenv("GITHUB_TOKEN")
                if not github_token:
                    raise ValueError("GitHub token not found. Please set the GITHUB_TOKEN environment variable.")
                else:
                    print_system("Initializing GitHub API wrapper...")
                    github_wrapper = GitHubAPIWrapper(github_token)
                    print_system("Creating GitHub profile evaluation tool...")
                    github_tool = create_evaluate_profiles_tool(github_wrapper)
                    tools.append(github_tool)
                    print_system("Successfully added GitHub profile evaluation tool")
            except Exception as e:
                print_error(f"Error initializing GitHub tools: {str(e)}")
                print_error("GitHub tools will not be available")

        # Create the runnable config with increased recursion limit
        runnable_config = RunnableConfig(recursion_limit=200)

        for tool in tools:
            print_system(tool.name)

        # Initialize memory saver
        memory = MemorySaver()

        # Combine personality with Coinbase AgentKit capabilities
        combined_personality = f"""
        {personality}

        You are also empowered with Coinbase AgentKit capabilities to interact onchain and on Twitter. You can:
        1. Execute blockchain transactions and interact with smart contracts
        2. Request funds from the faucet if on base-sepolia network
        3. Manage wallet operations and token interactions
        4. Access price feeds and other blockchain data
        5. Post tweets, reply to tweets, and manage Twitter interactions
        6. Follow/unfollow users and manage Twitter engagement

        Before executing blockchain or Twitter actions:
        1. Check wallet details and network for blockchain operations
        2. Verify sufficient funds for transactions
        3. Handle errors gracefully (retry on 5XX errors)
        4. Use available tools appropriately
        5. Follow Twitter's usage guidelines and best practices

        If asked about unavailable functionality, recommend checking docs.cdp.coinbase.com.
        """

        return create_react_agent(
            llm,
            tools=tools,
            checkpointer=memory,
            state_modifier=combined_personality,
        ), config, runnable_config, knowledge_base, podcast_knowledge_base

    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        raise

def choose_mode():
    """Choose whether to run in autonomous or chat mode."""
    while True:
        print("\nAvailable modes:")
        print("1. chat    - Interactive chat mode")
        print("2. auto    - Autonomous action mode")

        choice = input("\nChoose a mode (enter number or name): ").lower().strip()
        if choice in ["1", "chat"]:
            return "chat"
        elif choice in ["2", "auto"]:
            return "auto"
        print("Invalid choice. Please try again.")

async def run_with_progress(func, *args, **kwargs):
    """Run a function while showing a progress indicator between outputs."""
    progress = ProgressIndicator()
    
    try:
        # Handle both async and sync generators
        generator = func(*args, **kwargs)
        
        if hasattr(generator, '__aiter__'):  # Check if it's an async generator
            async for chunk in generator:
                progress.stop()  # Stop spinner before output
                yield chunk     # Yield the chunk immediately
                progress.start()  # Restart spinner while waiting for next chunk
        else:  # Handle synchronous generators
            for chunk in generator:
                progress.stop()
                yield chunk
                progress.start()
            
    finally:
        progress.stop()

async def run_chat_mode(agent_executor, config, runnable_config, knowledge_base=None, podcast_knowledge_base=None):
    """Run the agent interactively based on user input."""
    print_system("Starting chat mode... Type 'exit' to end.")
    print_system("Commands:")
    print_system("  exit     - Exit the chat")
    print_system("  status   - Check if agent is responsive")
    
    # Create the runnable config with required keys
    runnable_config = RunnableConfig(
        recursion_limit=200,
        configurable={
            "thread_id": config["configurable"]["thread_id"],
            "checkpoint_ns": "chat_mode",
            "checkpoint_id": str(datetime.now().timestamp())
        }
    )
    
    while True:
        try:
            prompt = f"{Colors.BLUE}{Colors.BOLD}User: {Colors.ENDC}"
            user_input = input(prompt)
            
            if not user_input:
                continue
            
            if user_input.lower() == "exit":
                break
            elif user_input.lower() == "status":
                print_system("Agent is responsive and ready for commands.")
                continue
            
            print_system(f"\nStarted at: {datetime.now().strftime('%H:%M:%S')}")
            
            async for chunk in run_with_progress(
                agent_executor.astream,
                {"messages": [HumanMessage(content=user_input)]},
                runnable_config
            ):
                if "agent" in chunk:
                    response = chunk["agent"]["messages"][0].content
                    print_ai(format_ai_message_content(response))
                elif "tools" in chunk:
                    print_system(chunk["tools"]["messages"][0].content)
                print_system("-------------------")
                
        except KeyboardInterrupt:
            print_system("\nExiting chat mode...")
            break
        except Exception as e:
            print_error(f"Error: {str(e)}")

async def run_autonomous_mode(agent_executor, config, runnable_config, knowledge_base=None, podcast_knowledge_base=None):
    """Run the agent autonomously with specified intervals."""
    print_system("Starting autonomous mode...")
    
    # Create the runnable config with required keys
    runnable_config = RunnableConfig(
        recursion_limit=200,
        configurable={
            "thread_id": config["configurable"]["thread_id"],
            "checkpoint_ns": "autonomous_mode",
            "checkpoint_id": str(datetime.now().timestamp())
        }
    )
    
    while True:
        try:
            thought = (
                "Be creative and do something interesting on the blockchain. "
                "Choose an action or set of actions and execute it that highlights your abilities."
            )

            async for chunk in run_with_progress(
                agent_executor.astream,
                {"messages": [HumanMessage(content=thought)]},
                runnable_config
            ):
                if "agent" in chunk:
                    print_ai(format_ai_message_content(chunk["agent"]["messages"][0].content))
                elif "tools" in chunk:
                    print_system(chunk["tools"]["messages"][0].content)
                print_system("-------------------")

            print_system("Waiting 10 seconds before next action...")
            await asyncio.sleep(10)

        except KeyboardInterrupt:
            print_system("\nExiting autonomous mode...")
            break
        except Exception as e:
            print_error(f"Error: {str(e)}")
            await asyncio.sleep(10)

async def main():
    """Start the chatbot agent."""
    try:
        agent_executor, config, runnable_config, knowledge_base, podcast_knowledge_base = await initialize_agent()
        mode = choose_mode()
        
        if mode == "chat":
            await run_chat_mode(
                agent_executor=agent_executor,
                config=config,
                runnable_config=runnable_config,
                knowledge_base=knowledge_base,
                podcast_knowledge_base=podcast_knowledge_base
            )
        elif mode == "auto":
            await run_autonomous_mode(
                agent_executor=agent_executor,
                config=config,
                runnable_config=runnable_config,
                knowledge_base=knowledge_base,
                podcast_knowledge_base=podcast_knowledge_base
            )
        
    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting Agent...")
    asyncio.run(main())
