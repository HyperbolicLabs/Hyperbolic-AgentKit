import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
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

# Import CDP related modules
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool
from pydantic import BaseModel, Field
from cdp import Wallet

# Import Hyperbolic related modules
from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper
from twitter_langchain import TwitterApiWrapper, TwitterToolkit
from custom_twitter_actions import create_delete_tweet_tool, create_get_user_id_tool, create_get_user_tweets_tool, create_retweet_tool
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
from twitter_state import TwitterState, MENTION_CHECK_INTERVAL, MAX_MENTIONS_PER_INTERVAL
from twitter_knowledge_base import TweetKnowledgeBase, Tweet, update_knowledge_base
from langchain_core.runnables import RunnableConfig
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
    
    # Create a dynamic prompt that encourages creative query generation
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

# # Knowledge base setup
# urls = [
#     "https://docs.prylabs.network/docs/monitoring/checking-status",
# ]

# # Load and process documents
# docs = [WebBaseLoader(url).load() for url in urls]
# docs_list = [item for sublist in docs for item in sublist]
# # Load and process documents
# docs = [WebBaseLoader(url).load() for url in urls]
# docs_list = [item for sublist in docs for item in sublist]

# text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
#     chunk_size=1000, chunk_overlap=200
# )
# doc_splits = text_splitter.split_documents(docs_list)
# text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
#     chunk_size=1000, chunk_overlap=200
# )
# doc_splits = text_splitter.split_documents(docs_list)

# vectorstore = SKLearnVectorStore.from_documents(
#     documents=doc_splits,
#     embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
# )
# vectorstore = SKLearnVectorStore.from_documents(
#     documents=doc_splits,
#     embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
# )

# retriever = vectorstore.as_retriever(k=3)
# retriever = vectorstore.as_retriever(k=3)

# retrieval_tool = Tool(
#     name="retrieval_tool",
#     description="Useful for retrieving information from the knowledge base about running Ethereum operations.",
#     func=retriever.get_relevant_documents
# )
# retrieval_tool = Tool(
#     name="retrieval_tool",
#     description="Useful for retrieving information from the knowledge base about running Ethereum operations.",
#     func=retriever.get_relevant_documents
# )

# Multi-token deployment setup
# Multi-token deployment setup
DEPLOY_MULTITOKEN_PROMPT = """
This tool deploys a new multi-token contract with a specified base URI for token metadata.
The base URI should be a template URL containing {id} which will be replaced with the token ID.
For example: 'https://example.com/metadata/{id}.json'
"""

class DeployMultiTokenInput(BaseModel):
    """Input argument schema for deploy multi-token contract action."""
    base_uri: str = Field(
        ...,
        description="The base URI template for token metadata. Must contain {id} placeholder.",
        example="https://example.com/metadata/{id}.json"
    )

def deploy_multi_token(wallet: Wallet, base_uri: str) -> str:
    """Deploy a new multi-token contract with the specified base URI."""
    """Deploy a new multi-token contract with the specified base URI."""
    if "{id}" not in base_uri:
        raise ValueError("base_uri must contain {id} placeholder")
    
    
    deployed_contract = wallet.deploy_multi_token(base_uri)
    result = deployed_contract.wait()
    return f"Successfully deployed multi-token contract at address: {result.contract_address}"

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

