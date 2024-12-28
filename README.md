# Hyperbolic Agentkit x X (Twitter) Chatbot x CDP Agentkit

> **Note:** If running on an Intel Mac, and the agent refuses to run, you may need to change your embedding model from `NomicEmbeddings` to `OpenAIEmbeddings`, as well as comment out the `NomicEmbeddings` import.

This repository is inspired by and modified from Coinbase's [CDP Agentkit](https://github.com/coinbase/cdp-agentkit). We extend our gratitude to the Coinbase Developer Platform team for their original work.


A template for running an AI agent with both blockchain and compute capabilities, plus X posting using:
- [Hyperbolic Compute Platform](https://app.hyperbolic.xyz/)
- [Coinbase Developer Platform (CDP) Agentkit](https://github.com/coinbase/cdp-agentkit/)

This template demonstrates a terminal-based chatbot that can:

Compute Operations (via Hyperbolic):
- Rent and Terminate GPU compute resources
- Check GPU availability
- Check Instance/Spend history
- Check Hyperbolic account balance
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
   Then edit the `.env` file and add your API keys. Additionally, you will need to manually export the following Twitter API credentials in your terminal:
   ```bash
   export TWITTER_ACCESS_TOKEN='...'
   export TWITTER_API_KEY='...'
   export TWITTER_API_SECRET='...'
   export TWITTER_ACCESS_TOKEN_SECRET='...'
   export TWITTER_BEARER_TOKEN='...'
   export TWITTER_CLIENT_ID='...'
   export TWITTER_CLIENT_SECRET='...'
   ```

2. **Install Dependencies**
   ```bash
   poetry install
   ```

3. **Run the Bot**
   ```bash
   poetry run python chatbot.py
   ```
   - Choose between chat mode or autonomous mode
   - Start interacting with blockchain and compute resources!

## Features
- Interactive chat mode for guided interactions
- Autonomous mode for self-directed operations
- Full CDP Agentkit integration for blockchain operations
- Hyperbolic integration for compute operations
- Persistent wallet management
- X (Twitter) integration

## Character Generation

To create a custom AI personality for your bot based on an existing Twitter account:

1. **Clone and Set Up Twitter Scraper**
   ```bash
   git clone https://github.com/elizaOS/twitter-scraper-finetune.git
   cd twitter-scraper-finetune
   npm install
   ```

2. **Configure Scraper Environment**
   - Copy `.env.example` to `.env`
   - Create a new Twitter account specifically for scraping (DO NOT use your main account)
   - Add your scraping account credentials to `.env`:
     ```
     TWITTER_USERNAME=your_scraper_account
     TWITTER_PASSWORD=your_scraper_password
     ```
   Note: This is different from the account that will be used for posting.

3. **Generate Character File**
   Run these commands in sequence:
   ```bash
   # 1. Collect tweets (replace target_username with the account you want to mimic)
   npm run twitter -- target_username

   # 2. Generate Virtuals character card (date should be in the format of YYYY-MM-DD)
   npm run generate-virtuals -- target_username date

   # 3. Generate final character file
   npm run character -- target_username date
   ```

4. **Import Character to Agentkit**
   - In Finder, navigate to `twitter-scraper-finetune/characters`
   - Copy the generated `target_username.json` file
   - Paste the file into the `characters` folder of the Hyperbolic Agentkit project
   - Update the file path in `chatbot.py`:
     ```python
     # Update this line with your character file name
     with open("characters/your_character.json") as f:
     ```

This process will create a personality model based on the target account's posting history and communication style.

## Modifying the Character File

After importing the generated `target_username.json` file into the `characters` folder, you may need to modify the first few lines to match the structure of the `chainyoda.character.json` file. This ensures that the new character file is compatible with the existing setup.

1. Open the `target_username.json` file in a text editor.
2. Modify the top section above the `bio` tag to match the following structure:

```json
{
    "name": "target_username",
    "clients": ["twitter"],
    "modelProvider": "anthropic",
    "plugins": [],
    "bio": [
        #existing bio
    ],
    #rest of file
}
```

3. Save the changes to the `target_username.json` file.

This modification will help ensure that the character behaves as expected within the Hyperbolic Agentkit framework, maintaining consistency with the `chainyoda.character.json` file.
