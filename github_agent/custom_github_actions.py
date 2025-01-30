from collections.abc import Callable
from json import dumps
import pandas as pd
from github import Github, GithubException
from langchain.tools import Tool
from typing import List
import re

class GitHubAPIWrapper:
    def __init__(self, github_token: str):
        self.client = Github(github_token)
        
    def run_action(self, action: Callable, **kwargs):
        return action(self.client, **kwargs)

def extract_username_from_url(url: str) -> str:
    """Extract GitHub username from profile URL."""
    # Handle different GitHub URL formats
    patterns = [
        r"github\.com/([^/]+)/?$",  # https://github.com/username
        r"github\.com/([^/]+)/?(?:\?|#|$)",  # https://github.com/username?tab=repositories
        #some of the urls are not github links, and do not work when clicked (invalid links)
        #some of the urls are personal websites, which are not valid github profiles
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError(f"Could not extract username from URL: {url}")

def evaluate_github_profiles_from_csv(client: Github, csv_path: str, 
                                    url_column: str = "github_url",
                                    min_commits: int = 20, 
                                    min_followers: int = 0) -> str:
    """Evaluate GitHub profiles from URLs in a CSV file."""
    try:
        # Read CSV file
        df = pd.read_csv(csv_path)
        
        if url_column not in df.columns:
            return f"Error: Column '{url_column}' not found in CSV file. Available columns: {', '.join(df.columns)}"
        
        results = []
        accepted_candidates = []
        rejected_candidates = []
        
        # Process each URL
        for url in df[url_column]:
            try:
                # Extract username from URL
                username = extract_username_from_url(url)
                
                # Get user profile
                user = client.get_user(username)
                
                # Get contribution stats
                contributions = 0
                for repo in user.get_repos():
                    try:
                        stats = repo.get_stats_contributors()
                        if stats:
                            for stat in stats:
                                if stat.author.login == username:
                                    contributions += sum(week.total for week in stat.weeks)
                    except GithubException:
                        continue

                # Get language stats
                language_stats = {}
                for repo in user.get_repos():
                    if repo.language:
                        language_stats[repo.language] = language_stats.get(repo.language, 0) + 1
                
                primary_language = max(language_stats.items(), key=lambda x: x[1])[0] if language_stats else "None"
                
                # Enhanced evaluation with clear accept/reject decision
                meets_requirements = (
                    contributions >= min_commits and 
                    user.followers >= min_followers and
                    primary_language == "Python"
                )
                
                evaluation = {
                    "github_url": url,
                    "username": username,
                    "name": user.name,
                    "total_commits": contributions,
                    "followers": user.followers,
                    "primary_language": primary_language,
                    "criteria_evaluation": {
                        "commits": f"{contributions}/{min_commits} required commits",
                        "followers": f"{user.followers}/{min_followers} required followers",
                        "language_expertise": f"Primary language: {primary_language}"
                    },
                    "decision": "ACCEPTED" if meets_requirements else "REJECTED",
                    "reason": (
                        "Meets all criteria" if meets_requirements else
                        f"Does not meet requirements: " + 
                        ", ".join([
                            f"insufficient commits ({contributions}/{min_commits})" if contributions < min_commits else "",
                            f"insufficient followers ({user.followers}/{min_followers})" if user.followers < min_followers else ""
                        ]).strip(", ")
                    )
                }
                
                results.append(evaluation)
                if meets_requirements:
                    accepted_candidates.append(username)
                else:
                    rejected_candidates.append(username)
                
            except Exception as e:
                results.append({
                    "github_url": url,
                    "error": str(e),
                    "decision": "REJECTED",
                    "reason": f"Error processing profile: {str(e)}"
                })
                rejected_candidates.append(url)
        
        summary = f"""
GitHub Profile Evaluation Summary:
--------------------------------
Total Candidates: {len(results)}
Accepted: {len(accepted_candidates)} ({', '.join(accepted_candidates) if accepted_candidates else 'None'})
Rejected: {len(rejected_candidates)} ({', '.join(rejected_candidates) if rejected_candidates else 'None'})

Detailed Evaluations:
{dumps(results, indent=2)}
"""
        return summary
    
    except Exception as e:
        return f"Error processing CSV file: {str(e)}"

def create_evaluate_profiles_tool(github_api_wrapper) -> Tool:
    """Create a tool to evaluate GitHub profiles from a CSV file."""
    return Tool(
        name="evaluate_github_profiles",
        description="""Evaluate GitHub profiles from URLs in a CSV file.
        Input should be the path to a CSV file containing GitHub profile URLs.
        The CSV should have a column named 'Github URL' with the profile URLs.
        Example: evaluate_github_profiles("candidates.csv")
        Returns evaluation based on:
        - Minimum 20 commits
        - Minimum 0 followers
        - Programming language expertise (Python)""",
        func=lambda csv_path: github_api_wrapper.run_action(
            evaluate_github_profiles_from_csv,
            csv_path=csv_path,
            min_commits=20,
            min_followers=0
        )
    )



#the tools created in this file are:
# create_evaluate_profiles_tool, which is used to evaluate multiple GitHub users as valid event candidates.