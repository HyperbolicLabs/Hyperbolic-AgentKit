import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
from typing import List, Dict, Any, Optional
import random
import asyncio
import warnings
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone
)
from cartesia import Cartesia
import re
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import torch
import numpy as np
import sounddevice as sd
import pyaudio
from collections import deque

load_dotenv(override=True)

os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from langchain_core.messages import HumanMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain.tools import Tool
from langchain_core.runnables import RunnableConfig
from langchain.tools import Tool
from langchain_core.runnables import RunnableConfig

from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool
from pydantic import BaseModel, Field
from cdp import Wallet

from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper
from twitter_langchain import TwitterApiWrapper, TwitterToolkit
from custom_twitter_actions import create_delete_tweet_tool, create_get_user_id_tool, create_get_user_tweets_tool, create_retweet_tool

from utils import (
    Colors, 
    print_ai, 
    print_system, 
    print_error, 
    ProgressIndicator, 
    run_with_progress, 
    format_ai_message_content
)
from twitter_state import TwitterState, MENTION_CHECK_INTERVAL
from twitter_knowledge_base import TweetKnowledgeBase, update_knowledge_base
from langchain_core.runnables import RunnableConfig
from podcast_agent.podcast_knowledge_base import PodcastKnowledgeBase

from voice_pipeline.agents.pipeline_factory import VoicePipelineFactory, PipelineCredentials, PipelineConfig
from voice_pipeline.agents.cartesia_tts import CartesiaTTSConfig

async def generate_llm_podcast_query(llm: ChatAnthropic = None) -> str:
    """
    Generates a dynamic, contextually-aware query for the podcast knowledge base using an LLM.
    Uses various prompting techniques to create unique and insightful queries.
    
    Args:
        llm: ChatAnthropic instance. If None, creates a new one.
        
    Returns:
        str: A generated query string
    """
    llm = ChatOpenAI(model="gpt-4o-mini-2024-07-18") #change model to 4o
    
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

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    query = response.content.strip()
    
    query = query.replace('"', '').replace('Query:', '').strip()
    
    return query

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
        llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
        query = await generate_llm_podcast_query(llm)
        return query
    except Exception as e:
        print_error(f"Error generating LLM query: {e}")
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
        response = await llm.ainvoke([HumanMessage(content=analysis_prompt)])
        enhanced_query = response.content.strip()
        
        enhanced_query = enhanced_query.replace('"', '').replace('Query:', '').strip()
        
        print_system(f"Enhanced query generated: {enhanced_query}")
        return enhanced_query
        
    except Exception as e:
        print_error(f"Error generating enhanced query: {e}")
        return f"Regarding {initial_query.split()[0:3].join(' ')}, what are the deeper technical implications?"

ALLOW_DANGEROUS_REQUEST = True 
wallet_data_file = "wallet_data.txt"

twitter_state = TwitterState()

check_replied_tool = Tool(
    name="has_replied_to",
    func=twitter_state.has_replied_to,
    description="Check if we have already replied to a tweet. Input should be a tweet ID string."
)

