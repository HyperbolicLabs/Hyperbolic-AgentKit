import os
import sys
from dotenv import load_dotenv
from datetime import datetime
import json
from typing import List, Dict, Any, Optional
import random
import asyncio
import warnings

# Import prompts
from prompts import (
    PODCAST_QUERY_PROMPT,
    PODCAST_TOPICS,
    PODCAST_ASPECTS,
    BASIC_QUERY_TEMPLATES
)
from tooldescriptions import (
    TWITTER_REPLY_CHECK_DESCRIPTION,
    TWITTER_ADD_REPLIED_DESCRIPTION,
    TWITTER_REPOST_CHECK_DESCRIPTION,
    TWITTER_ADD_REPOSTED_DESCRIPTION,
    TWITTER_KNOWLEDGE_BASE_DESCRIPTION,
    PODCAST_KNOWLEDGE_BASE_DESCRIPTION,
    WEB_SEARCH_DESCRIPTION
)

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
    
    # Format the prompt with random selections
    prompt = PODCAST_QUERY_PROMPT.format(
        topics=random.sample(PODCAST_TOPICS, 3),
        aspects=random.sample(PODCAST_ASPECTS, 2)
    )
    
    # Get response from LLM
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    query = response.content.strip()
    
    # Clean up the query if needed
    query = query.replace('"', '').replace('Query:', '').strip()
    
    return query

# Legacy function for fallback
def generate_basic_podcast_query() -> str:
    """Legacy function that returns a basic template query as fallback."""
    return random.choice(BASIC_QUERY_TEMPLATES)

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

# Constants
ALLOW_DANGEROUS_REQUEST = True  # Set to False in production for security
wallet_data_file = "wallet_data.txt"


# Create TwitterState instance
twitter_state = TwitterState()

# Create tools for Twitter state management
check_replied_tool = Tool(
    name="has_replied_to",
    func=twitter_state.has_replied_to,
    description=TWITTER_REPLY_CHECK_DESCRIPTION
)

add_replied_tool = Tool(
    name="add_replied_to",
    func=twitter_state.add_replied_tweet,
    description=TWITTER_ADD_REPLIED_DESCRIPTION
)

check_reposted_tool = Tool(
    name="has_reposted",
    func=twitter_state.has_reposted,
    description=TWITTER_REPOST_CHECK_DESCRIPTION
)

add_reposted_tool = Tool(
    name="add_reposted",
    func=twitter_state.add_reposted_tweet,
    description=TWITTER_ADD_REPOSTED_DESCRIPTION
)

