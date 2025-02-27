"""
Contains all prompts and related data used by the chatbot agent.
"""

# Topic areas for podcast queries
PODCAST_TOPICS = [
    # Scaling & Infrastructure
    "horizontal scaling challenges", "decentralization vs scalability tradeoffs",
    "infrastructure evolution", "restaking models and implementation",
    
    # Technical Architecture  
    "layer 2 solutions and rollups", "node operations", "geographic distribution",
    "decentralized service deployment",
    
    # Ecosystem Development
    "market coordination mechanisms", "operator and staker dynamics", 
    "blockchain platform evolution", "community bootstrapping",
    
    # Future Trends
    "ecosystem maturation", "market maker emergence",
    "strategy optimization", "service coordination",
    
    # Web3 Infrastructure
    "decentralized vs centralized solutions", "cloud provider comparisons",
    "resilience and reliability", "infrastructure distribution",
    
    # Market Dynamics
    "marketplace design", "coordination mechanisms",
    "efficient frontier development", "ecosystem player roles"
]

# Aspects to consider for podcast queries
PODCAST_ASPECTS = [
    # Technical
    "infrastructure scalability", "technical implementation challenges",
    "architectural tradeoffs", "system reliability",
    
    # Market & Economics
    "market efficiency", "economic incentives",
    "stakeholder dynamics", "value capture mechanisms",
    
    # Development
    "platform evolution", "ecosystem growth",
    "adoption patterns", "integration challenges",
    
    # Strategy
    "optimization approaches", "competitive dynamics",
    "strategic positioning", "risk management"
]

# Basic query templates for fallback
BASIC_QUERY_TEMPLATES = [
    "What are the key insights from recent podcast discussions?",
    "What emerging trends were highlighted in recent episodes?",
    "What expert predictions were made about the crypto market?",
    "What innovative blockchain use cases were discussed recently?",
    "What regulatory developments were analyzed in recent episodes?"
]

# Prompt for generating podcast queries
PODCAST_QUERY_PROMPT = '''
Generate ONE focused query about Web3 technology to search crypto podcast transcripts.

Consider these elements (but focus on just ONE):
- Core Topics: {topics}
- Key Aspects: {aspects}

Requirements for the query:
1. Focus on just ONE specific technical aspect or challenge from the above
2. Keep the scope narrow and focused
3. Use simple, clear language
4. Aim for 10-15 words
5. Ask about concrete technical details rather than abstract concepts

Example good queries:
- "What are the main challenges operators face when running rollup nodes?"
- "How do layer 2 solutions handle data availability?"
- "What infrastructure requirements do validators need for running nodes?"

Generate exactly ONE query that meets these criteria. Return ONLY the query text, nothing else.
'''

# Prompt for analyzing and enhancing query results
ENHANCE_QUERY_PROMPT = '''
As an AI specializing in podcast content analysis, analyze this query and its results to generate a more focused follow-up query.

<initial_query>
{initial_query}
</initial_query>

<query_result>
{query_result}
</query_result>

Your task:
1. Analyze the relationship between the query and its results
2. Identify any:
   - Unexplored angles
   - Interesting tangents
   - Deeper technical aspects
   - Missing context
   - Potential contradictions
   - Novel connections
3. Generate a follow-up query that:
   - Builds upon the most interesting insights
   - Explores identified gaps
   - Dives deeper into promising areas
   - Connects different concepts
   - Challenges assumptions
   - Seeks practical applications

Requirements for the enhanced query:
1. Must be more specific than the initial query
2. Should target unexplored aspects revealed in the results
3. Must maintain relevance to blockchain/crypto
4. Should encourage detailed technical or analytical responses
5. Must be a single, clear question
6. Should lead to actionable insights

Return ONLY the enhanced follow-up query, nothing else.
Make it unique and substantially different from the initial query.
'''

# Autonomous mode thought prompt
AUTONOMOUS_MODE_PROMPT = '''
Be creative and do something interesting on the blockchain. 
Choose an action or set of actions and execute it that highlights your abilities.
''' 