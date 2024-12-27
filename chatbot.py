import os
import sys
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import sqlite3

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to PYTHONPATH so Python can find the hyperbolic packages
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import time
import threading
from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.tools import DuckDuckGoSearchRun

from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.requests import TextRequestsWrapper

ALLOW_DANGEROUS_REQUEST = True  # Set to False in production for security

toolkit = RequestsToolkit(
    requests_wrapper=TextRequestsWrapper(headers={}),
    allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
)

# Import CDP Agentkit Langchain Extension.
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool
from pydantic import BaseModel, Field
from cdp import Wallet

# Import Hyperbolic Agentkit Langchain Extension
from hyperbolic_langchain.agent_toolkits import HyperbolicToolkit
from hyperbolic_langchain.utils import HyperbolicAgentkitWrapper

from twitter_langchain import (TwitterApiWrapper, TwitterToolkit)
from custom_twitter_actions import create_delete_tweet_tool
from hyperbolic_agentkit_core.actions.remote_shell import RemoteShellAction


from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import SKLearnVectorStore
from langchain_nomic.embeddings import NomicEmbeddings
from langchain.tools import Tool

urls = [
    "https://docs.prylabs.network/docs/monitoring/checking-status",
]

# Load documents
docs = [WebBaseLoader(url).load() for url in urls]
docs_list = [item for sublist in docs for item in sublist]

# Split documents
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=1000, chunk_overlap=200
)
doc_splits = text_splitter.split_documents(docs_list)

# Add to vectorDB
vectorstore = SKLearnVectorStore.from_documents(
    documents=doc_splits,
    embedding=NomicEmbeddings(model="nomic-embed-text-v1.5", inference_mode="local"),
)

# Create retriever
retriever = vectorstore.as_retriever(k=3)

# Create a retrieval tool
retrieval_tool = Tool(
    name="retrieval_tool",
    description="Useful for retrieving information from the knowledge base about running Ethereum operations.",
    func=retriever.get_relevant_documents
)

# Configure a file to persist the agent's CDP MPC Wallet Data.
wallet_data_file = "wallet_data.txt"

DEPLOY_MULTITOKEN_PROMPT = """
This tool deploys a new multi-token contract with a specified base URI for token metadata.
The base URI should be a template URL containing {id} which will be replaced with the token ID.
For example: 'https://example.com/metadata/{id}.json'
"""


class DeployMultiTokenInput(BaseModel):
    """Input argument schema for deploy multi-token contract action."""
    base_uri: str = Field(
        ...,
        description=
        "The base URI template for token metadata. Must contain {id} placeholder.",
        example="https://example.com/metadata/{id}.json")


def deploy_multi_token(wallet: Wallet, base_uri: str) -> str:
    """Deploy a new multi-token contract with the specified base URI.

    Args:
        wallet (Wallet): The wallet to deploy the contract from.
        base_uri (str): The base URI template for token metadata. Must contain {id} placeholder.

    Returns:
        str: A message confirming deployment with the contract address.
    """
    # Validate that the base_uri contains the {id} placeholder
    if "{id}" not in base_uri:
        raise ValueError("base_uri must contain {id} placeholder")

    # Deploy the contract
    deployed_contract = wallet.deploy_multi_token(base_uri)
    result = deployed_contract.wait()

    return f"Successfully deployed multi-token contract at address: {result.contract_address}"


