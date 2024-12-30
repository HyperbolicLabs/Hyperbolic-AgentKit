import os
import sys
from dotenv import load_dotenv
from datetime import datetime
import time
import json
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pickle
import random


os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Load environment variables from .env file
load_dotenv(override=True)

# Add the parent directory to PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_nomic.embeddings import NomicEmbeddings
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
MENTION_CHECK_INTERVAL = 600  # 10 minutes in seconds (changed from 900)

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
    embedding=NomicEmbeddings(model="nomic-embed-text-v1.5", inference_mode="local"),
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
    
    # Initialize post generator with specific character file
    print_system("Loading cached embeddings for chainyoda.character...")
    progress = ProgressIndicator()
    progress.start()
    post_generator = CharacterPostGenerator("characters/chainyoda.character.json")
    progress.stop()

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

    # Add Twitter tools
    twitter_api_wrapper = TwitterApiWrapper()
    twitter_toolkit = TwitterToolkit.from_twitter_api_wrapper(twitter_api_wrapper)
    tools.extend(twitter_toolkit.get_tools())
    
    # Add custom Twitter tools
    delete_tweet_tool = create_delete_tweet_tool(twitter_api_wrapper)
    tools.append(delete_tweet_tool)

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

    # Load character personalities from both files
    try:
        # Load base character file
        try:
            with open("characters/chainyoda.json") as f:
                base_character = json.load(f)
        except Exception as e:
            print_error(f"Error loading base character file: {e}")
            raise

        # Load character behavior file
        try:
            with open("characters/chainyoda.character.json") as f:
                character_behavior = json.load(f)
        except Exception as e:
            print_error(f"Error loading character behavior file: {e}")
            raise

        # Merge and process character data
        try:
            character = {**base_character, **character_behavior}
            chat_examples = "\n".join([
                f"Example {i+1}:\n{example}" 
                for i, example in enumerate(character.get('messageExamples', ['No examples available']))
            ])
            post_samples = "\n".join(character.get('postExamples', ['No post examples available'])[:10])
        except Exception as e:
            print_error(f"Error processing character data: {e}")
            raise

        # Get post style guidance for initial context
        post_template = post_generator.generate_post_template("crypto market")
        style_patterns = post_generator.analyze_style_patterns()
        
        personality_context = f"""You are ChainYoda, a crypto-savvy AI agent.

        Post Style Variations (randomly choose one):
        1. One-word power statements: {post_template['style_guide']['post_types']['one_word']}
        2. Emoji posts ({int(post_template['style_guide']['emoji_frequency']*100)}% of posts): {post_template['style_guide']['post_types']['with_emoji']}
        3. Clean posts: {post_template['style_guide']['post_types']['without_emoji']}
        4. News analysis: {post_template['style_guide']['post_types']['news_style']}
        5. Current events (use web_search ~20% of the time): Brief take on latest AI/crypto news

        Length Distribution:
        - Short ({int(post_template['style_guide']['length_distribution']['short']*100)}%): 1-20 chars
        - Medium ({int(post_template['style_guide']['length_distribution']['medium']*100)}%): 20-100 chars
        - Long ({int(post_template['style_guide']['length_distribution']['long']*100)}%): 100+ chars

        Voice Examples:
        {chr(10).join(post_template['similar_posts'][:5])}

        Key Rules:
        1. Randomly vary between post styles
        2. Stay technically precise but conversational
        3. Use emojis naturally and sparingly
        4. For crypto prices: ALWAYS use CDP tools, never web search
        5. For AI/tech news: use web_search occasionally
        6. Maintain slight irreverence while being helpful

        Remember: 
        - Every response must contain meaningful content
        - Only trust CDP tools for current crypto prices
        - Web search is for AI/tech news only"""

    except Exception as e:
        print_error(f"Error in character initialization: {e}")
        sys.exit(1)

    return create_react_agent(
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=personality_context,
    ), config, post_generator

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
    print_system("Processing tokenizers...")
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
            
            # Get chunks from run_with_progress
            chunks = run_with_progress(
                agent_executor.stream,
                {"messages": [HumanMessage(content=user_input)]},
                config
            )
            
            # Process the chunks
            for chunk in chunks:
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

