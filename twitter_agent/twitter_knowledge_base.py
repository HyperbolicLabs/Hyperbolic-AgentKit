from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
from utils import print_system, print_error
import asyncio
import os
import random
import json  # Add json import for pretty printing
from twitter_agent.custom_twitter_actions import TwitterClient, Tweet

# Add Tweet model definition that was missing
class Tweet(BaseModel):
    id: str
    text: str
    created_at: str
    author_id: str

class TweetKnowledgeBase:
    def __init__(self, collection_name: str = "twitter_knowledge"):
        print_system("Initializing TweetKnowledgeBase...")
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize ChromaDB client with persistence in data directory
        self.client = chromadb.PersistentClient(path="./chroma_db")
        
        # Use a more advanced embedding model
        self.embedding_model = SentenceTransformer('all-mpnet-base-v2')
        
        # Create embedding function that matches ChromaDB's expected interface
        class EmbeddingFunction:
            def __init__(self, model):
                self.model = model
            
            def __call__(self, input: List[str]) -> List[List[float]]:
                embeddings = self.model.encode(input)
                return embeddings.tolist()
        
        embedding_func = EmbeddingFunction(self.embedding_model)
        
        # Create or get collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_func
            )
        except Exception as e:
            print(f"Error initializing collection: {e}")
            raise

    def add_tweets(self, tweets: List[Tweet]):
        """Add tweets to the knowledge base."""
        documents = [tweet.text for tweet in tweets]
        ids = [tweet.id for tweet in tweets]
        metadata = [
            {
                "author_id": tweet.author_id,
                "created_at": tweet.created_at,
            }
            for tweet in tweets
        ]
        
        self.collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadata
        )

    def query_knowledge_base(self, query: str, n_results: int = 10) -> List[Dict]:
        """Query the knowledge base for relevant tweets."""
        try:
            print_system(f"Querying knowledge base with: {query}")
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Debug logging
            print_system(f"Raw query results: {json.dumps(results, indent=2)}")
            
            if not results['documents'][0]:
                print_system("No results found in knowledge base")
                return []
                
            formatted_results = []
            for doc, metadata, distance in zip(
                results['documents'][0], 
                results['metadatas'][0],
                results['distances'][0]
            ):
                # Format timestamp for readability
                created_at = datetime.fromisoformat(metadata['created_at'].replace('Z', '+00:00'))
                formatted_date = created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                
                formatted_results.append({
                    "text": doc,
                    "metadata": {
                        **metadata,
                        "created_at": formatted_date
                    },
                    "relevance_score": 1 - distance  # Convert distance to similarity score
                })
            
            # Sort by relevance score
            formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            print_system(f"Found {len(formatted_results)} relevant tweets")
            return formatted_results
            
        except Exception as e:
            print_error(f"Error querying knowledge base: {e}")
            return []

    def format_query_results(self, results: List[Dict]) -> str:
        """Format query results into a readable string."""
        if not results:
            return "No relevant tweets found in knowledge base."
            
        formatted_output = []
        for result in results:
            formatted_output.append(
                f"Tweet from {result['metadata']['created_at']}\n"
                f"Relevance: {result['relevance_score']:.2f}\n"
                f"Content: {result['text']}\n"
            )
            
        return "\n---\n".join(formatted_output)

    def get_collection_stats(self) -> Dict:
        """Get statistics about the knowledge base collection."""
        try:
            count = self.collection.count()
            metadata = self.collection.get()
            last_update = None
            if metadata.get("metadatas"):
                # Get most recent tweet timestamp
                last_update = max(m["created_at"] for m in metadata["metadatas"])
                last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            
            print_system(f"Knowledge base contains {count} tweets")
            return {
                "count": count,
                "last_update": last_update or datetime.now()
            }
        except Exception as e:
            print_error(f"Error getting collection stats: {str(e)}")
            return {"count": 0, "last_update": datetime.now()}

    def clear_collection(self) -> bool:
        """Clear all tweets from the knowledge base."""
        try:
            print_system("Clearing knowledge base collection...")
            ids = self.collection.get()["ids"]
            if ids:  # Only attempt to delete if there are IDs
                self.collection.delete(ids=ids)
                print_system("Knowledge base cleared successfully")
            else:
                print_system("Knowledge base is already empty")
            return True
        except Exception as e:
            print_error(f"Error clearing knowledge base: {str(e)}")
            return False

