from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np
from custom_twitter_actions import get_user_tweets, get_user_id
from utils import print_system, print_error
import asyncio

# Add Tweet model definition that was missing
class Tweet(BaseModel):
    id: str
    text: str
    created_at: str
    author_id: str

class TweetKnowledgeBase:
    def __init__(self, collection_name: str = "twitter_knowledge"):
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
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
            # Add logging for debugging
            print_system(f"Querying knowledge base with: {query}")
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
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
            print_system(f"Knowledge base contains {count} tweets")
            return {"count": count}
        except Exception as e:
            print_error(f"Error getting collection stats: {str(e)}")
            return {"count": 0}

    def clear_collection(self) -> bool:
        """Clear all tweets from the knowledge base."""
        try:
            print_system("Clearing knowledge base collection...")
            self.collection.delete(ids=self.collection.get()["ids"])
            print_system("Knowledge base cleared successfully")
            return True
        except Exception as e:
            print_error(f"Error clearing knowledge base: {str(e)}")
            return False

async def update_knowledge_base(twitter_api_wrapper, knowledge_base, kol_ids: List[str]):
    """Update the knowledge base with recent tweets from key opinion leaders."""
    all_tweets = []
    print_system(f"Starting knowledge base update for {len(kol_ids)} KOLs...")
    
    # Constants for rate limiting
    BATCH_SIZE = 10  # Process 10 users per 15-minute window (max app limit)
    WINDOW_DURATION = 15 * 60  # 15 minutes in seconds
    REQUEST_DELAY = 90  # 90 seconds between requests (15 minutes / 10 requests = 90 seconds)
    
    # Process users in batches
    for i in range(0, len(kol_ids), BATCH_SIZE):
        batch = kol_ids[i:i + BATCH_SIZE]
        print_system(f"Processing batch {i//BATCH_SIZE + 1} of {(len(kol_ids) + BATCH_SIZE - 1)//BATCH_SIZE}")
        
        for username in batch:
            print_system(f"Converting username to ID: {username}")
            try:
                # Get user ID
                response = twitter_api_wrapper.run_action(
                    get_user_id,
                    username=username
                )
                
                # Add delay after user ID request
                await asyncio.sleep(REQUEST_DELAY)
                
                # Parse the user ID from the response message
                if "Found user" in response:
                    user_id = response.split("with ID: ")[1].strip()
                    print_system(f"Fetching tweets for {username} (ID: {user_id})")
                    
                    response = twitter_api_wrapper.run_action(
                        get_user_tweets, 
                        user_id=user_id,
                        max_results=10
                    )
                    
                    # Debug the response
                    print_system(f"Raw response type: {type(response)}")
                    print_system(f"Raw response content: {response[:500]}...")
                    
                    try:
                        # Parse the response into Tweet objects
                        tweets_data = []
                        if isinstance(response, str):
                            tweet_blocks = [block.strip() for block in response.split("\n\n") if block.strip()]
                            
                            for block in tweet_blocks:
                                print_system(f"Processing tweet block: {block[:200]}...")
                                
                                if "[Tweet ID:" in block:
                                    try:
                                        tweet_id = block.split("[Tweet ID: ")[1].split("]")[0].strip()
                                        tweet_text = block.split("]\n", 1)[1].strip() if "]\n" in block else ""
                                        
                                        if tweet_id and tweet_text:
                                            tweets_data.append(
                                                Tweet(
                                                    id=tweet_id,
                                                    text=tweet_text,
                                                    created_at=datetime.now().isoformat(),
                                                    author_id=user_id
                                                )
                                            )
                                            print_system(f"Successfully parsed tweet ID: {tweet_id}")
                                    except Exception as e:
                                        print_error(f"Error parsing individual tweet block: {str(e)}")
                                        continue
                        
                        if tweets_data:
                            print_system(f"Successfully parsed {len(tweets_data)} tweets for {username}")
                            all_tweets.extend(tweets_data)
                            
                            # If we have accumulated enough tweets, add them to the knowledge base
                            if len(all_tweets) >= 50:
                                print_system(f"Adding batch of {len(all_tweets)} tweets to knowledge base")
                                knowledge_base.add_tweets(all_tweets)
                                all_tweets = []
                        else:
                            print_error(f"No tweets could be parsed for {username}")
                            print_system("Tweet blocks found: " + str(len(tweet_blocks)) if 'tweet_blocks' in locals() else "No tweet blocks found")
                            
                    except Exception as e:
                        print_error(f"Error parsing tweets for {username}: {str(e)}")
                        continue
                        
            except Exception as e:
                print_error(f"Error processing user {username}: {str(e)}")
                continue
            
            # Add delay between users within the batch
            await asyncio.sleep(REQUEST_DELAY)
        
        # After processing a batch, wait for the rate limit window to reset
        if i + BATCH_SIZE < len(kol_ids):
            wait_time = WINDOW_DURATION
            print_system(f"Rate limit window reached. Waiting {wait_time/60:.1f} minutes before next batch...")
            await asyncio.sleep(wait_time)
    
    # Add any remaining tweets
    if all_tweets:
        print_system(f"Adding final batch of {len(all_tweets)} tweets to knowledge base")
        try:
            knowledge_base.add_tweets(all_tweets)
            print_system("Successfully added final batch to knowledge base")
        except Exception as e:
            print_error(f"Error adding final batch to knowledge base: {str(e)}") 