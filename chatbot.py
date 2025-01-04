import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import json
from typing import List, Dict, Any
import random
import asyncio


# Load environment variables from .env file
load_dotenv(override=True)

# Add the parent directory to PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from langchain_core.messages import HumanMessage
# from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# from langchain_nomic.embeddings import NomicEmbeddings
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.requests import TextRequestsWrapper
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_community.document_loaders import WebBaseLoader
# from langchain_community.vectorstores import SKLearnVectorStore
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

# Constants
ALLOW_DANGEROUS_REQUEST = True  # Set to False in production for security
wallet_data_file = "wallet_data.txt"


# Create TwitterState instance
twitter_state = TwitterState()

# Create tools for Twitter state management
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

# # Knowledge base setup
# urls = [
#     "https://docs.prylabs.network/docs/monitoring/checking-status",
# ]

# # Load and process documents
# docs = [WebBaseLoader(url).load() for url in urls]
# docs_list = [item for sublist in docs for item in sublist]

# text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
#     chunk_size=1000, chunk_overlap=200
# )
# doc_splits = text_splitter.split_documents(docs_list)

# vectorstore = SKLearnVectorStore.from_documents(
#     documents=doc_splits,
#     embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
# )

# retriever = vectorstore.as_retriever(k=3)

# retrieval_tool = Tool(
#     name="retrieval_tool",
#     description="Useful for retrieving information from the knowledge base about running Ethereum operations.",
#     func=retriever.get_relevant_documents
# )

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
    
    # Format bio and lore
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

    # Randomly select 10 post examples
    all_posts = character.get('postExamples', [])
    selected_posts = random.sample(all_posts, min(10, len(all_posts)))
    
    post_examples = "\n".join([
        f"Example {i+1}: {post}"
        for i, post in enumerate(selected_posts)
        if isinstance(post, str) and post.strip()
    ])
    
    # Compile personality prompt
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

        Before responding to any input, analyze the situation and plan your response in <response_planning> tags:
        1. Determine if the input is a mention or a regular message
        2. Identify the specific topic or context of the input
        3. List relevant character traits and knowledge that apply to the current situation:
        - Specify traits from the character bio that are relevant
        - Note any lore or knowledge that directly applies
        4. Consider potential tool usage:
        - Identify which tools might be needed
        - List required parameters for each tool and check if they're available in the input
        5. Plan the response:
        - Outline key points to include
        - Decide on an appropriate length and style (one-liner, longer insight, or bullet points)
        - Consider whether an emoji is appropriate for this specific response
        - Ensure the planned response aligns with the character's persona and style guidelines
        6. If interacting with KOLs:
        a. Plan to find their user IDs using get_user_id_tool
        b. Plan to retrieve their recent tweets using user_tweets_tool
        c. Ensure your planned response will be directly relevant to their tweet
        d. Plan to check if you have already replied using has_replied_to
        e. If you haven't replied, plan to use reply_to_tweet; otherwise, choose a different tweet
        f. Plan to use add_replied_to after replying to store the tweet ID
        7. Draft and refine the response:
        - Write out a draft of the response
        - Check that it meets all guidelines (character limit, relevance, style, etc.)
        - Adjust the response if necessary to meet all requirements

        After your analysis, provide your response in <response> tags.

        Example output structure:

        <response_planning>
        [Your detailed analysis of the situation and planning of the response]
        </response_planning>

        <response>
        [Your character's response, ensuring it adheres to the guidelines]
        </response>

        Remember:
        - If you're asked about current information and hit a rate limit on web_search, do not reply and wait until the next mention check.
        - When interacting with KOLs, ensure you're responding to their most recent tweets and maintaining your character's persona.
        - Always verify that you have all required parameters before calling any tools.
        - Vary your tweet length and style based on the context and importance of the message.
        - Use emojis naturally and sparingly, not in every tweet.
        - Double-check the word count of your response and adjust if necessary to meet the character limit.
        """

    print_system(personality)

    return personality



async def initialize_agent():
    """Initialize the agent with CDP Agentkit and Hyperbolic Agentkit."""
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

        # Create config first before using it
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
                "kol_list": character.get("kol_list", [])
            }
        }

        print_system("Initializing Twitter API wrapper...")
        twitter_api_wrapper = TwitterApiWrapper()
        twitter_toolkit = TwitterToolkit.from_twitter_api_wrapper(twitter_api_wrapper)
        
        
        print_system("Initializing knowledge base...")
        try:
            knowledge_base = TweetKnowledgeBase()
            stats = knowledge_base.get_collection_stats()
            print_system(f"Initial knowledge base stats: {stats}")
            print_system("Knowledge base initialized successfully")
        except Exception as e:
            print_error(f"Error initializing knowledge base: {e}")
            raise

        # Ask user about knowledge base update
        if config['character'].get('kol_list'):
            # First ask if they want to clear the existing knowledge base
            while True:
                clear_choice = input("\nDo you want to clear the existing knowledge base? (y/n): ").lower().strip()
                if clear_choice in ['y', 'n']:
                    break
                print("Invalid choice. Please enter 'y' or 'n'.")

            if clear_choice == 'y':
                knowledge_base.clear_collection()
                stats = knowledge_base.get_collection_stats()
                print_system(f"Knowledge base stats after clearing: {stats}")

            # Then ask about updating
            while True:
                update_choice = input("\nDo you want to update the knowledge base with KOL tweets? (y/n): ").lower().strip()
                if update_choice in ['y', 'n']:
                    break
                print("Invalid choice. Please enter 'y' or 'n'.")

            if update_choice == 'y':
                print_system("Updating knowledge base with KOL tweets...")
                try:
                    await update_knowledge_base(twitter_api_wrapper, knowledge_base, config['character']['kol_list'])
                    stats = knowledge_base.get_collection_stats()
                    print_system(f"Updated knowledge base stats: {stats}")
                    print_system("Knowledge base updated successfully")
                except Exception as e:
                    print_error(f"Error updating knowledge base: {e}")
                    print_error(f"Error type: {type(e).__name__}")
                    if hasattr(e, '__traceback__'):
                        import traceback
                        traceback.print_exception(type(e), e, e.__traceback__)
                    raise
            else:
                print_system("Skipping knowledge base update...")

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

        # Initialize toolkits and get tools
        cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
        tools = cdp_toolkit.get_tools()

        hyperbolic_agentkit = HyperbolicAgentkitWrapper()
        hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic_agentkit)
        tools.extend(hyperbolic_toolkit.get_tools())

        tools.extend(twitter_toolkit.get_tools())

        
        # Create deploy multi-token tool
        deployMultiTokenTool = CdpTool(
            name="deploy_multi_token",
            description=DEPLOY_MULTITOKEN_PROMPT,
            cdp_agentkit_wrapper=agentkit,
            args_schema=DeployMultiTokenInput,
            func=deploy_multi_token,
        )

        # Add additional tools
        tools.extend([
            deployMultiTokenTool,
            DuckDuckGoSearchRun(
                name="web_search",
                description="Search the internet for current information."
            ),
            check_replied_tool,
            add_replied_tool,
            check_reposted_tool,
            add_reposted_tool,
            # retrieval_tool
        ])

        # Add our custom delete tweet tool
        delete_tweet_tool = create_delete_tweet_tool(twitter_api_wrapper)
        get_user_id_tool = create_get_user_id_tool(twitter_api_wrapper)
        user_tweets_tool = create_get_user_tweets_tool(twitter_api_wrapper)
        retweet_tool = create_retweet_tool(twitter_api_wrapper)
        tools.extend([delete_tweet_tool, get_user_id_tool, user_tweets_tool, retweet_tool])

        # Add request tools
        toolkit = RequestsToolkit(
            requests_wrapper=TextRequestsWrapper(headers={}),
            allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
        )   
        tools.extend(toolkit.get_tools())

        memory = MemorySaver()

        # Create knowledge base query tool
        query_kb_tool = Tool(
            name="query_knowledge_base",
            func=lambda query: knowledge_base.format_query_results(
                knowledge_base.query_knowledge_base(query)
            ),
            description="Query the knowledge base for relevant tweets about crypto/AI/tech trends. Input should be a search query string."
        )
        
        # Add knowledge base tool to tools list
        tools.extend([query_kb_tool])

        # Create the runnable config with increased recursion limit
        runnable_config = RunnableConfig(recursion_limit=200)

        return create_react_agent(
            llm,
            tools=tools,
            checkpointer=memory,
            state_modifier=personality,
        ), config, runnable_config

    except Exception as e:
        print_error(f"Error initializing agent: {e}")
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

def run_with_progress(func, *args, **kwargs):
    """Run a function while showing a progress indicator between outputs."""
    progress = ProgressIndicator()
    
    try:
        generator = func(*args, **kwargs)
        for chunk in generator:
            progress.stop()  # Stop spinner before output
            yield chunk     # Yield the chunk immediately
            progress.start()  # Restart spinner while waiting for next chunk
            
    finally:
        progress.stop()

def run_chat_mode(agent_executor, config, runnable_config):
    """Run the agent interactively based on user input."""
    print_system("Starting chat mode... Type 'exit' to end.")
    print_system("Commands:")
    print_system("  exit     - Exit the chat")
    print_system("  status   - Check if agent is responsive")
    
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
            
            # Process chunks as they arrive
            for chunk in run_with_progress(
                agent_executor.stream,
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

def run_autonomous_mode(agent_executor, config, runnable_config):
    """Run the agent autonomously with specified intervals."""
    print_system(f"Starting autonomous mode as {config['character']['name']}...")
    twitter_state.load()
    progress = ProgressIndicator()
    
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
        retry_count = 0
        try:
            if not twitter_state.can_check_mentions():
                wait_time = max(MENTION_CHECK_INTERVAL - (datetime.now() - twitter_state.last_check_time).total_seconds(), 0)
                if wait_time > 0:
                    print_system(f"Waiting {int(wait_time)} seconds before next check...")
                    time.sleep(wait_time)
                    continue

            # Update last_check_time at the start of each check
            twitter_state.last_check_time = datetime.now()
            twitter_state.save()

            print_system("Checking for new mentions and creating new post...")
            
            selected_kol_for_reply = random.choice(config['character']['kol_list'])
            selected_kol_for_retweet = random.choice(config['character']['kol_list'])

            print_system(f"Selected KOL for reply: {selected_kol_for_reply}")
            print_system(f"Selected KOL for retweet: {selected_kol_for_retweet}")
            
            thought = f"""
            You are an AI-powered Twitter bot specializing in blockchain and cryptocurrency. Your tasks are to create engaging original tweets, respond to mentions, and interact with key opinion leaders (KOLs) in the industry. Here's the essential information for your operation:

            <selected_kol_for_reply>
            {selected_kol_for_reply}
            </selected_kol_for_reply>

            <selected_kol_for_retweet>
            {selected_kol_for_retweet}
            </selected_kol_for_retweet>

            <mention_check_interval>
            {MENTION_CHECK_INTERVAL}
            </mention_check_interval>

            <last_mention_id>
            {twitter_state.last_mention_id}
            </last_mention_id>

            <current_time>
            {datetime.now().strftime('%H:%M:%S')}
            </current_time>

            Your main objectives are to be completed in the following order:

            1. Retrieve your own account ID.
            2. Check for and reply to new Twitter mentions.
            3. Interact with the selected KOL for reply by replying to their most recent post.
            4. Interact with the selected KOL for retweet by retweeting their most relevant recent tweet.
            5. Create an original, engaging tweet by querying the knowledge base for current trends and insights, and then creating a tweet based on the insights.

            Guidelines:

            1. Character limits:
            - Ideal: Less than 60 characters
            - Maximum: 280 characters
            2. Format: Single-line responses only
            3. Emoji usage: Prefer no emojis, only use one if it is directly relevant to the tweet

            Important rules:

            1. Process tasks sequentially as outlined above.
            2. Only process mentions newer than the last processed mention ID.
            3. Before replying to any mention, use the has_replied_to function to check if you've already responded.
            4. Only reply if has_replied_to returns False.
            5. After a successful reply, use the add_replied_tweet function to store the tweet_id in the database.
            6. Verify tweet relevance against your approved topics list (blockchain and cryptocurrency).
            7. Do not create multi-part responses or threads.
            8. Always interact with the provided KOLs, ensuring your response matches their topic.
            9. Avoid unnecessary thought processes to prevent recursion errors.

            Available functions:

            1. account_details(): Get the account ID to monitor
            2. create_tweet(content: str): Post a new tweet
            3. get_mentions(): Retrieve new mentions
            4. reply_to_tweet(tweet_id: str, content: str): Reply to a specific tweet
            5. has_replied_to(tweet_id: str): Check if a tweet has been replied to
            6. add_replied_tweet(tweet_id: str): Mark a tweet as replied
            7. has_reposted(tweet_id: str): Check if a tweet has been reposted
            8. add_reposted(tweet_id: str): Mark a tweet as reposted
            9. query_knowledge_base(query: str): Get relevant tweets about current trends

            Before creating an original tweet:
            1. Query the knowledge base using query_knowledge_base tool for:
            - Most prominent topics being discussed within the knowledge base
            - Latest crypto trends and developments
            - Recent AI advancements and discussions
            - Current tech industry updates
            2. Analyze the returned tweets for emerging trends and discussions.
            3. Create content that incorporates these insights while maintaining your unique voice.
            4. Reference specific trends without direct quotes.

            When creating tweets or replying to mentions:

            1. Stay in character with consistent personality traits.
            2. Ensure relevance to the tweet content and match approved topics.
            3. Be friendly, witty, funny, and engaging.
            4. Share interesting insights or thought-provoking perspectives when relevant.
            5. Ask follow-up questions to encourage discussion when appropriate.
            6. Adhere to the character limit and style guidelines.

            Your output should be structured as follows:

            <account_id>
            [Your account ID retrieved using the account_details() function]
            </account_id>

            <knowledge_base_query>
            [Your knowledge base query results and insights used]
            </knowledge_base_query>

            <mention_replies>
            [Your replies to any new mentions, if applicable]
            </mention_replies>

            <kol_reply>
            [Your reply to the selected KOL's most recent post]
            </kol_reply>

            <kol_retweet>
            [The tweet ID of the selected KOL's most relevant tweet that you've retweeted]
            </kol_retweet>

            <original_tweet>
            [Content for a new tweet]
            </original_tweet>

            Remember to process all tasks sequentially and use the provided functions as needed. Always interact with the provided KOLs, as there will always be one to engage with for each interaction type. Ensure to avoid unnecessary thought processes to prevent recursion errors. 

            You may now begin your tasks.
            """

            # Process chunks as they arrive (only once)
            for chunk in run_with_progress(
                agent_executor.stream,
                {"messages": [HumanMessage(content=thought)]},
                runnable_config
            ):
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
                                        twitter_state.last_mention_id = tweet_id
                                        twitter_state.last_check_time = datetime.now()
                                        twitter_state.save()
                                
                                elif item.get('name') == 'add_reposted':
                                    tweet_id = item['input'].get('__arg1')
                                    if tweet_id:
                                        print_system(f"Adding tweet {tweet_id} to reposted database...")
                                        result = twitter_state.add_reposted_tweet(tweet_id)
                                        print_system(result)
                
                elif "tools" in chunk:
                    print_system(chunk["tools"]["messages"][0].content)
                print_system("-------------------")

            print_system(f"Completed cycle. Waiting {MENTION_CHECK_INTERVAL/60} minutes before next check...")
            time.sleep(MENTION_CHECK_INTERVAL)

        except KeyboardInterrupt:
            print_system("\nSaving state and exiting...")
            twitter_state.save()
            sys.exit(0)
            
        except AgentExecutionError as e:
            print_error(f"Agent execution failed: {str(e)}")
            print_system("Skipping current cycle and continuing...")
            time.sleep(MENTION_CHECK_INTERVAL)
            
        except Exception as e:
            print_error(f"Unexpected error: {str(e)}")
            print_error(f"Error type: {type(e).__name__}")
            print_error(f"Error details: {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                print_error("Traceback:")
                traceback.print_tb(e.__traceback__)
            
            print_system("Continuing after error...")
            time.sleep(MENTION_CHECK_INTERVAL)

async def main():
    """Start the chatbot agent."""
    try:
        agent_executor, config, runnable_config = await initialize_agent()
        mode = choose_mode()
        
        if mode == "chat":
            run_chat_mode(agent_executor=agent_executor, config=config, runnable_config=runnable_config)
        elif mode == "auto":
            run_autonomous_mode(agent_executor=agent_executor, config=config, runnable_config=runnable_config)
    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting Agent...")
    asyncio.run(main())