add_replied_tool = Tool(
    name="add_replied_to",
    func=twitter_state.add_replied_tweet,
    description="Add a tweet ID to the database of replied tweets."
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
    
    bio = "\n".join([f"- {item}" for item in character.get('bio', [])])
    lore = "\n".join([f"- {item}" for item in character.get('lore', [])])
    knowledge = "\n".join([f"- {item}" for item in character.get('knowledge', [])])
    topics = "\n".join([f"- {item}" for item in character.get('topics', [])])
    kol_list = "\n".join([f"- {item}" for item in character.get('kol_list', [])])
    style_all = "\n".join([f"- {item}" for item in character.get('style', {}).get('all', [])])
    adjectives = "\n".join([f"- {item}" for item in character.get('adjectives', [])])

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
        
        You are an AI character designed to interact on social media, particularly Twitter, in the blockchain and cryptocurrency space. Your personality, knowledge, and capabilities are defined by the following information:

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

        Here is the list of Key Opinion Leaders (KOLs) to interact with:

        <kol_list>
        {kol_list}
        </kol_list>

        When communicating, adhere to these style guidelines:

        <style_guidelines>
        {style_all}
        </style_guidelines>

        Focus on these topics:

        <topics>
        {topics}
        </topics>

        Your core capabilities include:

        1. Blockchain Operations (via Coinbase Developer Platform - CDP):
        - Interact onchain
        - Deploy and manage tokens and wallets
        - Request funds from faucet on network ID `base-sepolia`

        2. Compute Operations (via Hyperbolic):
        - Rent compute resources
        - Check GPU status and availability
        - Connect to remote servers via SSH (use ssh_connect)
        - Execute commands on remote server (use remote_shell)

        3. System Operations:
        - Check SSH connection status with 'ssh_status'
        - Search the internet for current information
        - Post updates on X (Twitter)
        - Monitor and respond to mentions
        - Track replied tweets in database

        4. Knowledge Base Access:
        - Use DuckDuckGoSearchRun web_search tool for current information
        - Query Ethereum operations documentation
        - Access real-time blockchain information
        - Retrieve relevant technical documentation

        5. Twitter Interaction with Key Opinion Leaders (KOLs):
        - Find user IDs using get_user_id_tool
        - Retrieve tweets using user_tweets_tool
        - Reply to the most recent tweet of the selected KOL

        Important guidelines:
        1. Always stay in character
        2. Use your knowledge and capabilities appropriately
        3. Maintain consistent personality traits
        4. Follow style guidelines for all communications
        5. Use tools and capabilities when needed
        6. Do not reply to spam or bot mentions
        7. Ensure all tweets are less than 280 characters
        8. Vary your response style:
        - Generally use punchy one-liners (< 100 characters preferred)
        - Occasionally provide longer, more insightful posts
        - Sometimes use bullet points for clarity
        9. Respond directly to the core point
        10. Use emojis sparingly and naturally, not in every tweet
        11. Verify response relevance before posting:
            - Must reference specific blockchain/project if mentioned
            - Must directly address KOL's main point
            - Must match approved topics list
        12. No multi-part threads or responses
        13. Avoid qualifying statements or hedging language
        14. Check each response against filters:
            - Character limit adhered to
            - Contains relevant keyword
            - Directly matches conversation topic
            - Appropriate emoji usage (if any)

        When using tools:
        1. Check if you've replied to tweets using has_replied_to
        2. Track replied tweets using add_replied_to
        3. Check if you've reposted tweets using has_reposted
        4. Track reposted tweets using add_reposted
        5. Use retrieval_tool for Ethereum documentation
        6. Use get_user_id_tool to find KOL user IDs
        7. Use user_tweets_tool to retrieve KOL tweets
        """
    #     Before responding to any input, analyze the situation and plan your response in <response_planning> tags:
    #     1. Determine if the input is a mention or a regular message
    #     2. Identify the specific topic or context of the input
    #     3. List relevant character traits and knowledge that apply to the current situation:
    #     - Specify traits from the character bio that are relevant
    #     - Note any lore or knowledge that directly applies
    #     4. Consider potential tool usage:
    #     - Identify which tools might be needed
    #     - List required parameters for each tool and check if they're available in the input
    #     5. Plan the response:
    #     - Outline key points to include
    #     - Decide on an appropriate length and style (one-liner, longer insight, or bullet points)
    #     - Consider whether an emoji is appropriate for this specific response
    #     - Ensure the planned response aligns with the character's persona and style guidelines
    #     6. If interacting with KOLs:
    #     a. Plan to find their user IDs using get_user_id_tool
    #     b. Plan to retrieve their recent tweets using user_tweets_tool
    #     c. Ensure your planned response will be directly relevant to their tweet
    #     d. Plan to check if you have already replied using has_replied_to
    #     e. If you haven't replied, plan to use reply_to_tweet; otherwise, choose a different tweet
    #     f. Plan to use add_replied_to after replying to store the tweet ID
    #     7. Draft and refine the response:
    #     - Write out a draft of the response
    #     - Check that it meets all guidelines (character limit, relevance, style, etc.)
    #     - Adjust the response if necessary to meet all requirements

    #     After your analysis, provide your response in <response> tags.

    #     Example output structure:

    #     <response_planning>
    #     [Your detailed analysis of the situation and planning of the response]
    #     </response_planning>

    #     <response>
    #     [Your character's response, ensuring it adheres to the guidelines]
    #     </response>

    #     Remember:
    #     - If you're asked about current information and hit a rate limit on web_search, do not reply and wait until the next mention check.
    #     - When interacting with KOLs, ensure you're responding to their most recent tweets and maintaining your character's persona.
    #     - Always verify that you have all required parameters before calling any tools.
    #     - Vary your tweet length and style based on the context and importance of the message.
    #     - Use emojis naturally and sparingly, not in every tweet.
    #     - Double-check the word count of your response and adjust if necessary to meet the character limit.
    # # print_system(personality)

    return personality



async def initialize_agent():
    """Initialize the agent with tools and configuration."""
    try:
        print_system("Initializing LLM...")
        # Use GPT-4 Mini for faster responses
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model="gpt-4o-mini-2024-07-18",  # GPT-4 Mini model
            temperature=0.7,
            streaming=True,
            max_tokens=150,  # Keep responses concise for voice interaction
            presence_penalty=0.5,   # Encourage topic diversity
            frequency_penalty=0.5,  # Reduce repetition
            model_kwargs={
                "response_format": { "type": "text" }  # Force text responses
            }
        )

        print_system("Loading character configuration...")
        try:
            characters = loadCharacters(os.getenv("CHARACTER_FILE", "chainyoda.json"))
            character = characters[0] 
        except Exception as e:
            print_error(f"Error loading character: {e}")
            raise

        print_system("Processing character configuration...")
        personality = process_character_config(character)

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
        tools = []

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

        wallet_data = None
        if os.path.exists(wallet_data_file):
            with open(wallet_data_file) as f:
                wallet_data = f.read()

        values = {}
        if wallet_data is not None:
            values = {"cdp_wallet_data": wallet_data}
        
        agentkit = CdpAgentkitWrapper(**values)
        
        wallet_data = agentkit.export_wallet()
        with open(wallet_data_file, "w") as f:
            f.write(wallet_data)

        values = {}
        if wallet_data is not None:
            values = {"cdp_wallet_data": wallet_data}
        
        agentkit = CdpAgentkitWrapper(**values)
        
        wallet_data = agentkit.export_wallet()
        with open(wallet_data_file, "w") as f:
            f.write(wallet_data)

        twitter_toolkit = TwitterToolkit.from_twitter_api_wrapper(twitter_api_wrapper)
        cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
        hyperbolic_agentkit = HyperbolicAgentkitWrapper()
        hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic_agentkit)

    
        tools.append(Tool(
            name="enhance_query",
            func=lambda initial_query, query_result: enhance_result(initial_query, query_result, llm),
            description="Analyze the initial query and its results to generate an enhanced follow-up query. Takes two parameters: initial_query (the original query string) and query_result (the results obtained from that query)."
        ))

        deployMultiTokenTool = CdpTool(
            name="deploy_multi_token",
            description=DEPLOY_MULTITOKEN_PROMPT,
            cdp_agentkit_wrapper=agentkit,
            args_schema=DeployMultiTokenInput,
            func=deploy_multi_token,
        )

        delete_tweet_tool = create_delete_tweet_tool(twitter_api_wrapper)
        get_user_id_tool = create_get_user_id_tool(twitter_api_wrapper)
        user_tweets_tool = create_get_user_tweets_tool(twitter_api_wrapper)
        retweet_tool = create_retweet_tool(twitter_api_wrapper)

        toolkit = RequestsToolkit(
            requests_wrapper=TextRequestsWrapper(headers={}),
            allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
        )   

        memory = MemorySaver()
        
        # Knowledge Base Tools
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

        runnable_config = RunnableConfig(recursion_limit=200)

        for tool in tools:
            print_system(tool.name)

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
    """Choose whether to run in autonomous, chat, or voice mode."""
    while True:
        print("\nAvailable modes:")
        print("1. chat    - Interactive chat mode")
        print("2. auto    - Autonomous action mode")
        print("3. voice   - Voice conversation mode")

        choice = input("\nChoose a mode (enter number or name): ").lower().strip()
        if choice in ["1", "chat"]:
            return "chat"
        elif choice in ["2", "auto"]:
            return "auto"
        elif choice in ["3", "voice"]:
            return "voice"
        print("Invalid choice. Please try again.")

async def run_with_progress(func, *args, **kwargs):
    """Run a function while showing a progress indicator between outputs."""
    progress = ProgressIndicator()
    
    try:
        # Get the generator from the function call
        generator = func(*args, **kwargs)
        
        # Single loop to handle both async and sync generators
        if hasattr(generator, '__aiter__'):  # Async generator
            async for chunk in generator:
                progress.stop()
                yield chunk
                progress.start()
        else:  # Sync generator
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

class AudioBuffer:
    """Handles audio buffering and VAD processing."""
    def __init__(self, sample_rate=16000, chunk_size=512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        # Increase buffer size to ~5 seconds at 16kHz (160 chunks of 512 samples)
        self.buffer = deque(maxlen=160)  
        self.is_speaking = False
        # Adjust silence threshold based on Silero recommendations
        self.silence_threshold = 40  # Number of consecutive silent chunks to consider speech ended
        self.silence_counter = 0
        self.min_speech_duration_ms = 250  # Minimum speech duration in milliseconds
        self.speech_pad_ms = 30  # Padding for speech segments in milliseconds
        
        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Loading Silero VAD model...")
        
        # Initialize Silero VAD using their recommended approach
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        
        self.vad_model = model
        self.get_speech_timestamps = utils[0]
        
        # Move model to GPU if available
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.vad_model.to(self.device)
        
        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] VAD model loaded on {self.device}")
    
    def add_audio(self, audio_chunk: np.ndarray) -> None:
        """Add audio chunk to buffer."""
        # Convert to float32 if not already
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)
        
        # Ensure audio is mono
        if len(audio_chunk.shape) > 1:
            audio_chunk = audio_chunk.mean(axis=1)
        
        # Normalize audio to [-1, 1] range if needed
        if np.abs(audio_chunk).max() > 1.0:
            audio_chunk = audio_chunk / np.abs(audio_chunk).max()
        
        self.buffer.append(audio_chunk)
    
    def check_voice_activity(self) -> bool:
        """Check if voice activity is detected in the current buffer using Silero VAD."""
        if len(self.buffer) < 2:  # Need at least 2 chunks for processing
            return False
        
        # Concatenate buffer chunks
        audio = np.concatenate(list(self.buffer))
        
        # Convert to tensor
        tensor = torch.from_numpy(audio).float()
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)
        
        # Move to same device as model
        tensor = tensor.to(self.device)
        
        # Get speech timestamps
        speech_timestamps = self.get_speech_timestamps(
            tensor,
            self.vad_model,
            threshold=0.5,
            min_speech_duration_ms=self.min_speech_duration_ms,
            speech_pad_ms=self.speech_pad_ms,
            return_seconds=False
        )
        
        # Update speaking state based on timestamps
        if speech_timestamps:
            self.is_speaking = True
            self.silence_counter = 0
        else:
            self.silence_counter += 1
            if self.silence_counter >= self.silence_threshold:
                self.is_speaking = False
        
        return self.is_speaking
    
    def clear(self):
        """Clear the audio buffer."""
        self.buffer.clear()
        self.is_speaking = False
        self.silence_counter = 0
    
    def __del__(self):
        """Cleanup resources."""
        # Clear CUDA cache if using GPU
        if self.device.type == 'cuda':
            torch.cuda.empty_cache()

class VoiceIO:
    """Handles voice input and output operations."""
    def __init__(self):
        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing voice I/O...")
        
        # Initialize Deepgram with v3 SDK
        config = DeepgramClientOptions(
            verbose=False  # Set to True for debug logging
        )
        self.deepgram = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"), config=config)
        
        # Initialize Cartesia
        self.cartesia = Cartesia(api_key=os.getenv("CARTESIA_API_KEY"))
        self.voice_id = os.getenv("CARTESIA_VOICE_ID")
        self.model_id = os.getenv("CARTESIA_MODEL_ID", "sonic-english")
        
        # Initialize PyAudio for output only
        self.pyaudio = pyaudio.PyAudio()
        self.audio_stream = None
        self.sample_rate = 44100  # Cartesia's preferred sample rate
        
        # Add interruption handling
        self.is_interrupted = asyncio.Event()
        self.vad_detected = asyncio.Event()
        self.speaking = asyncio.Event()
        
        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Ready!")

    async def listen(self):
        """Record audio and convert to text using Deepgram's real-time transcription."""
        connection = None
        microphone = None
        try:
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Starting listen operation...")
            
            transcript = []
            is_finished = asyncio.Event()
            has_started = False
            connection_ready = asyncio.Event()
            
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing Deepgram connection...")
            
            # Setup Deepgram streaming configuration
            options = LiveOptions(
                model="nova-2",
                punctuate=True,
                language="en-US",
                encoding="linear16",
                channels=1,
                sample_rate=16000,
                smart_format=True,
                interim_results=True,
                utterance_end_ms="1000",
                vad_events=True
            )

            # Create a connection to Deepgram
            connection = self.deepgram.listen.websocket.v("1")
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Created Deepgram connection")
            
            # Define event handlers
            def on_message(_, result, **kwargs):
                nonlocal has_started
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Received message event: {result}")
                try:
                    if hasattr(result, 'channel') and hasattr(result.channel, 'alternatives'):
                        sentence = result.channel.alternatives[0].transcript
                        if len(sentence) > 0:
                            has_started = True
                            transcript.append(sentence)
                            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Heard: {sentence}")
                            if hasattr(result, 'speech_final') and result.speech_final:
                                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Speech final detected")
                                is_finished.set()
                except Exception as e:
                    print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error in message handler: {e}")

            def on_error(_, error, **kwargs):
                print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error event received: {error}")
                is_finished.set()

            def on_close(_, close, **kwargs):
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Close event received: {close}")
                if has_started:  # Only set finished if we've received some speech
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Setting finished on close (has_started=True)")
                    is_finished.set()
                else:
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Not setting finished on close (has_started=False)")

            def on_metadata(_, metadata, **kwargs):
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Metadata event received: {metadata}")

            def on_utterance_end(_, utterance_end, **kwargs):
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Utterance end event received: {utterance_end}")
                if has_started:  # Only set finished if we've received some speech
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Setting finished on utterance end (has_started=True)")
                    is_finished.set()
                else:
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Not setting finished on utterance end (has_started=False)")

            def on_open(_, open, **kwargs):
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Open event received: {open}")
                connection_ready.set()

            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Registering event handlers...")
            # Register event handlers
            connection.on(LiveTranscriptionEvents.Open, on_open)
            connection.on(LiveTranscriptionEvents.Transcript, on_message)
            connection.on(LiveTranscriptionEvents.Error, on_error)
            connection.on(LiveTranscriptionEvents.Close, on_close)
            connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
            connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)

            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Deepgram connection...")
            # Start the connection with options
            connection.start(options)
            
            # Wait for connection to be ready
            try:
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for connection to be ready...")
                await asyncio.wait_for(connection_ready.wait(), timeout=5.0)
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Deepgram connection ready")
            except asyncio.TimeoutError:
                print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Timeout waiting for connection")
                return None
            
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing microphone...")
            # Create and start microphone
            microphone = Microphone(connection.send)
            
            try:
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Starting microphone...")
                # Start the microphone
                microphone.start()
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Microphone started")
                
                # Wait for speech to complete or timeout
                timeout = 30  # 30 seconds timeout
                try:
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for speech (timeout={timeout}s)...")
                    await asyncio.wait_for(is_finished.wait(), timeout)
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Speech wait completed")
                except asyncio.TimeoutError:
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Listening timeout")
                
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Adding final delay...")
                # Add a small delay to ensure we get the final transcript
                await asyncio.sleep(0.5)
                
                # Only return transcript if we actually heard something
                if has_started and transcript:
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Returning transcript: {' '.join(transcript)}")
                    return " ".join(transcript)
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] No speech detected (has_started={has_started})")
                return None
                
            finally:
                # Clean up microphone
                if microphone:
                    try:
                        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Cleaning up microphone...")
                        microphone.finish()
                        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Microphone cleanup complete")
                    except Exception as e:
                        print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error cleaning up microphone: {e}")
                
                # Clean up connection
                if connection:
                    try:
                        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Cleaning up connection...")
                        connection.finish()  # Don't await the finish call
                        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Connection cleanup complete")
                    except Exception as e:
                        print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error cleaning up connection: {e}")
        
        except Exception as e:
            print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error recording audio: {e}")
            print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error details: {type(e).__name__}: {str(e)}")
            import traceback
            print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Traceback: {traceback.format_exc()}")
            # Ensure cleanup on error
            if microphone:
                try:
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Emergency cleanup of microphone...")
                    microphone.finish()
                except:
                    pass
            if connection:
                try:
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Emergency cleanup of connection...")
                    connection.finish()  # Don't await the finish call
                except:
                    pass
            return None

    async def stream_chunk(self, text: str):
        """Stream a chunk of text as audio using Cartesia."""
        interruption_checker = None  # Define at the start of the method
        try:
            if not text.strip():
                return

            # Set speaking flag
            self.speaking.set()
            
            # Start interruption checker
            interruption_checker = asyncio.create_task(self.check_for_interruption())

            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Generating audio for text of length {len(text)}...")
            
            # Generate audio using Cartesia
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Calling Cartesia TTS with format: pcm_f32le, {self.sample_rate}Hz")
            audio_data = self.cartesia.tts.bytes(
                model_id=self.model_id,
                transcript=text,
                voice_id=self.voice_id,
                output_format={
                    "container": "wav",
                    "encoding": "pcm_f32le",
                    "sample_rate": self.sample_rate,
                }
            )
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Received {len(audio_data)} bytes from Cartesia")
            
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Parsing WAV header...")
            # Parse WAV header to find data chunk
            offset = 12  # Skip RIFF header and chunk size
            while offset < len(audio_data):
                chunk_id = audio_data[offset:offset + 4]
                chunk_size = int.from_bytes(audio_data[offset + 4:offset + 8], 'little')
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Found chunk: {chunk_id}, size: {chunk_size}")
                
                if chunk_id == b'data':
                    data_offset = offset + 8  # Skip chunk ID and size
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Found data chunk at offset {data_offset}")
                    break
                    
                offset += 8 + chunk_size  # Move to next chunk
            else:
                raise ValueError("Could not find data chunk in WAV file")
            
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Converting audio data to numpy array...")
            # Convert audio data to numpy array, skipping WAV header
            audio_array = np.frombuffer(audio_data[data_offset:], dtype=np.float32)
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Converted to numpy array of shape {audio_array.shape}, dtype {audio_array.dtype}")
            
            # Initialize audio stream if needed
            if not self.audio_stream:
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing PyAudio stream...")
                self.audio_stream = self.pyaudio.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.sample_rate,
                    output=True,
                    frames_per_buffer=1024
                )
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] PyAudio stream initialized")
            
            # Calculate chunk size to ensure it's a multiple of 4 (float32 size)
            chunk_size = 1024  # Base chunk size (must be multiple of 4 for float32)
            total_samples = len(audio_array)
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Processing {total_samples} samples in chunks of {chunk_size}")
            
            # Process audio in chunks
            chunks_processed = 0
            for i in range(0, total_samples, chunk_size):
                # Check for interruption
                if self.is_interrupted.is_set():
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Stopping audio due to interruption")
                    break
                
                # Get chunk and ensure it's properly sized
                chunk = audio_array[i:min(i + chunk_size, total_samples)]
                original_chunk_size = len(chunk)
                
                if len(chunk) % 4 != 0:  # Pad the last chunk if needed
                    pad_size = 4 - (len(chunk) % 4)
                    chunk = np.pad(chunk, (0, pad_size), 'constant')
                    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Padded chunk {chunks_processed} from {original_chunk_size} to {len(chunk)} samples")
                
                # Write the chunk to the stream
                try:
                    chunk_bytes = chunk.tobytes()
                    self.audio_stream.write(chunk_bytes, len(chunk))
                    chunks_processed += 1
                except Exception as e:
                    print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error writing chunk {chunks_processed}: {e}")
                    print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Chunk details: size={len(chunk)}, byte_size={len(chunk.tobytes())}")
                    raise
                
                # Small sleep to prevent blocking
                await asyncio.sleep(0.001)
            
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Audio complete - processed {chunks_processed} chunks")
            
        except Exception as e:
            print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error streaming speech chunk: {e}")
            print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error details: {type(e).__name__}: {str(e)}")
            print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Full traceback:")
            import traceback
            print_error(traceback.format_exc())
        finally:
            # Clear flags
            self.speaking.clear()
            if interruption_checker:  # Only cancel if it was created
                interruption_checker.cancel()
                try:
                    await interruption_checker
                except asyncio.CancelledError:
                    pass

    async def check_for_interruption(self):
        """Background task to check for voice activity while speaking."""
        connection = None
        microphone = None
        try:
            # Setup Deepgram streaming configuration for VAD
            options = LiveOptions(
                model="nova-2",
                punctuate=False,  # Don't need punctuation for VAD
                language="en-US",
                encoding="linear16",
                channels=1,
                sample_rate=16000,
                smart_format=True,
                interim_results=False,
                vad_events=True
            )

            # Create a connection to Deepgram
            connection = self.deepgram.listen.websocket.v("1")
            connection_ready = asyncio.Event()
            
            # Define VAD event handlers
            def on_speech_started(event):
                # Add a small delay to verify it's real speech
                async def verify_speech():
                    await asyncio.sleep(0.5)  # Wait 500ms to verify it's not a false positive
                    if self.speaking.is_set():  # Only set interruption if we're still speaking
                        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] VAD detected sustained speech")
                        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Interruption detected!")
                        self.is_interrupted.set()
                    self.vad_detected.set()
                
                # Create task for verification
                asyncio.create_task(verify_speech())

            def on_error(error):
                print_error(f"[{datetime.now().strftime('%H:%M:%S')}] VAD Error: {error}")

            def on_close(close):
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] VAD connection closed: {close}")

            def on_open(open):
                print_system(f"[{datetime.now().strftime('%H:%M:%S')}] VAD connection opened: {open}")
                connection_ready.set()

            # Register event handlers
            connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
            connection.on(LiveTranscriptionEvents.Error, on_error)
            connection.on(LiveTranscriptionEvents.Close, on_close)
            connection.on(LiveTranscriptionEvents.Open, on_open)

            # Start the connection with options
            connection.start(options)
            
            # Wait for connection to be ready
            try:
                await asyncio.wait_for(connection_ready.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Timeout waiting for VAD connection")
                return
            
            # Create and start microphone for VAD
            microphone = Microphone(connection.send)
            microphone.start()
            
            # Keep running until interrupted
            while not self.is_interrupted.is_set():
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error in interruption checker: {e}")
        finally:
            if microphone:
                try:
                    microphone.finish()
                except:
                    pass
            if connection:
                try:
                    connection.finish()
                except:
                    pass

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'audio_stream') and self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
        
        if hasattr(self, 'pyaudio'):
            try:
                self.pyaudio.terminate()
            except:
                pass