async def update_knowledge_base(twitter_client: TwitterClient, knowledge_base, kol_list: List[Dict]):
    """Update the knowledge base with recent tweets from top KOLs."""
    TOP_KOLS = 5
    TWEETS_PER_KOL = 15
    REQUEST_DELAY = 5
    
    print_system("\n=== Starting Knowledge Base Update ===")
    print_system("Function parameter details:")
    print_system(f"twitter_client type: {type(twitter_client)}")
    print_system(f"knowledge_base type: {type(knowledge_base)}")
    print_system(f"kol_list type: {type(kol_list)}")
    
    try:
        print_system("Testing twitter_client...")
        print_system(f"twitter_client attributes: {dir(twitter_client)}")
        if hasattr(twitter_client, 'run_action'):
            print_system("twitter_client has run_action method")
        else:
            print_error("twitter_client missing run_action method")
    except Exception as e:
        print_error(f"Error inspecting twitter_client: {str(e)}")
    
    # Immediate validation of kol_list
    if kol_list is None:
        print_error("KOL list is None")
        return
    
    try:
        # Debug the exact structure of kol_list
        print_system("\nKOL List details:")
        print_system(f"KOL List type: {type(kol_list)}")
        print_system(f"KOL List length: {len(kol_list)}")
        if len(kol_list) > 0:
            print_system("First KOL entry details:")
            first_kol = kol_list[0]
            print_system(f"Type: {type(first_kol)}")
            print_system(f"Content: {json.dumps(first_kol, indent=2)}")
            if isinstance(first_kol, dict):
                print_system(f"Keys: {list(first_kol.keys())}")
    except Exception as e:
        print_error(f"Error examining KOL list: {str(e)}")
        import traceback
        print_error(f"KOL list examination traceback:\n{traceback.format_exc()}")
        return
    
    # Ensure kol_list is a list
    if isinstance(kol_list, dict):
        print_system("Converting single KOL dict to list...")
        kol_list = [kol_list]
    elif isinstance(kol_list, str):
        try:
            print_system("Attempting to parse string KOL list as JSON...")
            kol_list = json.loads(kol_list)
            if isinstance(kol_list, dict):
                kol_list = [kol_list]
        except json.JSONDecodeError as e:
            print_error(f"Failed to parse KOL list as JSON: {e}")
            print_error(f"Raw KOL list string: {kol_list[:200]}...")  # Show first 200 chars
            return
    
    if not isinstance(kol_list, list):
        print_error(f"KOL list must be a list, got {type(kol_list)}")
        return
    
    print_system(f"\n=== Processing {len(kol_list)} KOLs ===")
    
    # Validate and clean KOL entries
    valid_kols = []
    for i, kol in enumerate(kol_list):
        print_system(f"\nProcessing KOL {i+1}/{len(kol_list)}")
        print_system(f"KOL entry type: {type(kol)}")
        print_system(f"KOL entry content: {json.dumps(kol, indent=2)}")
        
        if not isinstance(kol, dict):
            print_error(f"Invalid KOL entry at index {i} (not a dict): {kol}")
            continue
        
        # Extract username and user_id, with detailed error logging
        try:
            username = kol.get('username')
            user_id = kol.get('user_id')
            
            print_system(f"Extracted username: {username}")
            print_system(f"Extracted user_id: {user_id}")
            
            if not username or not user_id:
                print_error(f"Missing required fields in KOL entry at index {i}: {kol}")
                continue
            
            valid_kol = {
                'username': str(username),
                'user_id': str(user_id)
            }
            print_system(f"Valid KOL entry created: {json.dumps(valid_kol, indent=2)}")
            valid_kols.append(valid_kol)
            
        except Exception as e:
            print_error(f"Error processing KOL entry at index {i}: {str(e)}")
            print_error(f"Problematic KOL entry: {json.dumps(kol, indent=2)}")
            continue
    
    if not valid_kols:
        print_error("No valid KOLs found in list")
        return
    
    print_system(f"\n=== Found {len(valid_kols)} valid KOLs ===")
    
    update_time = datetime.now()
    all_tweets = []
    
    # Select random sample of KOLs
    try:
        print_system("\n=== Selecting random KOLs ===")
        selected_kols = random.sample(valid_kols, min(TOP_KOLS, len(valid_kols)))
        print_system(f"Selected {len(selected_kols)} KOLs for processing")
        print_system("Selected KOLs:")
        for i, kol in enumerate(selected_kols):
            print_system(f"{i+1}. {kol['username']} (ID: {kol['user_id']})")
    except Exception as e:
        print_error(f"Error sampling KOLs: {str(e)}")
        return
    
    # Clear existing knowledge base
    try:
        print_system("\n=== Clearing existing knowledge base ===")
        knowledge_base.clear_collection()
        print_system("Knowledge base cleared successfully")
    except Exception as e:
        print_error(f"Error clearing knowledge base: {e}")
        return
    
    # Process each selected KOL
    print_system("\n=== Processing selected KOLs ===")
    for i, kol in enumerate(selected_kols, 1):
        try:
            print_system(f"\nProcessing KOL {i}/{len(selected_kols)}: {kol['username']}")
            kol_tweets = []
            
            print_system(f"Getting tweets for user {kol['username']} (ID: {kol['user_id']})")
            tweets = await twitter_client.get_user_tweets(
                user_id=kol['user_id'],
                max_results=TWEETS_PER_KOL
            )
            
            if not tweets:
                print_system(f"No tweets found for {kol['username']}")
                continue
                
            print_system(f"Found {len(tweets)} tweets")
            kol_tweets.extend(tweets)
            
            if kol_tweets:
                print_system(f"Adding {len(kol_tweets)} tweets to knowledge base")
                knowledge_base.add_tweets(kol_tweets)
            
            print_system(f"Waiting {REQUEST_DELAY} seconds before next API call...")
            await asyncio.sleep(REQUEST_DELAY)
            
        except Exception as e:
            print_error(f"Error processing KOL {kol['username']}: {str(e)}")
            continue
    
    if all_tweets:
        print_system(f"\n=== Adding {len(all_tweets)} tweets to knowledge base ===")
        try:
            knowledge_base.add_tweets(all_tweets)
            print_system(f"Knowledge base updated successfully at {update_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        except Exception as e:
            print_error(f"Error updating knowledge base: {e}")
    else:
        print_system("\n=== No tweets to add to knowledge base ===") 