def get_relevant_topic_examples(post_generator, context=None):
    """Get relevant post examples based on current context or trending topics."""
    topic_categories = {
        'market': ["crypto market", "market analysis", "trading", "price action"],
        'tech': ["blockchain tech", "web3", "smart contracts", "developer tools"],
        'news': ["crypto news", "blockchain updates", "protocol updates"],
        'defi': ["defi trends", "yield farming", "liquidity pools"],
        'general': ["ethereum", "blockchain", "crypto community"]
    }
    
    # Check if we have valid mention text
    if context and context.get('mention_text'):
        mention_text = context['mention_text'].lower()
        for category, topics in topic_categories.items():
            for topic in topics:
                if any(word in mention_text for word in topic.split()):
                    return post_generator.get_similar_posts(topic, n=3)
    
    # Default behavior when no context or no mention text
    random_categories = random.sample(list(topic_categories.keys()), 2)
    examples = []
    for category in random_categories:
        topic = random.choice(topic_categories[category])
        examples.extend(post_generator.get_similar_posts(topic, n=2))
    
    return examples[:3]  # Return top 3 examples

def run_autonomous_mode(agent_executor, config, post_generator):
    """Run the agent autonomously with specified intervals."""
    print_system("Starting autonomous mode...")
    
    twitter_state.load()
    progress = ProgressIndicator()

    while True:
        try:
            current_time = datetime.now()
            if not twitter_state.can_check_mentions():
                wait_time = max(0, MENTION_CHECK_INTERVAL - 
                              (current_time - twitter_state.last_check_time).total_seconds())
                if wait_time > 0:
                    print_system(f"Waiting {int(wait_time)} seconds before next check...")
                    time.sleep(wait_time)
                continue

            print_system("Checking mentions and creating new post...")
            progress.start()
            
            # Get contextual examples based on any existing mentions
            post_examples = get_relevant_topic_examples(
                post_generator, 
                context={'mention_text': twitter_state.last_mention_text if hasattr(twitter_state, 'last_mention_text') else None}
            )
            
            thought = f"""You are an AI agent that both posts original content and replies to mentions.

            Post Style Guide:
            {post_examples}
            
            Common patterns in your writing:
            {post_generator.analyze_style_patterns()}

            Process:
            1. Fetch twitter account information 
            2. Create one new original post first using the style guide above
            3. Check for new mentions using the twitter_langchain functions
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

class CharacterPostGenerator:
    def __init__(self, character_file, cache_dir="character_caches"):
        self.character_file = character_file
        progress = ProgressIndicator()
        
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        
        # Generate cache filename based on character file
        character_name = os.path.splitext(os.path.basename(character_file))[0]
        self.cache_file = os.path.join(cache_dir, f"{character_name}_embeddings.pkl")
        
        # Try to load from cache first
        if os.path.exists(self.cache_file):
            print(f"Loading cached embeddings for {character_name}...")
            progress.start()
            with open(self.cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                self.post_examples = cached_data['post_examples']
                self.post_embeddings = cached_data['post_embeddings']
                self.model = cached_data['model']
            progress.stop()
            return

        print(f"Creating new embeddings for {character_name}...")
        progress.start()
        # Original initialization code
        with open(character_file) as f:
            character = json.load(f)
            self.post_examples = character.get('postExamples', [])
        
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.post_embeddings = self.model.encode(self.post_examples)
        
        # Save to cache
        with open(self.cache_file, 'wb') as f:
            pickle.dump({
                'post_examples': self.post_examples,
                'post_embeddings': self.post_embeddings,
                'model': self.model
            }, f)
        progress.stop()

    def get_similar_posts(self, query, n=3):
        """Get n most similar posts to the query"""
        # Encode the query
        query_embedding = self.model.encode([query])
        
        # Calculate similarities
        similarities = cosine_similarity(query_embedding, self.post_embeddings)[0]
        
        # Get top n similar posts
        top_indices = similarities.argsort()[-n:][::-1]
        return [self.post_examples[i] for i in top_indices]
    
    def analyze_style_patterns(self):
        """Analyze common patterns in posts"""
        patterns = {
            'emoji_usage': {},
            'avg_length': 0,
            'common_phrases': set(),
            'capitalization': {
                'all_caps': 0,
                'sentence_case': 0,
                'no_caps': 0
            }
        }
        
        # Unicode ranges for emojis
        emoji_pattern = r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]'
        
        for post in self.post_examples:
            # Analyze length
            patterns['avg_length'] += len(post)
            
            # Analyze emoji usage with proper regex pattern
            emojis = re.findall(emoji_pattern, post)
            for emoji in emojis:
                patterns['emoji_usage'][emoji] = patterns['emoji_usage'].get(emoji, 0) + 1
            
            # Rest of the analysis...
            if post.isupper():
                patterns['capitalization']['all_caps'] += 1
            elif post[0].isupper():
                patterns['capitalization']['sentence_case'] += 1
            else:
                patterns['capitalization']['no_caps'] += 1
                
            words = post.split()
            for i in range(len(words)-2):
                phrase = ' '.join(words[i:i+3])
                if self.post_examples.count(phrase) > 1:
                    patterns['common_phrases'].add(phrase)
        
        patterns['avg_length'] /= len(self.post_examples) if self.post_examples else 1
        return patterns

    def generate_post_template(self, topic):
        """Generate a post template based on analyzed patterns"""
        patterns = self.analyze_style_patterns()
        similar_posts = self.get_similar_posts(topic)
        
        # Categorize example posts
        short_posts = [post for post in self.post_examples if len(post) < 20]
        medium_posts = [post for post in self.post_examples if 20 <= len(post) <= 100]
        long_posts = [post for post in self.post_examples if len(post) > 100]
        
        # Get posts with and without emojis
        emoji_pattern = r'[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]'
        posts_with_emojis = [post for post in self.post_examples if re.search(emoji_pattern, post)]
        posts_without_emojis = [post for post in self.post_examples if not re.search(emoji_pattern, post)]
        
        return {
            'similar_posts': similar_posts,
            'style_guide': {
                'post_types': {
                    'one_word': random.choice(short_posts[:10]),
                    'with_emoji': random.choice(posts_with_emojis[:10]),
                    'without_emoji': random.choice(posts_without_emojis[:10]),
                    'news_style': random.choice(long_posts[:10])
                },
                'length_distribution': {
                    'short': len(short_posts) / len(self.post_examples),
                    'medium': len(medium_posts) / len(self.post_examples),
                    'long': len(long_posts) / len(self.post_examples)
                },
                'emoji_frequency': len(posts_with_emojis) / len(self.post_examples)
            }
        }

class Chatbot:
    def __init__(self):
        # ... existing init code ...
        self.post_generator = CharacterPostGenerator("characters/chainyoda.character.json")
    
    async def generate_response(self, message, context=None):
        if context.get('platform') == 'twitter':
            # Get post style guidance
            post_template = self.post_generator.generate_post_template(message)
            
            # Add style guidance to the prompt
            style_context = f"""
            Reference similar posts:
            {'\n'.join(post_template['similar_posts'])}
            
            Style guide:
            - Aim for ~{int(post_template['style_guide']['avg_length'])} characters
            - Common patterns: {', '.join(post_template['style_guide']['typical_patterns'])}
            - Preferred capitalization: {post_template['style_guide']['capitalization_preference']}
            """
            
            # Add to message context
            context['style_guidance'] = style_context
            
        # ... rest of generate_response code ...

def main():
    """Start the chatbot agent."""
    agent_executor, config, post_generator = initialize_agent()
    mode = choose_mode()
    
    if mode == "chat":
        run_chat_mode(agent_executor=agent_executor, config=config)
    elif mode == "auto":
        run_autonomous_mode(agent_executor=agent_executor, config=config, post_generator=post_generator)

if __name__ == "__main__":
    print("Starting Agent...")
    main()