def initialize_agent():
    """Initialize the agent with CDP Agentkit and Hyperbolic Agentkit."""
    # Initialize LLM.
    # llm = ChatOpenAI(model="gpt-4o")
    # llm = ChatOpenAI(model="Qwen/Qwen2.5-Coder-32B-Instruct", base_url="https://api.hyperbolic.xyz/v1", api_key=os.getenv("HYPERBOLIC_API_KEY"))
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")

    wallet_data = None

    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    # Configure CDP Agentkit Langchain Extension.
    values = {}
    if wallet_data is not None:
        # If there is a persisted agentic wallet, load it and pass to the CDP Agentkit Wrapper.
        values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # persist the agent's CDP MPC Wallet Data.
    wallet_data = agentkit.export_wallet()
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data)

    # Initialize CDP Agentkit Toolkit and get tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = cdp_toolkit.get_tools()

    # Initialize Hyperbolic Agentkit Toolkit and get tools.
    hyperbolic_agentkit = HyperbolicAgentkitWrapper()
    hyperbolic_toolkit = HyperbolicToolkit.from_hyperbolic_agentkit_wrapper(hyperbolic_agentkit)
    tools.extend(hyperbolic_toolkit.get_tools())

    twitter_api_wrapper = TwitterApiWrapper()
    twitter_toolkit = TwitterToolkit.from_twitter_api_wrapper(
        twitter_api_wrapper)
    tools.extend(twitter_toolkit.get_tools())

    # Add our custom delete tweet tool
    delete_tweet_tool = create_delete_tweet_tool(twitter_api_wrapper)
    tools.append(delete_tweet_tool)
    
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
            description="Search the internet for current information. Use this when you need to find up-to-date information or verify facts."
        )])
    
    # browser = create_sync_playwright_browser()
    # tools.extend(PlayWrightBrowserToolkit.from_browser(sync_browser=browser).get_tools())
    toolkit = RequestsToolkit(
        requests_wrapper=TextRequestsWrapper(headers={}),
        allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
    )   
    tools.extend(toolkit.get_tools())

    tools.append(retrieval_tool)

    # Store buffered conversation history in memory.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP and Hyperbolic Agentkit Chatbot Example!"}}



    # Create ReAct Agent using the LLM and all tools.
    return create_react_agent(
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=
        f"""You are an autonomous agent that have your independent identity and can interact with multiple platforms and services:

        1. Blockchain Operations (via CDP):
        - Interact onchain via Coinbase Developer Platform
        - Deploy your own tokens and manage your wallets
        - Request funds from faucet on network ID `base-sepolia`

        2. Compute Operations (via Hyperbolic):
        - Rent compute resources
        - Check your GPU status and availability
        - Connect to your remote servers via SSH (use ssh_connect)
        - Execute commands on remote server (use remote_shell)

        3. System Operations:
        - Use 'ssh_status' to check current SSH connection
        - Search the internet for current information
        - Post your updates on X (Twitter)
    
        Extra available tools:
        {', '.join([str((tool.name, tool.description)) for tool in tools])}

        Be concise and helpful. Only describe your tools when explicitly asked.""",
    ), config


class CommandTimeout(Exception):
    """Exception raised when a command execution times out."""
    pass

# ANSI color codes
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"

def print_ai(text):
    """Print AI responses in green."""
    print(f"{Colors.GREEN}{text}{Colors.ENDC}")

def print_system(text):
    """Print system messages in yellow."""
    print(f"{Colors.YELLOW}{text}{Colors.ENDC}")

def print_error(text):
    """Print error messages in red."""
    print(f"{Colors.RED}{text}{Colors.ENDC}")

class ProgressIndicator:
    def __init__(self):
        self.animation = "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁"
        self.idx = 0
        self._stop_event = threading.Event()
        self._thread = None
        
    def _animate(self):
        """Animation loop running in separate thread."""
        while not self._stop_event.is_set():
            print(f"\r{Colors.YELLOW}Processing {self.animation[self.idx]}{Colors.ENDC}", end="", flush=True)
            self.idx = (self.idx + 1) % len(self.animation)
            time.sleep(0.2)  # Update every 0.2 seconds
            
    def start(self):
        """Start the progress animation in a separate thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._animate)
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        """Stop the progress animation."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()
            print("\r" + " " * 50 + "\r", end="", flush=True)  # Clear the line

def run_with_progress(func, *args, **kwargs):
    """Run a function while showing a progress indicator."""
    progress = ProgressIndicator()
    
    try:
        progress.start()
        generator = func(*args, **kwargs)
        chunks = []
        
        for chunk in generator:
            progress.stop()
            
            if "agent" in chunk:
                print(f"\n{Colors.GREEN}{chunk['agent']['messages'][0].content}{Colors.ENDC}")
            elif "tools" in chunk:
                print(f"\n{Colors.YELLOW}{chunk['tools']['messages'][0].content}{Colors.ENDC}")
            print(f"\n{Colors.YELLOW}-------------------{Colors.ENDC}")
            
            chunks.append(chunk)
            progress.start()
        
        return chunks
    finally:
        progress.stop()


def format_ai_message_content(content, additional_kwargs=None):
    """Format AI message content based on its type."""
    formatted_parts = []
    
    # Handle text content
    if isinstance(content, list):
        # Handle Claude-style messages
        text_parts = [f"{Colors.GREEN}{item['text']}{Colors.ENDC}" 
                     for item in content if item.get('type') == 'text' and 'text' in item]
        if text_parts:
            formatted_parts.extend(text_parts)
        tool_uses = [item for item in content if item.get('type') == 'tool_use']
        for tool_use in tool_uses:
            formatted_parts.append(f"{Colors.MAGENTA}Tool Call: {tool_use['name']}({tool_use['input']}){Colors.ENDC}")
        
    elif isinstance(content, str):
        # Handle GPT-style messages
        if content:
            formatted_parts.append(f"{Colors.GREEN}{content}{Colors.ENDC}")
        if additional_kwargs and 'tool_calls' in additional_kwargs:
            for tool_call in additional_kwargs['tool_calls']:
                formatted_parts.append(
                    f"{Colors.MAGENTA}Tool Call: {tool_call['function']['name']}({tool_call['function']['arguments']}){Colors.ENDC}"
                )    
    
    return '\n'.join(formatted_parts) if formatted_parts else str(content)

