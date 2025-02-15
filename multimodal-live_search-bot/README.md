# Gemini Search Bot

A conversational AI bot that provides the latest news and information using Google's Gemini model and search capabilities.

## Features

- Real-time voice interaction using Daily.co
- Latest news retrieval using Google Search API
- Natural conversation with Gemini AI model
- Voice synthesis for bot responses
- Voice activity detection for smooth interaction

## Prerequisites

- Python 3.8+
- A Daily.co API key
- A Google Gemini API key

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

## Environment Variables

Create a `.env` file with the following variables:

```
# Required
DAILY_API_KEY=your_daily_api_key
GEMINI_API_KEY=your_gemini_api_key

# Optional
DAILY_SAMPLE_ROOM_URL=your_daily_room_url  # URL of an existing Daily room
DAILY_API_URL=https://api.daily.co/v1      # Custom Daily API URL
```

## Usage

Run the bot with default settings (will create a new Daily room):
```bash
python src/main.py
```

Or specify an existing Daily room:
```bash
python src/main.py --url https://your-domain.daily.co/room-name
```

Command line options:
- `-u, --url`: URL of the Daily room to join
- `-k, --apikey`: Daily API Key (can also be set in .env)

The bot will:
1. Connect to the specified Daily room (or create a new one)
2. Print the room URL
3. Wait for a participant to join
4. Start the conversation with news-related queries

## Project Structure

```
gemini-search-bot/
├── src/
│   ├── config/
│   │   └── settings.py     # Configuration settings
│   ├── services/
│   │   └── daily.py        # Daily.co service setup
│   ├── utils/
│   │   └── logger.py       # Logging configuration
│   └── main.py             # Main application
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## License

BSD 2-Clause License