def create_agent_tools(llm, twitter_api_wrapper, knowledge_base, podcast_knowledge_base, agentkit, config):
    """Create and return a list of tools for the agent to use."""
    tools = []

    # Add enhance query tool
    tools.append(Tool(
        name="enhance_query",
        func=lambda initial_query, query_result: enhance_result(initial_query, query_result, llm),
        description="Analyze the initial query and its results to generate an enhanced follow-up query. Takes two parameters: initial_query (the original query string) and query_result (the results obtained from that query)."
    ))

    # Create CDP tools
    deployMultiTokenTool = CdpTool(
        name="deploy_multi_token",
        description=DEPLOY_MULTITOKEN_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=DeployMultiTokenInput,
        func=deploy_multi_token,
    )

    # Create Twitter tools
    delete_tweet_tool = create_delete_tweet_tool(twitter_api_wrapper)
    get_user_id_tool = create_get_user_id_tool(twitter_api_wrapper)
    user_tweets_tool = create_get_user_tweets_tool(twitter_api_wrapper)
    
    retweet_tool = create_retweet_tool(twitter_api_wrapper)

    # Create toolkits
    twitter_toolkit = TwitterToolkit.from_twitter_api_wrapper(twitter_api_wrapper)
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    hyperbolic_agentkit = HyperbolicAgentkitWrapper()
    hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic_agentkit)
    toolkit = RequestsToolkit(
        requests_wrapper=TextRequestsWrapper(headers={}),
        allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
    )

    # Add Knowledge Base Tools based on environment variables
    if os.getenv("USE_TWITTER_KNOWLEDGE_BASE", "true").lower() == "true" and knowledge_base is not None:
        tools.append(Tool(
            name="query_knowledge_base",
            description="Query the knowledge base for relevant tweets about crypto/AI/tech trends.",
            func=lambda query: knowledge_base.query_knowledge_base(query)
        ))

    if os.getenv("USE_PODCAST_KNOWLEDGE_BASE", "true").lower() == "true" and podcast_knowledge_base is not None:
        tools.append(Tool(
            name="query_podcast_knowledge_base",
            func=lambda query: podcast_knowledge_base.format_query_results(
                podcast_knowledge_base.query_knowledge_base(query)
            ),
            description="Query the podcast knowledge base for relevant podcast segments about crypto/Web3/gaming. Input should be a search query string."
        ))

    # Add tools based on environment variables
    if os.getenv("USE_CDP_TOOLS", "false").lower() == "true":
        tools.extend(cdp_toolkit.get_tools())

    if os.getenv("USE_HYPERBOLIC_TOOLS", "false").lower() == "true":
        tools.extend(hyperbolic_toolkit.get_tools())

    if os.getenv("USE_TWITTER_CORE", "true").lower() == "true":
        tools.extend(twitter_toolkit.get_tools())

    if os.getenv("USE_TWEET_REPLY_TRACKING", "true").lower() == "true":
        tools.extend([check_replied_tool, add_replied_tool])

    if os.getenv("USE_TWEET_REPOST_TRACKING", "true").lower() == "true":
        tools.extend([check_reposted_tool, add_reposted_tool])

    if os.getenv("USE_TWEET_DELETE", "true").lower() == "true":
        tools.append(delete_tweet_tool)

    if os.getenv("USE_USER_ID_LOOKUP", "true").lower() == "true":
        tools.append(get_user_id_tool)

    if os.getenv("USE_USER_TWEETS_LOOKUP", "true").lower() == "true":
        tools.append(user_tweets_tool)

    if os.getenv("USE_RETWEET", "true").lower() == "true":
        tools.append(retweet_tool)

    if os.getenv("USE_DEPLOY_MULTITOKEN", "false").lower() == "true":
        tools.append(deployMultiTokenTool)

    if os.getenv("USE_WEB_SEARCH", "false").lower() == "true":
        tools.append(DuckDuckGoSearchRun(
            name="web_search",
            description="Search the internet for current information."
        ))

    if os.getenv("USE_REQUEST_TOOLS", "false").lower() == "true":
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

        print_system("Initializing Twitter API wrapper...")
        twitter_api_wrapper = TwitterApiWrapper(config=config)
        
        
        
        print_system("Initializing knowledge bases...")
        knowledge_base = None
        podcast_knowledge_base = None

        # Twitter Knowledge Base initialization
        if os.getenv("USE_KNOWLEDGE_BASE", "true").lower() == "true":
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
                        print_system("Updating knowledge base with KOL tweets...")
                        await update_knowledge_base(twitter_api_wrapper, knowledge_base, config['character']['kol_list'])
                        stats = knowledge_base.get_collection_stats()
                        print_system(f"Updated knowledge base stats: {stats}")
                except Exception as e:
                    print_error(f"Error initializing Twitter knowledge base: {e}")

        # Podcast Knowledge Base initialization
        if os.getenv("USE_PODCAST_KNOWLEDGE_BASE", "true").lower() == "true":
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

        # Rest of initialization (tools, etc.)
        # Reference to original code:

        wallet_data = None
        if os.path.exists(wallet_data_file):
            with open(wallet_data_file) as f:
                wallet_data = f.read()

        # Configure CDP Agentkit
        values = {}
        if wallet_data is not None:
            values = {"cdp_wallet_data": wallet_data}
        
        agentkit = CdpAgentkitWrapper(**values)
        
        # Save wallet data
        wallet_data = agentkit.export_wallet()
        with open(wallet_data_file, "w") as f:
            f.write(wallet_data)

        # Create tools using the helper function
        tools = create_agent_tools(llm, twitter_api_wrapper, knowledge_base, podcast_knowledge_base, agentkit, config)

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
        ), config, runnable_config, twitter_api_wrapper, knowledge_base, podcast_knowledge_base

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
            
            # Process chunks using the updated runnable_config with async handling
            async for chunk in run_with_progress(
                agent_executor.astream,  # Use astream instead of stream
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



class AgentExecutionError(Exception):
    """Custom exception for agent execution errors."""
    pass

async def run_autonomous_mode(agent_executor, config, runnable_config, twitter_api_wrapper, knowledge_base, podcast_knowledge_base):
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
            print_system(f"Completed cycle. Waiting {MENTION_CHECK_INTERVAL/60} minutes before next check...")
            await asyncio.sleep(MENTION_CHECK_INTERVAL)

        except KeyboardInterrupt:
            print_system("\nSaving state and exiting...")
            twitter_state.save()
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
        agent_executor, config, runnable_config, twitter_api_wrapper, knowledge_base, podcast_knowledge_base = await initialize_agent()
        mode = choose_mode()
        
        if mode == "chat":
            await run_chat_mode(agent_executor=agent_executor, config=config, runnable_config=runnable_config)
        elif mode == "auto":
            await run_autonomous_mode(
                agent_executor=agent_executor,
                config=config,
                runnable_config=runnable_config,
                twitter_api_wrapper=twitter_api_wrapper,
                knowledge_base=knowledge_base,
                podcast_knowledge_base=podcast_knowledge_base
            )
        
    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting Agent...")
    asyncio.run(main())


#   "kol_list": [
#     {
#       "username": "aixbt_agent",
#       "user_id": "1852674305517342720"
#     },
#     {
#       "username": "0xMert_",
#       "user_id": "1309886201944473600"
#     },
#     {
#       "username": "sassal0x",
#       "user_id": "313724502"
#     },
#     {
#       "username": "jessepollak",
#       "user_id": "18876842"
#     },
#     {
#       "username": "0xCygaar",
#       "user_id": "1287576585353039872"
#     },
#     {
#       "username": "iamDCinvestor",
#       "user_id": "956670268596015105"
#     },
#     {
#       "username": "blknoiz06",
#       "user_id": "973261472"
#     },
#     {
#       "username": "shawmakesmagic",
#       "user_id": "1830340867737178112"
#     },
#     {
#       "username": "mteamisloading",
#       "user_id": "1461735251412193281"
#     },
#     {
#       "username": "cryptopunk7213",
#       "user_id": "1025381906173583361"
#     },
#     {
#       "username": "stevenyuntcap",
#       "user_id": "780884633252683780"
#     },
#     {
#       "username": "dabit3",
#       "user_id": "17189394"
#     },
#     {
#       "username": "gammichan",
#       "user_id": "905566160044920832"
#     },
#     {
#       "username": "NateGeraci",
#       "user_id": "522571568"
#     },
#     {
#       "username": "Punk9277",
#       "user_id": "950486928784228352"
#     },
#     {
#       "username": "S4mmyEth",
#       "user_id": "223921570"
#     },
#     {
#       "username": "jon_charb",
#       "user_id": "1484537340412452868"
#     },
#     {
#       "username": "beast_ico",
#       "user_id": "1499585375534206980"
#     },
#     {
#       "username": "MaxResnick1",
#       "user_id": "1275877058342682633"
#     },
#     {
#       "username": "0xBreadguy",
#       "user_id": "1453661470869360643"
#     },
#     {
#       "username": "Austin_Federa",
#       "user_id": "38055242"
#     },
#     {
#       "username": "balajis",
#       "user_id": "2178012643"
#     },
#     {
#       "username": "RyanWatkins_",
#       "user_id": "708805895258574849"
#     },
#     {
#       "username": "JasonYanowitz",
#       "user_id": "1107518478"
#     },
#     {
#       "username": "HighCoinviction",
#       "user_id": "1268013291944771584"
#     },
#     {
#       "username": "divine_economy",
#       "user_id": "1379448557711818759"
#     },
#     {
#       "username": "udiWertheimer",
#       "user_id": "14527699"
#     },
#     {
#       "username": "0xngmi",
#       "user_id": "1373304198448709632"
#     },
#     {
#       "username": "OX_DAO",
#       "user_id": "1471279207095406595"
#     },
#     {
#       "username": "DefiIgnas",
#       "user_id": "831767219071754240"
#     },
#     {
#       "username": "DeFi_Dad",
#       "user_id": "991745162274467840"
#     },
#     {
#       "username": "llamaonthebrink",
#       "user_id": "1276213805580681219"
#     },
#     {
#       "username": "lex_node",
#       "user_id": "954015928924057601"
#     },
#     {
#       "username": "keoneHD",
#       "user_id": "19569158"
#     },
#     {
#       "username": "brian_armstrong",
#       "user_id": "14379660"
#     },
#     {
#       "username": "ryanberckmans",
#       "user_id": "546460454"
#     },
#     {
#       "username": "KevinWSHPod",
#       "user_id": "1328652802344833024"
#     },
#     {
#       "username": "DSBatten",
#       "user_id": "73066647"
#     },
#     {
#       "username": "jerallaire",
#       "user_id": "2478756618"
#     },
#     {
#       "username": "gakonst",
#       "user_id": "804029200315334656"
#     },
#     {
#       "username": "sreeramkannan",
#       "user_id": "2166711024"
#     },
#     {
#       "username": "Rewkang",
#       "user_id": "1138033434"
#     },
#     {
#       "username": "chainyoda",
#       "user_id": "112509659"
#     },
#     {
#       "username": "alpha_pls",
#       "user_id": "1450882486372913152"
#     },
#     {
#       "username": "TimBeiko",
#       "user_id": "80722677"
#     },
#     {
#       "username": "CampbellJAustin",
#       "user_id": "1625681692848537603"
#     },
#     {
#       "username": "WazzCrypto",
#       "user_id": "869659857590288384"
#     },
#     {
#       "username": "templecrash",
#       "user_id": "2882819127"
#     },
#     {
#       "username": "tarunchitra",
#       "user_id": "53836928"
#     },
#     {
#       "username": "Narodism",
#       "user_id": "897198731975680001"
#     },
#     {
#       "username": "SmallCapScience",
#       "user_id": "1352089119334281216"
#     },
#     {
#       "username": "defi_monk",
#       "user_id": "1469182121013129223"
#     },
#     {
#       "username": "ChainLinkGod",
#       "user_id": "1035721495"
#     },
#     {
#       "username": "trentdotsol",
#       "user_id": "1562178659766751237"
#     },
#     {
#       "username": "armaniferrante",
#       "user_id": "276810355"
#     },
#     {
#       "username": "Vivek4real_",
#       "user_id": "851277718368829443"
#     },
#     {
#       "username": "Zagabond",
#       "user_id": "1423031747432783872"
#     },
#     {
#       "username": "punk9059",
#       "user_id": "1449164448321605632"
#     },
#     {
#       "username": "dotkrueger",
#       "user_id": "67469426"
#     },
#     {
#       "username": "fede_intern",
#       "user_id": "1634677972979310594"
#     },
#     {
#       "username": "VaderResearch",
#       "user_id": "1416874867086045192"
#     },
#     {
#       "username": "DeeZe",
#       "user_id": "127646057"
#     },
#     {
#       "username": "LukeYoungblood",
#       "user_id": "86364019"
#     },
#     {
#       "username": "CryptoKaduna",
#       "user_id": "1103404363861684236"
#     },
#     {
#       "username": "Shaughnessy119",
#       "user_id": "2215937899"
#     },
#     {
#       "username": "LucaNetz",
#       "user_id": "807982663000674305"
#     },
#     {
#       "username": "0xstark",
#       "user_id": "14053424"
#     },
#     {
#       "username": "DavidFBailey",
#       "user_id": "30597171"
#     },
#     {
#       "username": "Defi0xJeff",
#       "user_id": "1460252469745782790"
#     },
#     {
#       "username": "Darrenlautf",
#       "user_id": "987634087274823680"
#     },
#     {
#       "username": "mdudas",
#       "user_id": "7184612"
#     },
#     {
#       "username": "dankrad",
#       "user_id": "115069952"
#     }
# ],