def run_chat_mode(agent_executor, config):
    """Run the agent interactively based on user input."""
    print_system("Starting chat mode... Type 'exit' to end.")
    print_system("Commands:")
    print_system("  exit     - Exit the chat")
    print_system("  status   - Check if agent is responsive")
    
    while True:
        try:
            # Simple input handling without readline
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
            
            try:
                progress = ProgressIndicator()
                progress.start()
                
                for chunk in agent_executor.stream(
                    {"messages": [HumanMessage(content=user_input)]},
                    config
                ):
                    progress.stop()
                    if "agent" in chunk:
                        message = chunk['agent']['messages'][0]
                        formatted_content = format_ai_message_content(
                            message.content,
                            message.additional_kwargs
                        )
                        if formatted_content:
                            print(formatted_content)  # No need for color wrapping here
                    elif "tools" in chunk:
                        print(f"{Colors.YELLOW}{chunk['tools']['messages'][0].content}{Colors.ENDC}")
                    progress.start()
                
                progress.stop()
                print_system(f"Completed at: {datetime.now().strftime('%H:%M:%S')}")
                
            except Exception as e:
                print_error(f"\nError: {str(e)}")
                print_system("The agent encountered an error but is still running.")
            
        except KeyboardInterrupt:
            print_system("\nOperation interrupted by user")
            choice = input(f"{Colors.YELLOW}Do you want to exit? (y/N): {Colors.ENDC}")
            if choice.lower() == 'y':
                print_system("Goodbye Agent!")
                sys.exit(0)
            print_system("Continuing...")
            continue


# Add these constants near the top of the file
# TWITTER_ACCOUNT_ID = "1704150815886225408"  # static account ID for dealing with rate limits
MENTION_CHECK_INTERVAL = 15 * 60  # 15 minutes in seconds
MAX_MENTIONS_PER_INTERVAL = 50  # Adjust based on your API tier limits