def loadCharacters(charactersArg: str) -> List[Dict[str, Any]]:
    """Load character files and return their configurations."""
    characterPaths = charactersArg.split(",") if charactersArg else []
    loadedCharacters = []

    if not characterPaths:
        # Load default chainyoda character
        default_path = os.path.join(os.path.dirname(__file__), "characters/default.json")
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

    # Add Twitter Knowledge Base Tools if enabled
    if os.getenv("USE_TWITTER_KNOWLEDGE_BASE", "true").lower() == "true" and knowledge_base is not None:
        tools.append(Tool(
            name="query_twitter_knowledge_base",
            description=TWITTER_KNOWLEDGE_BASE_DESCRIPTION,
            func=lambda query: knowledge_base.query_knowledge_base(query)
        ))

    # Add Twitter State Management Tools if enabled
    if os.getenv("USE_TWEET_REPLY_TRACKING", "true").lower() == "true":
        twitter_state = TwitterState()
        tools.extend([
            Tool(
                name="has_replied_to",
                func=twitter_state.has_replied_to,
                description=TWITTER_REPLY_CHECK_DESCRIPTION
            ),
            Tool(
                name="add_replied_to",
                func=twitter_state.add_replied_tweet,
                description=TWITTER_ADD_REPLIED_DESCRIPTION
            )
        ])

    if os.getenv("USE_TWEET_REPOST_TRACKING", "true").lower() == "true":
        if not 'twitter_state' in locals():
            twitter_state = TwitterState()
        tools.extend([
            Tool(
                name="has_reposted",
                func=twitter_state.has_reposted,
                description=TWITTER_REPOST_CHECK_DESCRIPTION
            ),
            Tool(
                name="add_reposted",
                func=twitter_state.add_reposted_tweet,
                description=TWITTER_ADD_REPOSTED_DESCRIPTION
            )
        ])

    # Initialize Twitter client and add custom Twitter Tools if enabled
    if os.getenv("USE_TWITTER_CORE", "true").lower() == "true":
        print_system("Adding custom Twitter tools...")
        twitter_client = TwitterClient()
        
        if os.getenv("USE_TWEET_DELETE", "true").lower() == "true":
            tools.append(create_delete_tweet_tool())
            
        if os.getenv("USE_USER_ID_LOOKUP", "true").lower() == "true":
            tools.append(create_get_user_id_tool())
            
        if os.getenv("USE_USER_TWEETS_LOOKUP", "true").lower() == "true":
            tools.append(create_get_user_tweets_tool())
            
        if os.getenv("USE_RETWEET", "true").lower() == "true":
            tools.append(create_retweet_tool())
            
        print_system("Added custom Twitter tools")

    # Add Podcast Knowledge Base Tools if enabled
    if os.getenv("USE_PODCAST_KNOWLEDGE_BASE", "true").lower() == "true" and podcast_knowledge_base is not None:
        tools.append(Tool(
            name="query_podcast_knowledge_base",
            func=lambda query: podcast_knowledge_base.format_query_results(
                podcast_knowledge_base.query_knowledge_base(query)
            ),
            description=PODCAST_KNOWLEDGE_BASE_DESCRIPTION
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

    # Add web search if enabled
    if os.getenv("USE_WEB_SEARCH", "false").lower() == "true":
        tools.append(DuckDuckGoSearchRun(
            name="web_search",
            description=WEB_SEARCH_DESCRIPTION
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
            characters = loadCharacters(os.getenv("CHARACTER_FILE"))
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
                
                # Get current stats before processing
                stats = podcast_knowledge_base.get_collection_stats()
                print_system(f"Current podcast knowledge base stats: {stats}")
                
                print_system("Checking for new podcast transcripts...")
                podcast_knowledge_base.process_all_json_files()
                
                # Get updated stats
                new_stats = podcast_knowledge_base.get_collection_stats()
                print_system(f"Updated podcast knowledge base stats: {new_stats}")
                
                if new_stats["count"] > stats["count"]:
                    print_system(f"Added {new_stats['count'] - stats['count']} new segments to the knowledge base")
                else:
                    print_system("No new segments were added to the knowledge base")
                    
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

       

        return create_react_agent(
            llm,
            tools=tools,
            checkpointer=memory,
            state_modifier=personality,
        ), config, runnable_config

    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        raise

def choose_mode():
    """Choose whether to run in autonomous or chat mode."""
    while True:
        print("\nAvailable modes:")
        print("1. Interactive chat mode")
        print("2. Character Twitter Automation")

        choice = input("\nChoose a mode (enter number): ").lower().strip()
        if choice in ["1"]:
            return "chat"
        elif choice in ["2"]:
            return "twitter_automation"
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

async def run_chat_mode(agent_executor, config, runnable_config):
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

async def run_twitter_automation(agent_executor, config, runnable_config):
    """Run the agent autonomously with specified intervals."""
    print_system(f"Starting autonomous mode as {config['character']['name']}...")
    twitter_state.load()
    
    # Reset last_check_time on startup to ensure immediate first run
    twitter_state.last_check_time = None
    twitter_state.save()
    
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
            # Check mention timing - only wait if we've checked too recently
            if not twitter_state.can_check_mentions():
                wait_time = MENTION_CHECK_INTERVAL - (datetime.now() - twitter_state.last_check_time).total_seconds()
                if wait_time > 0:
                    print_system(f"Waiting {int(wait_time)} seconds before next mention check...")
                    await asyncio.sleep(wait_time)
                    continue

            # Update last_check_time at the start of each check
            twitter_state.last_check_time = datetime.now()
            twitter_state.save()

            # Select unique KOLs for interaction using random.sample
            NUM_KOLS = 1  # Define constant for number of KOLs to interact with
            selected_kols = random.sample(config['character']['kol_list'], NUM_KOLS)

            # Log selected KOLs
            for i, kol in enumerate(selected_kols, 1):
                print_system(f"Selected KOL {i}: {kol['username']}")
            
            # Create KOL XML structure for the prompt
            kol_xml = "\n".join([
                f"""<kol_{i+1}>
                <username>{kol['username']}</username>
                <user_id>{kol['user_id']}</user_id>
                </kol_{i+1}>""" 
                for i, kol in enumerate(selected_kols)
            ])
            
            thought = f"""
            You are an AI-powered Twitter bot acting as a marketer for The Rollup Podcast (@therollupco). Your primary functions are to create engaging original tweets, respond to mentions, and interact with key opinion leaders (KOLs) in the blockchain and cryptocurrency industry. 
            Your goal is to promote the podcast and drive engagement while maintaining a consistent, friendly, and knowledgeable persona.

            Here's the essential information for your operation:

            <kol_list>
            {kol_xml}
            </kol_list>

            <account_info>
            {config['character']['accountid']}
            </account_info>

            <twitter_settings>
            <mention_check_interval>{MENTION_CHECK_INTERVAL}</mention_check_interval>
            <last_mention_id>{twitter_state.last_mention_id}</last_mention_id>
            <current_time>{datetime.now().strftime('%H:%M:%S')}</current_time>
            </twitter_settings>

            For each task, read the entire task instructions before taking action. Wrap your reasoning inside <reasoning> tags before taking action.

            Task 1: Query podcast knowledge base and recent tweets

            First, gather context from recent tweets using the get_user_tweets() for each ofthese accounts:
            Account 1: 1172866088222244866
            Account 2: 1046811588752285699  
            Account 3: 2680433033

            Then query the podcast knowledge base:

            <podcast_query>
            {await generate_podcast_query()}
            </podcast_query>

            <reasoning>
            1. Analyze all available context:
            - Review all recent tweets retrieved from the accounts
            - Analyze the podcast knowledge base query results
            - Identify common themes and topics across both sources
            - Note key insights that could inform an engaging tweet

            2. Synthesize information:
            - Find connections between recent tweets and podcast content
            - Identify trending topics or discussions
            - Look for opportunities to add unique value or insights
            - Consider how to build on existing conversations

            3. Brainstorm tweet ideas:
            Tweet Guidelines:
            - Ideal length: Less than 70 characters
            - Maximum length: 280 characters
            - Emoji usage: Do not use emojis
            - Content references: Use evergreen language when referencing podcast content
                - DO: "We explored this topic in our podcast"
                - DO: "Check out our podcast episode about [topic]"
                - DO: "We discussed this in depth on @therollupco"
                - DON'T: "In our latest episode..."
                - DON'T: "Just released..."
                - DON'T: "Our newest episode..."
            - Generate at least three distinct tweet ideas that combine insights from both sources, and follow the tweet guidelines
            - For each idea, write out the full tweet text
            - Count the characters in each tweet to ensure they meet length requirements
            - Use evergreen references to podcast content while staying relevant to current discussions

            4. Evaluate and refine tweets:
            - Assess each tweet for engagement potential, relevance, and clarity
            - Refine the tweets to improve their impact and adhere to guidelines
            - Ensure references to podcast content are accurate and timeless
            - Verify the tweet adds value to ongoing conversations

            5. Select the best tweet:
            - Choose the most effective tweet based on your evaluation
            - Explain why this tweet best combines recent context with podcast insights
            - Verify it aligns with The Rollup's messaging and style
            </reasoning>

            After your reasoning, create and post your tweet using the create_tweet() function.


            Task 2: Check for and reply to new Twitter mentions

            Use the get_mentions() function to retrieve new mentions. For each mention newer than the last_mention_id:

            <reasoning>
            1. Analyze the mention:
            - Summarize the content of the mention
            - Identify any specific questions or topics related to blockchain and cryptocurrency
            - Determine the sentiment (positive, neutral, negative) of the mention

            2. Determine reply appropriateness:
            - Check if you've already responded using has_replied_to()
            - Assess if the mention requires a response based on its content and relevance
            - Explain your decision to reply or not

            3. Craft a response (if needed):
            - Outline key points to address in your reply
            - Consider how to add value or insights to the conversation
            - Draft a response that is engaging, informative, and aligned with your persona

            4. Review and refine:
            - Ensure the response adheres to character limits and style guidelines
            - Check that the reply is relevant to blockchain and cryptocurrency
            - Verify that the tone is friendly and encouraging further discussion
            </reasoning>

            If you decide to reply:
            1. Create a response using the reply_to_tweet() function
            2. Mark the tweet as replied using the add_replied_tweet() function

            Task 3: Interact with KOLs

            For each KOL in the provided list:

            <reasoning>
            1. Retrieve and analyze recent tweets:
            - Use get_user_tweets() to fetch recent tweets
            - Summarize the main topics and themes in the KOL's recent tweets
            - Identify tweets specifically related to blockchain and cryptocurrency

            2. Select a tweet to reply to:
            - List the top 3 most relevant tweets for potential interaction
            - For each tweet, explain its relevance to blockchain/cryptocurrency and potential for engagement
            - Choose the best tweet for reply, justifying your selection

            3. Formulate a reply:
            - Identify unique insights or perspectives you can add to the conversation
            - Draft 2-3 potential replies, each offering a different angle or value-add
            - Evaluate each draft for engagement potential, relevance, and alignment with your persona

            4. Finalize the reply:
            - Select the best reply from your drafts
            - Ensure the chosen reply meets all guidelines (character limit, style, etc.)
            - Explain why this reply is the most effective for interacting with the KOL and promoting The Rollup Podcast
            </reasoning>

            After your reasoning:
            1. Select the most relevant and recent tweet to reply to
            2. Create a reply for the selected tweet using the reply_to_tweet() function

            General Guidelines:
            1. Stay in character with consistent personality traits
            2. Ensure all interactions are relevant to blockchain and cryptocurrency
            3. Be friendly, witty, and engaging
            4. Share interesting insights or thought-provoking perspectives when relevant
            5. Ask follow-up questions to encourage discussion when appropriate
            6. Adhere to the character limits and style guidelines

            Output your actions in the following format:

            <knowledge_base_query>
            [Your knowledge base query results and insights used]
            </knowledge_base_query>

            <recent_tweets_analysis>
            [Your analysis of the 9 recent tweets from The Rollup accounts]
            </recent_tweets_analysis>

            <original_tweets>
            <tweet_1>[Content for new tweet]</tweet_1>
            </original_tweets>

            <mention_replies>
            [Your replies to any new mentions, if applicable]
            </mention_replies>

            <kol_interactions>
            [For each of the KOLs in the provided list:]
            <kol_name>[KOL's name]</kol_name>
            <reply_to>
                <tweet_id>[ID of the tweet you're replying to]</tweet_id>
                <reply_content>[Your reply content]</reply_content>
            </reply_to>
            </kol_interactions>

            Remember to use the provided functions as needed and adhere to all guidelines and rules throughout your interactions.
            """

            # Process chunks as they arrive using async for
            async for chunk in agent_executor.astream(
                {"messages": [HumanMessage(content=thought)]},
                runnable_config
            ):
                print_system(chunk)
                if "agent" in chunk:
                    response = chunk["agent"]["messages"][0].content
                    print_ai(format_ai_message_content(response))
                    
                    # Handle tool responses
                    if isinstance(response, list):
                        for item in response:
                            if item.get('type') == 'tool_use':
                                if item.get('name') == 'add_replied_to':
                                    tweet_id = item['input'].get('__arg1')
                                    if tweet_id:
                                        print_system(f"Adding tweet {tweet_id} to replied database...")
                                        result = twitter_state.add_replied_tweet(tweet_id)
                                        print_system(result)
                                        
                                        # Update state after successful reply
                                        twitter_state.last_mentigiton_id = tweet_id
                                        twitter_state.last_check_time = datetime.now()
                                        twitter_state.save()
                                
                elif "tools" in chunk:
                    print_system(chunk["tools"]["messages"][0].content)
                print_system("-------------------")

            print_system(f"Completed cycle. Waiting {MENTION_CHECK_INTERVAL/60} minutes before next check...")
            await asyncio.sleep(MENTION_CHECK_INTERVAL)

        except KeyboardInterrupt:
            print_system("\nSaving state and exiting...")
            twitter_state.save()
            sys.exit(0)
            
        except Exception as e:
            print_error(f"Unexpected error: {str(e)}")
            print_error(f"Error type: {type(e).__name__}")
            if hasattr(e, '__traceback__'):
                import traceback
                traceback.print_tb(e.__traceback__)
            
            print_system("Continuing after error...")
            await asyncio.sleep(MENTION_CHECK_INTERVAL)


async def main():
    """Start the chatbot agent."""
    try:
        agent_executor, config, runnable_config = await initialize_agent()
        mode = choose_mode()
        
        if mode == "chat":
            await run_chat_mode(
                agent_executor=agent_executor,
                config=config,
                runnable_config=runnable_config,
            )
        elif mode == "twitter_automation":     
            await run_twitter_automation(
                agent_executor=agent_executor,
                config=config,
                runnable_config=runnable_config,
            )
        
    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting Agent...")
    asyncio.run(main())