class ResponseQueue:
    def __init__(self):
        self.queue = Queue()
        self.is_speaking = False
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.processing = True
        self._stop_event = asyncio.Event()
    
    def add_response(self, text: str):
        """Add a response to the queue"""
        if self.processing:
            self.queue.put(text)
    
    def clear_queue(self):
        """Clear the response queue when interrupted"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                pass
        
    async def process_queue(self, voice_io: VoiceIO):
        """Process responses in the queue"""
        try:
            while self.processing and not self._stop_event.is_set():
                if not self.queue.empty() and not self.is_speaking:
                    self.is_speaking = True
                    text = self.queue.get()
                    
                    try:
                        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Processing response: {text}")
                        await voice_io.stream_chunk(text)
                        
                        # Check if we were interrupted
                        if voice_io.is_interrupted.is_set():
                            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Response interrupted by user")
                            voice_io.is_interrupted.clear()  # Reset interruption flag
                            # Don't break or clear queue, just continue with next response
                            
                    except Exception as e:
                        print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error in audio processing: {e}")
                    finally:
                        self.is_speaking = False
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            print_system("Response queue processing cancelled")
            self.stop()
        except Exception as e:
            print_error(f"Error in queue processing: {e}")
            self.stop()
    
    def stop(self):
        """Stop the queue processor"""
        self.processing = False
        self._stop_event.set()
        # Clear the queue
        self.clear_queue()
    
    async def wait_until_empty(self):
        """Wait until all responses have been spoken"""
        try:
            while not self._stop_event.is_set() and (not self.queue.empty() or self.is_speaking):
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.stop()
    
    def __del__(self):
        """Cleanup resources"""
        self.stop()
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)

async def run_voice_mode(agent_executor, config, runnable_config):
    """Run the agent in voice conversation mode using the voice pipeline."""
    print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Initializing voice pipeline...")
    
    try:
        # Create pipeline credentials
        credentials = PipelineCredentials(
            deepgram_api_key=os.getenv("DEEPGRAM_API_KEY"),
            cartesia_api_key=os.getenv("CARTESIA_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Configure TTS
        tts_config = CartesiaTTSConfig(
            voice_id=os.getenv("CARTESIA_VOICE_ID", ""),
            model_id=os.getenv("CARTESIA_MODEL_ID", "sonic-english"),
            sample_rate=44100,
            num_channels=1
        )
        
        # Configure pipeline
        pipeline_config = PipelineConfig(
            allow_interruptions=True,
            interrupt_speech_duration=0.5,
            interrupt_min_words=3,
            min_endpointing_delay=0.5,
            max_endpointing_delay=6.0,
            preemptive_synthesis=True
        )
        
        # Create pipeline
        pipeline = VoicePipelineFactory.create_pipeline(
            credentials=credentials,
            config=pipeline_config,
            tts_config=tts_config
        )
        
        # Setup pipeline event handlers
        @pipeline.on("user_started_speaking")
        def on_user_start():
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] User started speaking")
            
        @pipeline.on("user_stopped_speaking")
        def on_user_stop():
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] User stopped speaking")
            
        @pipeline.on("agent_started_speaking")
        def on_agent_start():
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Agent started speaking")
            
        @pipeline.on("agent_stopped_speaking")
        def on_agent_stop():
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Agent stopped speaking")
            
        @pipeline.on("user_speech_committed")
        def on_user_commit(message):
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] User: {message.content}")
            
        @pipeline.on("agent_speech_committed")
        def on_agent_commit(message):
            print_ai(f"[{datetime.now().strftime('%H:%M:%S')}] Agent: {message.content}")
            
        @pipeline.on("agent_speech_interrupted")
        def on_interrupt(message):
            print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Speech interrupted")
            
        # Start pipeline
        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Starting voice pipeline...")
        await pipeline.start()
        
        print_system(f"[{datetime.now().strftime('%H:%M:%S')}] Voice mode active. Speak to interact, say 'exit' to end.")
        
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(0.1)
                
        except KeyboardInterrupt:
            print_system(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopping voice pipeline...")
            
        finally:
            # Cleanup
            await pipeline.stop()
            
    except Exception as e:
        print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error in voice mode: {str(e)}")
        print_error(f"[{datetime.now().strftime('%H:%M:%S')}] Error details: {type(e).__name__}: {str(e)}")
        import traceback
        print_error(traceback.format_exc())

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
                                        twitter_state.last_mentigon_id = tweet_id
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
        elif mode == "voice":
            await run_voice_mode(agent_executor=agent_executor, config=config, runnable_config=runnable_config)
    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting Agent...")
    asyncio.run(main())
