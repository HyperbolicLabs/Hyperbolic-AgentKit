# Hyperbolic Agentkit x X (Twitter) Chatbot x CDP Agentkit

This repository is inspired by and modified from Coinbase's [CDP Agentkit](https://github.com/coinbase/cdp-agentkit). We extend our gratitude to the Coinbase Developer Platform team for their original work.


A template for running an AI agent with both blockchain and compute capabilities, plus X posting using:
- [Hyperbolic Compute Platform](https://app.hyperbolic.xyz/)
- [Coinbase Developer Platform (CDP) Agentkit](https://github.com/coinbase/cdp-agentkit/)

This template demonstrates a chatbot that can:

Compute Operations (via Hyperbolic):
- Rent GPU compute resources
- Check GPU availability
- Monitor GPU status
- Access to GPU machines
- Run command lines on remote GPU machines

Blockchain Operations (via CDP):
- Deploy tokens (ERC-20 & NFTs)
- Manage wallets
- Execute transactions
- Interact with smart contracts
- Post on X

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

3. **Browser Automation**
   - Install Playwright browsers after installing dependencies:
   ```bash
   poetry run playwright install
   ```

## Quick Start

1. **Set Up Environment Variables**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   ```
   Then edit `.env` file and add your API keys

2. **Install Dependencies**
   ```bash
   poetry install
   ```

3. **Run the Bot**
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

   b. **Web Interface (Gradio)**
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


```