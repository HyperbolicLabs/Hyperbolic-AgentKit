# Hyperbolic's Agent Framework

This repository is inspired by and modified from Coinbase's [CDP Agentkit](https://github.com/coinbase/cdp-agentkit). We extend our gratitude to the Coinbase Developer Platform team for their original work.
For the voice agent, we extend the work of [langchain-ai/react-voice-agent](https://github.com/langchain-ai/react-voice-agent).

We recommend reading this entire README before running the application or developing new tools, as many of your questions will be answered here.

## Features

This template demonstrates a chatbot with the following capabilities:

### Compute Operations (via Hyperbolic):

- Connect Ethereum wallet address to Hyperbolic account
- Rent GPU compute resources
- Terminate GPU instances
- Check GPU availability
- Monitor GPU status
- Query billing history
- SSH access to GPU machines
- Run command line tools on remote GPU machines

### Blockchain Operations (via CDP):

- Deploy tokens (ERC-20 & NFTs)
- Manage wallets
- Execute transactions
- Interact with smart contracts

### Twitter Operations:

- Get X account info
- Get User ID from username
- Get an account's recent tweets
- Post tweet
- Delete tweet
- Reply to tweet and check reply status
- Retweet a tweet and check retweet status

### Additional Tools:

- **Podcast Agent**: Tools for video processing and transcription
  - `podcast_agent/aiagenteditor.py`: Trim video files using Gemini and ffmpeg
  - `podcast_agent/geminivideo.py`: Transcribe video files using Gemini

### Knowledge Base Integrations:

- Twitter Knowledge Base: Scrapes tweets from KOLs for informed X posting
- Podcast Knowledge Base: Uses podcast transcripts for accurate Q&A

## Prerequisites

### 1. System Requirements

- Operating System: macOS or Linux (Windows has not been tested)
- Python 3.12 (required)
- Node.js 18+ (for web interface)
- Git

### 2. API Keys and Configuration

- **Core API Keys (Required)**

  - **Anthropic**
    - Get API key from [Anthropic Portal](https://console.anthropic.com/dashboard)
  - **OpenAI** (Required only for voice agent)
    - Get API key from [OpenAI Portal](https://platform.openai.com/api-keys)
  - **CDP**
    - Sign up at [CDP Portal](https://portal.cdp.coinbase.com/access/api)
  - **Hyperbolic** (Required for compute tools)
    - Sign up at [Hyperbolic Portal](https://app.hyperbolic.xyz)
    - Navigate to Settings to generate API key, this is also where you configure ssh access with your RSA public key

- **Optional Integrations**
  - **X (Twitter) API Access**
    - Create a developer account at [Twitter Developer Portal](https://developer.twitter.com)
    - Required credentials: API Key/Secret, Access Token/Secret, Bearer Token, Client ID/Secret
  - **Web Search**: Tavily API key
  - **Google Cloud** (for Podcast Agent/Gemini)
    - Create a service account and download key as `eaccservicekey.json` into the project root
  - **LangChain**: Endpoint, API key, and project name

### 3. Crypto Setup for GPU Compute

To pay for Hyperbolic's GPU compute using crypto:

1. Have an Ethereum wallet with funds on Base network
2. Connect your wallet:
   ```
   Prompt the agent: "connect my wallet 0xYOUR_WALLET_ADDRESS to Hyperbolic"
   ```
3. Send funds:
   - Supported tokens: USDC, USDT, or DAI on Base network
   - Send to: `0xd3cB24E0Ba20865C530831C85Bd6EbC25f6f3B60`
4. Start computing:
   - Funds will be available immediately
   - Use the agent to rent and manage GPU resources

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Hyperbolic-AgentKit.git
cd Hyperbolic-AgentKit
```

### 2. Python Environment Setup

**Using Poetry (Recommended)**:

```bash
# Install Poetry if you haven't
curl -sSL https://install.python-poetry.org | python3 -

# Set up the environment
poetry env use python3.12
poetry install
```

**Browser Automation**

- Install Playwright browsers after installing dependencies:

```bash
poetry run playwright install
```

### 3. Environment Configuration

```bash
# Copy and edit the environment file
cp .env.example .env
nano .env  # or use any text editor
```

**API Keys**
The `.env.example` file contains all possible configurations. Required fields depend on which features you want to use and are specified in the file.

### 4. Character Configuration

The `template.json` file allows you to customize your AI agent's personality and communication style. Duplicate the file and edit the fields to define:

- Agent's name, twitter account info, and description
- Personality traits
- Communication style, tone, and examples
- Background lore and expertise
- KOL list for automated interaction

### 5. Additional Setup

- **Browser Automation** (if using browser tools):
  ```bash
  poetry run playwright install  # or: playwright install
  ```
- **SSH Key** (for GPU compute):
  - Ensure you have an RSA key at `~/.ssh/id_rsa` or configure `SSH_PRIVATE_KEY_PATH`
    - Only RSA keys are supported for now
    - In order to generate an RSA key, run `ssh-keygen -t rsa -b 4096 -C "your_email@example.com"`

## Running the Application

### 1. Voice Agent (Web Interface)

```bash
# Start the server
PYTHONPATH=$PWD/server/src poetry run python server/src/server/app.py

# Access the interface at http://localhost:3000
```

### 2. Terminal Interface

```bash
poetry run python chatbot.py
```

### 3. Gradio Web Interface

```bash
poetry run python gradio_ui.py
# Access the interface at http://localhost:7860
```

## Troubleshooting

### Common Issues:

1. **API Key Errors**

   - Verify all API keys are correctly set in `.env`
   - Check API key permissions and quotas

2. **Python Version Issues**

   ```bash
   # Check Python version
   python --version

   # If needed, install Python 3.12
   # On macOS:
   brew install python@3.12
   # On Ubuntu:
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install python3.12
   ```

3. **Dependencies Issues**

   ```bash
   # Clean Poetry environment
   poetry env remove python3.12
   poetry env use python3.12
   poetry install --no-cache
   ```

4. **Browser Automation Issues**

   ```bash
   # Reinstall Playwright browsers
   poetry run playwright install --force
   ```

5. **Chrome Browser Setup Issues**
   - Ensure Google Chrome is installed on your system
   - Configure a default Chrome profile:
     1. Open Chrome
     2. Make sure a profile is already selected/active
     3. Remove all pinned tabs from the active profile (they can cause browser automation issues)
     4. Ensure Chrome doesn't show a profile selector on startup
   - If using browser automation tools, the agent assumes:
     - Chrome is your default browser
     - A default profile exists and is automatically selected
     - No pinned tabs are present in the active profile

## Adding New Tools

The agent framework supports two main interfaces, each with its own tool registration point:

### 1. Project Structure

New agentic capabilities should be organized in dedicated folders at the root level. For example:

- `twitter_agent/` - Twitter API integration and knowledge base
- `browser_agent/` - Browser automation capabilities
- `podcast_agent/` - Podcast processing and transcription

Each agent folder typically contains:

- `__init__.py` - Exports and initialization
- Core functionality modules (e.g., `twitter_state.py`, `browser_tool.py`)
- Knowledge base implementations if applicable

### 2. Repository Organization

```
Hyperbolic-AgentKit/
├── characters/              # Character configurations
│   └── default.json        # Default character profile
├── *_agent/                # Agent-specific capabilities
│   ├── __init__.py
│   └── core modules
├── server/                 # Voice agent interface
│   └── src/
│       └── server/
│           └── tools.py   # Voice agent tools
└── chatbot.py             # Main agent initialization
```

### 3. Agent Initialization Flow

The agent is initialized through several key functions in `chatbot.py`:

1. `loadCharacters()`:

   - Loads character configurations from JSON files
   - Supports multiple characters with fallback to default
   - Handles character file path resolution

2. `process_character_config()`:

   - Transforms character JSON into agent personality
   - Processes bio, lore, knowledge, style guidelines
   - Formats examples and KOL lists

3. `create_agent_tools()`:

   - Registers tools based on environment configuration
   - Supports multiple tool categories (browser, Twitter, podcast, etc.)
   - Handles tool dependencies and state management

4. `initialize_agent()`:
   - Orchestrates the entire setup process
   - Initializes LLM, character, and knowledge bases
   - Configures tools and agent state

### 4. Voice Agent Structure

The voice agent is implemented in `server/src/server/app.py` using WebSocket communication:

```
server/src/server/
├── app.py              # Main server implementation
├── tools.py            # Voice agent tools
├── prompt.py           # Voice agent instructions
└── static/             # Web interface files
    └── index.html
```

Key components:

1. Server Setup:

   ```python
   app = Starlette(
       routes=[
           Route("/", homepage),
           WebSocketRoute("/ws", websocket_endpoint)
       ]
   )
   ```

2. WebSocket Communication:

   - Browser ↔️ Server real-time communication
   - Handles voice input/output streams
   - Maintains persistent connection for conversation

3. Agent Configuration:

   ```python
   agent = OpenAIVoiceReactAgent(
       model="gpt-4o-realtime-preview", # gpt-4o-realtime-preview and gpt-4o-mini-realtime-preview are the only models that support the voice agent
       tools=TOOLS,
       instructions=full_instructions,
       voice="verse"  # Available: alloy, ash, ballad, coral, echo, sage, shimmer, verse
   )
   ```

4. Character Integration:
   - Reuses `loadCharacters()` and `process_character_config()`
   - Combines base instructions with character personality
   - Maintains consistent persona across interfaces

### 5. Tool Registration

Tools are registered in two places:

1. Main chatbot interface (`chatbot.py`) via `create_agent_tools()`
2. Voice agent interface (`server/src/server/tools.py`) via `create_tools()`

Look at the existing action implementations in `/hyperbolic_agentkit_core` for examples of:

- Adding individual tools and toolkits
- Configuring via environment variables
- Managing dependencies and state

### 6. Tool Categories

The framework includes several categories of pre-built tools you can reference:

- Browser automation tools
- Knowledge base tools
- Social media tools (Twitter/X)
- Blockchain tools (CDP)
- Compute tools (Hyperbolic)
- Web search tools
- HTTP request tools

When adding a new capability, examine similar implementations in existing agent folders for patterns and best practices.

## Support and Resources

- [Hyperbolic Documentation](https://docs.hyperbolic.xyz/docs/getting-started) 
- [CDP Documentation](https://docs.cdp.coinbase.com/agentkit/docs/welcome)
- [X API Documentation](https://docs.x.com/x-api/introduction)
- [Report Issues](https://github.com/yourusername/Hyperbolic-AgentKit/issues)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details.

This project incorporates work from:

- [CDP Agentkit](https://github.com/coinbase/cdp-agentkit) (Apache License 2.0)
- [langchain-ai/react-voice-agent](https://github.com/langchain-ai/react-voice-agent) (MIT License)
