from collections.abc import Callable
from json import dumps
from pydantic import BaseModel, Field
from langchain.tools import Tool
from typing import Optional, List, Dict, Union
import tweepy
import os
from dotenv import load_dotenv
import asyncio
from functools import partial

# Load environment variables
load_dotenv()

class Tweet(BaseModel):
    id: str
    text: str
    author_id: str
    created_at: str

class TwitterClient:
    def __init__(self):
        """Initialize Twitter API v2 client with credentials from environment variables."""
        self.client = tweepy.Client(
            bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
            wait_on_rate_limit=True
        )

    async def get_user_id(self, username: str) -> Optional[str]:
        """Get user ID from username."""
        try:
            user = self.client.get_user(username=username)
            if user and user.data:
                return str(user.data.id)
            return None
        except Exception as e:
            print(f"Error getting user ID for {username}: {str(e)}")
            return None

    async def get_user_tweets(self, user_id: str, max_results: int = 10) -> List[Tweet]:
        """Get recent tweets from a user."""
        try:
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=max_results,
                tweet_fields=['created_at', 'author_id']
            )
            
            if not tweets.data:
                return []
                
            return [
                Tweet(
                    id=str(tweet.id),
                    text=tweet.text,
                    author_id=str(tweet.author_id),
                    created_at=tweet.created_at.isoformat()
                )
                for tweet in tweets.data
            ]
        except Exception as e:
            print(f"Error getting tweets for user {user_id}: {str(e)}")
            return []

    async def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet."""
        try:
            response = self.client.delete_tweet(id=tweet_id)
            return response.data is not None
        except Exception as e:
            print(f"Error deleting tweet {tweet_id}: {str(e)}")
            return False

    async def retweet(self, tweet_id: str) -> bool:
        """Retweet a tweet."""
        try:
            response = self.client.retweet(tweet_id=tweet_id)
            return response.data is not None
        except Exception as e:
            print(f"Error retweeting {tweet_id}: {str(e)}")
            return False

# Create a single instance of TwitterClient
twitter_client = TwitterClient()

def create_delete_tweet_tool() -> Tool:
    """Create a delete tweet tool."""
    return Tool(
        name="delete_tweet",
        description="""Delete a tweet using its ID. You can only delete tweets from your own account.
        Input should be the tweet ID as a string.
        Example: delete_tweet("1234567890")""",
        func=lambda tweet_id: asyncio.run(twitter_client.delete_tweet(tweet_id))
    )

def create_get_user_id_tool() -> Tool:
    """Create a tool to get a user's ID from their username."""
    return Tool(
        name="get_user_id",
        description="""Get a Twitter user's ID from their username.
        Input should be the username as a string (without the @ symbol).
        Example: get_user_id("TwitterDev")""",
        func=lambda username: asyncio.run(twitter_client.get_user_id(username))
    )

def create_get_user_tweets_tool() -> Tool:
    """Create a tool to get a user's recent tweets."""
    return Tool(
        name="get_user_tweets",
        description="""Get recent tweets from a Twitter user using their ID.
        Input should be the user ID as a string.
        Example: get_user_tweets("783214")
        Optionally specify max_results (default 10) as: get_user_tweets("783214", max_results=5)""",
        func=lambda user_id, max_results=10: asyncio.run(twitter_client.get_user_tweets(user_id, max_results))
    )

def create_retweet_tool() -> Tool:
    """Create a retweet tool."""
    return Tool(
        name="retweet",
        description="""Retweet a tweet using its ID. You can only retweet public tweets.
        Input should be the tweet ID as a string.
        Example: retweet("1234567890")""",
        func=lambda tweet_id: asyncio.run(twitter_client.retweet(tweet_id))
    )

def create_query_knowledge_base_tool(knowledge_base) -> Tool:
    """Create a tool to query the Twitter knowledge base."""
    return Tool(
        name="query_knowledge_base",
        description="""Query the knowledge base for relevant information about current trends.
        Input should be a query string describing the information you're looking for.
        Example: query_knowledge_base("latest developments in AI")""",
        func=lambda query: knowledge_base.query_knowledge_base(query)
    )


