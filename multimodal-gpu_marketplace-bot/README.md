# GPU Marketplace Voice Assistant Bot

An interactive voice assistant bot that helps users explore and find GPU instances on the Hyperbolic GPU Marketplace.

## Features

- **Real-time GPU Availability**: Live access to Hyperbolic's GPU marketplace
- **Voice Interaction**: Natural conversation about GPU options and pricing
- **Smart Filtering**:
  - Price ranges (budget to high-end)
  - GPU quantities (1X to 8X+)
  - Storage capacity
  - Availability status
- **Dynamic Price Display**:
  - Under $1: Shows in cents (e.g., "13¢/hr")
  - $1 and above: Shows in dollars (e.g., "$1.50/hr")

## Available GPU Types

- Consumer GPUs (RTX 3070, 3080, 4090)
- Data Center GPUs (H100 SXM, NVIDIA H200)
- Various configurations (1X to 8X+)

## Requirements

- Python 3.12+
- Google API key (for Gemini)
- Daily.co API key
- Access to Hyperbolic Marketplace API

## Environment Setup

Create a `.env` file with:

```
GOOGLE_API_KEY=your_google_api_key
DAILY_API_KEY=your_daily_api_key
DAILY_SAMPLE_ROOM_URL=your_daily_room_url
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Start the bot:

```bash
python main.py
```

Join the Daily.co room to interact with the bot. You can:

- Ask about available GPUs
- Filter by price range
- Sort by price (low to high or high to low)
- Filter by GPU quantity
- Check storage options
- Get real-time availability updates

## Example Queries

- "What GPUs are available?"
- "Show me budget options under 50 cents per hour"
- "What are your high-end GPUs?"
- "Do you have any 8X GPU configurations?"
- "Show me GPUs with over 500GB storage"
- "What's the price range for H100s?"

## Notes

- All GPU instances are located in US, North America
- Prices are always displayed per hour
- The bot automatically refreshes data for the most current availability
