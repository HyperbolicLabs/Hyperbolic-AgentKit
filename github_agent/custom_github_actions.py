from collections.abc import Callable
from json import dumps
import pandas as pd
from github import Github, GithubException
from langchain.tools import Tool
from typing import List, Dict, Optional
import re
import time
import requests

class GitHubAPIWrapper:
    def __init__(self, github_token: str):
        self.token = github_token
        self.headers = {
            'Authorization': f'Bearer {github_token}',
            'Content-Type': 'application/json',
        }
        self.endpoint = 'https://api.github.com/graphql'

    def execute_query(self, query: str, variables: Dict) -> Dict:
        """Execute a GraphQL query against GitHub's API."""
        response = requests.post(
            self.endpoint,
            json={'query': query, 'variables': variables},
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def get_user_profile_data(self, username: str) -> Optional[Dict]:
        """Get user's contributions and top languages."""
        query = """
        query($userName:String!) {
            user(login: $userName) {
                contributionsCollection {
                    contributionCalendar {
                        totalContributions
                    }
                }
                repositories(first: 10, orderBy: {field: STARGAZERS, direction: DESC}, ownerAffiliations: [OWNER]) {
                    nodes {
                        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
                            edges {
                                size
                                node {
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        try:
            result = self.execute_query(query, {'userName': username})
            
            # Get contributions
            contributions = result['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions']
            
            # Calculate language statistics
            language_stats = {}
            repositories = result['data']['user']['repositories']['nodes']
            
            for repo in repositories:
                if repo['languages'] and repo['languages']['edges']:
                    for lang_edge in repo['languages']['edges']:
                        lang_name = lang_edge['node']['name']
                        lang_size = lang_edge['size']
                        language_stats[lang_name] = language_stats.get(lang_name, 0) + lang_size
            
            # Sort languages by total size
            sorted_languages = sorted(language_stats.items(), key=lambda x: x[1], reverse=True)
            top_languages = [lang[0] for lang in sorted_languages[:3]]  # Reduced from 5 to 3 top languages
            
            return {
                'contributions': contributions,
                'top_languages': top_languages,
                'primary_language': top_languages[0] if top_languages else None
            }
            
        except Exception as e:
            print(f"Error fetching data for {username}: {e}")
            return None

def verify_github_auth(client: Github) -> bool:
    """Verify GitHub authentication and permissions."""
    try:
        # Get authenticated user
        user = client.get_user()
        print(f"Authenticated as: {user.login}")
        
        # Check rate limit
        rate_limit = client.get_rate_limit()
        print(f"API Rate Limit: {rate_limit.core.remaining}/{rate_limit.core.limit}")
        
        return True
    except GithubException as e:
        print(f"Authentication Error: {e}")
        return False


def extract_username_from_url(url: str) -> str:
    """Extract GitHub username from profile URL."""
    patterns = [
        r"github\.com/([^/]+)/?$",
        r"github\.com/([^/]+)/?(?:\?|#|$)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError(f"Could not extract username from URL: {url}")

def evaluate_github_profiles_from_csv(github_api: GitHubAPIWrapper, 
                                    csv_path: str = "github_agent/csvs/PMF or Die_ AI Agent Hackathon @ Hyper(r)House - Guests - 2025-01-30-09-24-49.csv",
                                    url_column: str = "Github URL",
                                    min_commits: int = 20,
                                    min_followers: int = 0) -> str:
    """Evaluate GitHub profiles from URLs in a CSV file."""
    print("=== Starting GitHub Profile Evaluation ===")
    print(f"Parameters received:")
    print(f"- csv_path: {csv_path}")
    print(f"- url_column: {url_column}")
    print(f"- min_commits: {min_commits}")
    
    try:
        # Read CSV file
        df = pd.read_csv(csv_path)
        print(f"Found {len(df)} entries")
        
        if url_column not in df.columns:
            return f"Error: Column '{url_column}' not found in CSV file. Available columns: {', '.join(df.columns)}"
        
        results = []
        accepted_candidates = []
        rejected_candidates = []
        
        # Process each URL
        for idx, url in enumerate(df[url_column]):
            print(f"Processing URL {idx + 1}/{len(df)}: {url}")
            try:
                if not isinstance(url, str) or not url.startswith('https://github.com/'):
                    results.append({
                        "github_url": url,
                        "error": "Invalid GitHub URL format",
                        "decision": "REJECTED",
                        "reason": "Invalid GitHub URL format"
                    })
                    rejected_candidates.append(str(url))
                    continue

                username = extract_username_from_url(url)
                print(f"Extracted username: {username}")
                
                # Get user data using GraphQL
                user_data = github_api.get_user_profile_data(username)
                if user_data is None:
                    raise ValueError("Could not fetch user data")
                
                contributions = user_data['contributions']
                top_languages = user_data['top_languages']
                primary_language = user_data['primary_language']
                
                print(f"Found {contributions} contributions for {username}")
                print(f"Top languages: {', '.join(top_languages)}")
                
                # Make decision based on contribution count
                meets_requirements = contributions >= min_commits
                
                evaluation = {
                    "github_url": url,
                    "username": username,
                    "total_contributions": contributions,
                    "top_languages": top_languages,
                    "primary_language": primary_language,
                    "criteria_evaluation": {
                        "contributions": f"{contributions}/{min_commits} required contributions",
                        "languages": f"Primary language: {primary_language}, Top languages: {', '.join(top_languages)}"
                    },
                    "decision": "ACCEPTED" if meets_requirements else "REJECTED",
                    "reason": (
                        "Meets all criteria" if meets_requirements else
                        f"Insufficient contributions ({contributions}/{min_commits})"
                    )
                }
                
                results.append(evaluation)
                if meets_requirements:
                    accepted_candidates.append(username)
                else:
                    rejected_candidates.append(username)
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
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
{results}
"""
        return summary
    
    except Exception as e:
        return f"Error processing CSV file: {str(e)}"

def create_evaluate_profiles_tool(github_api_wrapper) -> Tool:
    """Create a tool to evaluate GitHub profiles from a CSV file."""
    return Tool(
        name="evaluate_github_profiles",
        description="""Evaluate GitHub profiles from URLs in a CSV file.
        This tool automatically reads from a hardcoded CSV file.
        No input parameters needed - just call the tool directly.""",
        func=lambda *args: evaluate_github_profiles_from_csv(
            github_api=github_api_wrapper,
            csv_path="github_agent/csvs/PMF or Die_ AI Agent Hackathon @ Hyper(r)House - Guests - 2025-01-30-09-24-49.csv",
            url_column="Github URL",
            min_commits=20,
            min_followers=0
        )
    )



#the tools created in this file are:
# create_evaluate_profiles_tool, which is used to evaluate multiple GitHub users as valid event candidates.