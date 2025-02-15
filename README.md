# Hyperbolic Agentkit x X (Twitter) Chatbot x CDP Agentkit

This repository is inspired by and modified from Coinbase's [CDP Agentkit](https://github.com/coinbase/cdp-agentkit). We extend our gratitude to the Coinbase Developer Platform team for their original work.
For the voice agent, we extend the work of [langchain-ai/react-voice-agent](https://github.com/langchain-ai/react-voice-agent).

A template for running an AI agent with both blockchain and compute capabilities, plus X posting using:
- [Hyperbolic Compute Platform](https://app.hyperbolic.xyz/)
- [Coinbase Developer Platform (CDP) Agentkit](https://github.com/coinbase/cdp-agentkit/)

This template demonstrates a chatbot that can:

Compute Operations (via Hyperbolic):
- Connect ethereum wallet address to Hyperbolic account 
- Rent GPU compute resources
- Terminate GPU instances
- Check GPU availability
- Monitor GPU status
- Query billing history
- ssh access to GPU machines
- Run command lines on remote GPU machines

How to pay for compute using crypto:
- Prompt the agent to connect your ethereum wallet address to hyperbolic (ex. "connect my wallet 0x7C9CB45454545A6222a29843A603b6e56ee93 to hyperbolic")
- From your wallet, send desired amount of USDC, USDT, or DAI on Base network to Hyperbolic address: 0xd3cB24E0Ba20865C530831C85Bd6EbC25f6f3B60
- The funds will now be available in your Hyperbolic account and can be used to pay for compute

Blockchain Operations (via CDP):
- Deploy tokens (ERC-20 & NFTs)
- Manage wallets
- Execute transactions
- Interact with smart contracts

Twitter Operations:
- Get X account info
- Get User ID from username
- Get an accounts's recent tweets, given their username/user ID
- Post tweet
- Delete tweet
- Reply to tweet, and check if a tweet has been replied to
- Retweet a tweet, and check if a tweet has been retweeted

Browser Automation:
- Autonomous web browsing and research
- Price comparisons across different services
- Web search and information gathering
- Automated task completion
- Visual history of agent actions

Other Python Scripts that can be run directly:
- podcast_agent/aiagenteditor.py: A tool for trimming videofiles using gemini and ffmpeg
- podcast_agent/geminivideo.py: A tool for transcribing video files using gemini

To access Gemini, you should create a servicekey using google cloud and add it as eaccservicekey.json in the root directory

Knowledge Base Integrations:
- Twitter Knowledge Base: scrapes tweets from specified list of KOLs and uses them as a knowledge base for the agent to create relevant X posts
- Podcast Knowledge Base: uses podcast transcripts as a knowledge base for the agent to accurately answer questions about a podcast

## Prerequisites

1. **Python Version**
   - This project requires Python 3.12
   - If using Poetry, you can ensure the correct version with:
   ```bash
   poetry env use python3.12
   poetry install
   ```

2. **API Keys**
   - OpenAI API key from the [OpenAI Portal](https://platform.openai.com/api-keys) or Anthropic API key from the [Anthropic Portal](https://console.anthropic.com/dashboard)
   - CDP API credentials from [CDP Portal](https://portal.cdp.coinbase.com/access/api)
   - X Social API (Account Key and secret, Access Key and Secret)
   - Hyperbolic API Key from [Hyperbolic Portal](https://app.hyperbolic.xyz/settings)

3. **Browser Automation Setup**
   - Install browser dependencies:
   ```bash
   poetry run playwright install
   poetry run playwright install-deps
   ```

## Quick Start

1. **Clone the Repository**
```bash
git clone https://github.com/yourusername/Hyperbolic-AgentKit.git
cd Hyperbolic-AgentKit
```

2. **Initialize Submodules**
The repository contains submodules that need to be initialized. Run the following commands:
```bash
git config --global protocol.file.allow always
git submodule sync
git submodule update --init --recursive
git config --global protocol.file.allow never
```

3. **Set Up Environment Variables**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   ```
   Then edit `.env` file and add your API keys

3. **Install Dependencies**
   ```bash
   # Install Python dependencies
   poetry install
   
   # Install browser automation dependencies
   poetry run playwright install
   poetry run playwright install-deps
   ```

4. **Run the Bot**
   You can run the bot in three ways:

   a. **Voice Agent**
   ```bash
   PYTHONPATH=$PWD/server/src poetry run python server/src/server/app.py
   ```
   - Once the server is running, load up localhost:3000 in your browser
   - Talk to the agent by clicking the "Start" button and speaking into your microphone

   b. **Terminal Interface**
   ```bash
   poetry run python chatbot.py
   ```
   - Choose between chat mode or autonomous mode
   - Start interacting with blockchain and compute resources!

   c. **Web Interface (Gradio)**
   ```bash
   poetry run python gradio_ui.py
   ```
   - Access the user-friendly web interface
   - Chat with the agent through your browser
   - View responses in a modern chat interface

## Features
- Interactive chat mode for guided interactions
- Autonomous mode for self-directed operations
- Full CDP Agentkit integration for blockchain operations
- Hyperbolic integration for compute operations
- Persistent wallet management
- X (Twitter) integration
- Modern web interface powered by Gradio
- Autonomous browser automation capabilities
