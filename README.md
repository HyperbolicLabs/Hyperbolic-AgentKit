# Hyperbolic's Agent Framework

This repository is inspired by and modified from Coinbase's [CDP Agentkit](https://github.com/coinbase/cdp-agentkit). We extend our gratitude to the Coinbase Developer Platform team for their original work.
For the voice agent, we extend the work of [langchain-ai/react-voice-agent](https://github.com/langchain-ai/react-voice-agent).

A template for running an AI agent with both blockchain and compute capabilities, plus X posting using:
- [Hyperbolic Compute Platform](https://app.hyperbolic.xyz/)
- [Coinbase Developer Platform (CDP) Agentkit](https://github.com/coinbase/cdp-agentkit/)

## Features

This template demonstrates a chatbot with the following capabilities:

### Compute Operations (via Hyperbolic):
- Connect ethereum wallet address to Hyperbolic account 
- Rent GPU compute resources
- Terminate GPU instances
- Check GPU availability
- Monitor GPU status
- Query billing history
- ssh access to GPU machines
- Run command lines on remote GPU machines

### Blockchain Operations (via CDP):
- Deploy tokens (ERC-20 & NFTs)
- Manage wallets
- Execute transactions
- Interact with smart contracts

### Twitter Operations:
- Get X account info
- Get User ID from username
- Get an accounts's recent tweets
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
- Operating System: macOS, Linux, or Windows
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
    - Generate API key name and private key
  - **Hyperbolic** (Required for compute tools)
    - Sign up at [Hyperbolic Portal](https://app.hyperbolic.xyz)
    - Navigate to Settings to generate API key

- **Optional Integrations**
  - **X (Twitter) API Access**
    - Create a developer account at [Twitter Developer Portal](https://developer.twitter.com)
    - Required credentials: API Key/Secret, Access Token/Secret, Bearer Token, Client ID/Secret
  - **Web Search**: Tavily API key
  - **Google Cloud** (for Podcast Agent/Gemini)
    - Create a service account and download key as `eaccservicekey.json`
  - **LangChain**: Endpoint, API key, and project name

### 3. Crypto Setup for GPU Compute
To pay for Hyperbolic's GPU compute using crypto:
1. Have an Ethereum wallet with funds on Base network
2. Connect your wallet:
   ```
   Prompt the agent: "connect my wallet 0xYOUR_WALLET_ADDRESS to hyperbolic"
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

## Support and Resources

- [Hyperbolic Documentation](https://app.hyperbolic.xyz/docs)
- [CDP Documentation](https://docs.cloud.coinbase.com/cdp/docs)
- [X API Documentation](https://developer.twitter.com/en/docs)
- [Report Issues](https://github.com/yourusername/Hyperbolic-AgentKit/issues)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

This project incorporates work from:
- [CDP Agentkit](https://github.com/coinbase/cdp-agentkit) (Apache License 2.0)
- [langchain-ai/react-voice-agent](https://github.com/langchain-ai/react-voice-agent) (MIT License)