class TwitterState:
    def __init__(self):
        # self.account_id = TWITTER_ACCOUNT_ID
        self.last_mention_id = None
        self.last_check_time = None
        self.mentions_count = 0
        self.reset_time = None
        self._init_db()
        
    def _init_db(self):
        """Initialize SQLite database for state and replied tweets."""
        with sqlite3.connect('twitter_state.db') as conn:
            # Create replied tweets table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS replied_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create state table for other Twitter state data
            conn.execute('''
                CREATE TABLE IF NOT EXISTS twitter_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            conn.execute('CREATE INDEX IF NOT EXISTS idx_replied_at ON replied_tweets(replied_at)')
    
    def load(self):
        """Load state from SQLite database."""
        with sqlite3.connect('twitter_state.db') as conn:
            cursor = conn.execute('SELECT key, value FROM twitter_state')
            for key, value in cursor.fetchall():
                if key == 'last_mention_id':
                    self.last_mention_id = value
                elif key == 'last_check_time':
                    self.last_check_time = datetime.fromisoformat(value) if value else None
                elif key == 'reset_time':
                    self.reset_time = datetime.fromisoformat(value) if value else None
                elif key == 'mentions_count':
                    self.mentions_count = int(value)

    def save(self):
        """Save state to SQLite database."""
        with sqlite3.connect('twitter_state.db') as conn:
            state_data = {
                'last_mention_id': self.last_mention_id,
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'mentions_count': str(self.mentions_count),
                'reset_time': self.reset_time.isoformat() if self.reset_time else None
            }
            
            for key, value in state_data.items():
                conn.execute('''
                    INSERT OR REPLACE INTO twitter_state (key, value) 
                    VALUES (?, ?)
                ''', (key, value))

    def add_replied_tweet(self, tweet_id):
        """Add a tweet ID to the database of replied tweets."""
        with sqlite3.connect('twitter_state.db') as conn:
            conn.execute('INSERT OR REPLACE INTO replied_tweets (tweet_id) VALUES (?)', (tweet_id,))
            # Clean up old tweets (older than 30 days)
            conn.execute('DELETE FROM replied_tweets WHERE replied_at < ?', 
                       (datetime.now() - timedelta(days=30),))

    def has_replied_to(self, tweet_id):
        """Check if we've already replied to this tweet."""
        with sqlite3.connect('twitter_state.db') as conn:
            cursor = conn.execute('SELECT 1 FROM replied_tweets WHERE tweet_id = ?', (tweet_id,))
            return cursor.fetchone() is not None

    def can_check_mentions(self):
        """Check if enough time has passed since last mention check."""
        if not self.last_check_time:
            return True
        
        time_since_last_check = (datetime.now() - self.last_check_time).total_seconds()
        return time_since_last_check >= MENTION_CHECK_INTERVAL

    def update_rate_limit(self):
        """Update and check rate limits."""
        now = datetime.now()
        if not self.reset_time or now >= self.reset_time:
            self.mentions_count = 0
            self.reset_time = now + timedelta(minutes=15)
        
        self.mentions_count += 1
        return self.mentions_count <= MAX_MENTIONS_PER_INTERVAL

# Modify the run_autonomous_mode function
def run_autonomous_mode(agent_executor, config, interval=10):
    """Run the agent autonomously with specified intervals."""
    print_system("Starting autonomous mode...")
    twitter_state = TwitterState()
    twitter_state.load()

    while True:
        try:
            if not twitter_state.can_check_mentions():
                wait_time = MENTION_CHECK_INTERVAL - (datetime.now() - twitter_state.last_check_time).total_seconds()
                print_system(f"Waiting {int(wait_time)} seconds before next mention check...")
                time.sleep(wait_time)
                continue

            if not twitter_state.update_rate_limit():
                print_system("Rate limit reached. Waiting for reset...")
                time.sleep((twitter_state.reset_time - datetime.now()).total_seconds())
                continue

            # Update the autonomous thought to include state information and replied tweets handling
            thought = f"""You are an AI-powered Twitter bot designed to automatically scan for and reply to mentions using Twitter LangChain resources.
            
            Current State (stored in SQLite database):
            - Account ID to monitor: {twitter_state.account_id}
            - Last processed mention ID: {twitter_state.last_mention_id}
            - Only process mentions newer than this ID
            - All replied tweets are tracked in the SQLite database
            - IMPORTANT: After checking mentions, wait 15 minutes before checking again to respect API limits
            - Current time: {datetime.now().strftime('%H:%M:%S')}

            Before replying to any mention:
            1. Query the SQLite database to check if tweet_id exists using has_replied_to
            2. Only proceed with reply if has_replied_to returns False
            3. After successful reply, store the tweet_id in the database using add_replied_tweet

            Personality Guidelines:
            - Be friendly, witty, and engaging in your responses
            - Share interesting insights or thought-provoking perspectives when relevant
            - Use emojis occasionally to add personality (but don't overdo it)
            - Feel free to ask follow-up questions to encourage discussion
            - When appropriate, share relevant facts or insights about AI, blockchain, or technology

            Always sign your replies with:
            "🤖 - Your AI friend via @hyperbolic_labs & @LangChainAI"
            """

            # Run agent in autonomous mode
            for chunk in agent_executor.stream({"messages": [HumanMessage(content=thought)]}, config):
                if "agent" in chunk:
                    response = chunk["agent"]["messages"][0].content
                    print_ai(response)
                    
                    # Update state if mentions were processed
                    if "mention_id" in response:
                        twitter_state.last_mention_id = response["mention_id"]
                        twitter_state.last_check_time = datetime.now()
                        twitter_state.save()
                        
                elif "tools" in chunk:
                    print_system(chunk["tools"]["messages"][0].content)
                print_system("-------------------")

            # Force wait after processing mentions
            print_system(f"Processed mentions. Waiting {MENTION_CHECK_INTERVAL/60} minutes before next check...")
            time.sleep(MENTION_CHECK_INTERVAL)

        except KeyboardInterrupt:
            print_system("Saving state and exiting...")
            twitter_state.save()
            sys.exit(0)


# Mode Selection
def choose_mode():
    """Choose whether to run in autonomous or chat mode based on user input."""
    while True:
        print("\nAvailable modes:")
        print("1. chat    - Interactive chat mode")
        print("2. auto    - Autonomous action mode")

        choice = input(
            "\nChoose a mode (enter number or name): ").lower().strip()
        if choice in ["1", "chat"]:
            return "chat"
        elif choice in ["2", "auto"]:
            return "auto"
        print("Invalid choice. Please try again.")


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
