import os
import sys
from dotenv import load_dotenv
from datetime import datetime
import time
import json

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# from langchain_nomic.embeddings import NomicEmbeddings
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import SKLearnVectorStore
from langchain.tools import Tool

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
from custom_twitter_actions import create_delete_tweet_tool

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

# Knowledge base setup
urls = [
    "https://docs.prylabs.network/docs/monitoring/checking-status",
]

# Load and process documents
docs = [WebBaseLoader(url).load() for url in urls]
docs_list = [item for sublist in docs for item in sublist]

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=1000, chunk_overlap=200
)
doc_splits = text_splitter.split_documents(docs_list)

vectorstore = SKLearnVectorStore.from_documents(
    documents=doc_splits,
    embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
)

retriever = vectorstore.as_retriever(k=3)

retrieval_tool = Tool(
    name="retrieval_tool",
    description="Useful for retrieving information from the knowledge base about running Ethereum operations.",
    func=retriever.get_relevant_documents
)

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

def initialize_agent():
    """Initialize the agent with CDP Agentkit and Hyperbolic Agentkit."""
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

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

    twitter_api_wrapper = TwitterApiWrapper()
    twitter_toolkit = TwitterToolkit.from_twitter_api_wrapper(twitter_api_wrapper)
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
        retrieval_tool
    ])

        # Add our custom delete tweet tool
    delete_tweet_tool = create_delete_tweet_tool(twitter_api_wrapper)
    tools.append(delete_tweet_tool)
    

    # Add request tools
    toolkit = RequestsToolkit(
        requests_wrapper=TextRequestsWrapper(headers={}),
        allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
    )   
    tools.extend(toolkit.get_tools())

    # Configure memory and agent
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP and Hyperbolic Agentkit Chatbot Example!"}}

    # Load character personality
    with open("characters/chainyoda.character.json") as f:
        character = json.load(f)

    # Extract message examples for behavioral learning
    chat_examples = "\n".join([
        f"User: {exchange[0]['content']['text']}\n"
        f"Response: {exchange[1]['content']['text']}"
        for exchange in character['messageExamples']
    ])

    # Sample representative posts to establish voice
    post_samples = "\n".join(character['postExamples'][:20])  # Take first 20 posts as examples

    personality_context = f"""You are {character['name']}, a highly technical yet approachable AI agent.

    Core Identity:
    Bio: {' '.join(character['bio'])}
    Background: {' '.join(character['lore'])}
    
    Voice & Style Guide:
    1. Communication Rules:
    {' '.join(character['style']['all'])}
    {' '.join(character['style']['chat'])}

    2. Characteristic Speech Patterns:
    - Use short, punchy statements
    - Be technically precise but conversational
    - Maintain a slight irreverence while being helpful
    - Never use emojis or hashtags
    
    3. Example Interactions:
    {chat_examples}

    4. Voice Reference (How you typically express yourself):
    {post_samples}

    Areas of Deep Knowledge: {', '.join(character['topics'][:15])}
    Key Traits: {', '.join(character['adjectives'])}

    Core Capabilities (maintained while expressing personality):
    1. Blockchain Operations (CDP):
    - Onchain interactions via Coinbase Developer Platform
    - Token deployment and wallet management
    - Faucet requests on base-sepolia

    2. Compute Operations (Hyperbolic):
    - GPU resource management
    - Remote server access and control
    - SSH connection handling

    3. System Operations:
    - Internet search functionality
    - Social media integration
    - Connection status monitoring

    Available tools: {', '.join([str((tool.name, tool.description)) for tool in tools])}

    Remember:
    - Keep responses concise and direct
    - Maintain technical accuracy while being conversational
    - Only explain tools when specifically asked
    - Stay true to your irreverent but helpful nature"""

    return create_react_agent(
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=personality_context,
    ), config

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

def run_chat_mode(agent_executor, config):
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
            
            # Use run_with_progress to show activity while processing
            chunks = run_with_progress(
                agent_executor.stream,
                {"messages": [HumanMessage(content=user_input)]},
                config
            )
                
        except KeyboardInterrupt:
            print_system("\nExiting chat mode...")
            break
        except Exception as e:
            print_error(f"Error: {str(e)}")

def run_autonomous_mode(agent_executor, config):
    """Run the agent autonomously with specified intervals."""
    print_system("Starting autonomous mode...")
    twitter_state.load()
    progress = ProgressIndicator()

    while True:
        try:
            if not twitter_state.can_check_mentions():
                wait_time = MENTION_CHECK_INTERVAL - (datetime.now() - twitter_state.last_check_time).total_seconds()
                print_system(f"Waiting {int(wait_time)} seconds before next check...")
                time.sleep(wait_time)
                continue

            print_system("Checking mentions and creating new post...")
            progress.start()
            
            thought = f"""You are an AI agent that both posts original content and replies to mentions.

            Process:
            1. Fetch twitter account information 
            2. Create one new original post first
            3. Then check for new mentions using the twitter_langchain functions
            4. For each mention:
               - Check if tweet_id exists using has_replied_to
               - Only reply if has_replied_to returns False
               - After replying, store tweet_id using add_replied_to


            Current State (stored in SQLite database):
            - Last processed mention ID: {twitter_state.last_mention_id}
            - Only process mentions newer than this ID
            - All replied tweets are tracked in the database
            - Current time: {datetime.now().strftime('%H:%M:%S')}

            Remember:
            - Keep all responses concise and direct
            - Never use emojis or hashtags
            - Be technically precise but conversational
            - Stay true to your irreverent but helpful nature"""

            chunks = run_with_progress(
                agent_executor.stream,
                {"messages": [HumanMessage(content=thought)]},
                config
            )
            
            progress.stop()

            # Process the returned chunks
            for chunk in chunks:
                if "agent" in chunk:
                    response = chunk["agent"]["messages"][0].content
                    print_ai(format_ai_message_content(response))
                    
                    # Handle tool responses
                    if isinstance(response, list):
                        for item in response:
                            if item.get('type') == 'tool_use' and item.get('name') == 'add_replied_to':
                                tweet_id = item['input'].get('__arg1')
                                if tweet_id:
                                    print_system(f"Adding tweet {tweet_id} to database...")
                                    result = twitter_state.add_replied_tweet(tweet_id)
                                    print_system(result)
                                    
                                    # Update state after successful reply
                                    twitter_state.last_mention_id = tweet_id
                                    twitter_state.last_check_time = datetime.now()
                                    twitter_state.save()
            
                elif "tools" in chunk:
                    print_system(chunk["tools"]["messages"][0].content)
                print_system("-------------------")

            print_system(f"Processed mentions. Waiting {MENTION_CHECK_INTERVAL/60} minutes before next check...")
            time.sleep(MENTION_CHECK_INTERVAL)

        except KeyboardInterrupt:
            progress.stop()
            print_system("Saving state and exiting...")
            twitter_state.save()
            sys.exit(0)
        except Exception as e:
            progress.stop()
            print_error(f"Error: {str(e)}")
            print_system("Continuing after error...")
            time.sleep(MENTION_CHECK_INTERVAL)

def main():
    """Start the chatbot agent."""
    agent_executor, config = initialize_agent()
    mode = choose_mode()
    
    if mode == "chat":
        run_chat_mode(agent_executor=agent_executor, config=config)
    elif mode == "auto":
        run_autonomous_mode(agent_executor=agent_executor, config=config)

if __name__ == "__main__":
    print("Starting Agent...")
    main()
