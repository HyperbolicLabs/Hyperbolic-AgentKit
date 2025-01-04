from collections.abc import Callable
from json import dumps
import tweepy
from pydantic import BaseModel, Field
from langchain.tools import Tool
from typing import Optional, List, Dict, Union
import random

class Tweet(BaseModel):
    id: str
    text: str
    created_at: str
    author_id: str

def delete_tweet(client: tweepy.Client, tweet_id: str) -> str:
    """Delete a tweet from Twitter."""
    try:
        response = client.delete_tweet(id=tweet_id)
        message = f"Successfully deleted tweet {tweet_id}:\n{dumps(response)}"
    except tweepy.errors.TweepyException as e:
        message = f"Error deleting tweet:\n{e}"
    return message

def create_delete_tweet_tool(twitter_api_wrapper) -> Tool:
    """Create a delete tweet tool with the given Twitter API wrapper."""
    return Tool(
        name="delete_tweet",
        description="""Delete a tweet using its ID. You can only delete tweets from your own account.
        Input should be the tweet ID as a string.
        Example: delete_tweet("1234567890")""",
        func=lambda tweet_id: twitter_api_wrapper.run_action(delete_tweet, tweet_id=tweet_id)
    )

def get_user_id(client: tweepy.Client, username: str) -> str:
    """Get a user's ID from their username."""
    try:
        # The get_user method in tweepy handles the /2/users/by endpoint
        response = client.get_user(username=username)
        if response:
            user_id = response['data']['id']
            twitter_username = response['data']['username']
            message = f"Found user '{twitter_username}' with ID: {user_id}"
        else:
            message = f"No user found with username"
    except tweepy.errors.TweepyException as e:
        message = f"Error getting user ID:\n{e}"
    return message

def create_get_user_id_tool(twitter_api_wrapper) -> Tool:
    """Create a tool to get a user's ID from their username."""
    return Tool(
        name="get_user_id",
        description="""Get a Twitter user's ID from their username.
        Input should be the username as a string (without the @ symbol).
        Example: get_user_id("TwitterDev")""",
        func=lambda username: twitter_api_wrapper.run_action(get_user_id, username=username)
    )

def get_user_tweets(client: tweepy.Client, user_id: str, max_results: int = 10) -> str:
    """Get recent tweets from a user by their ID."""
    try:
        response = client.get_users_tweets(
            id=user_id, 
            max_results=max_results
        )
        if response['data']:
            tweets = []
            for tweet in response['data']:
                tweet_id = tweet['id']
                tweet_text = tweet['text']
                tweets.append(f"[Tweet ID: {tweet_id}]\n{tweet_text}")

            meta = response['meta']
            message = (
                f"Recent tweets from user {user_id}:\n"
                f"(Showing {meta['result_count']} tweets between IDs {meta['oldest_id']} and {meta['newest_id']})\n\n"
                + "\n\n".join(tweets)
            )
        else:
            message = f"No tweets found for user ID: {user_id}"
    except tweepy.errors.TweepyException as e:
        message = f"Error fetching tweets:\n{e}"
    return message

def create_get_user_tweets_tool(twitter_api_wrapper) -> Tool:
    """Create a tool to get a user's recent tweets."""
    return Tool(
        name="get_user_tweets",
        description="""Get recent tweets from a Twitter user using their ID.
        Input should be the user ID as a string.
        Example: get_user_tweets("783214")
        Optionally specify max_results (default 10) as: get_user_tweets("783214", max_results=5)""",
        func=lambda user_id, max_results=10: twitter_api_wrapper.run_action(
            get_user_tweets, 
            user_id=user_id,
            max_results=max_results
        )
    )

def retweet(client: tweepy.Client, tweet_id: str) -> str:
    """Retweet a tweet using its ID."""
    try:
        response = client.retweet(tweet_id=tweet_id)
        message = f"Successfully retweeted tweet {tweet_id}:\n{dumps(response)}"
    except tweepy.errors.TweepyException as e:
        message = f"Error retweeting tweet:\n{e}"
    return message

def create_retweet_tool(twitter_api_wrapper) -> Tool:
    """Create a retweet tool with the given Twitter API wrapper."""
    return Tool(
        name="retweet",
        description="""Retweet a tweet using its ID. You can only retweet public tweets.
        Input should be the tweet ID as a string.
        Example: retweet("1234567890")""",
        func=lambda tweet_id: twitter_api_wrapper.run_action(retweet, tweet_id=tweet_id)
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


