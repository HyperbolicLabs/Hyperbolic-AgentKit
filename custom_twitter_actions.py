from collections.abc import Callable
from json import dumps
import tweepy
from pydantic import BaseModel, Field
from langchain.tools import Tool

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