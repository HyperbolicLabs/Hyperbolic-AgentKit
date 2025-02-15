# Multimodal Video Bot

A video conferencing bot that can analyze screen shares and camera feeds using Gemini's multimodal capabilities.

## Features

- **Prioritized Screen Sharing**: Automatically attempts to capture screen sharing first, falling back to camera if unavailable
- **Voice Activation Detection (VAD)**: Uses Silero VAD for precise audio detection
- **Multimodal Analysis**: Processes both visual and audio inputs using Google's Gemini API
- **Interactive Response**: Provides real-time responses to user queries about visual content

## Requirements

- Python 3.12+
- Google API key with access to Gemini API
- Daily.co API key
- See `requirements.txt` for complete dependencies

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

Run the bot:

```bash
python src/main.py
```

Or with explicit room URL:

```bash
python src/main.py -u "https://your-domain.daily.co/room" -k "your-daily-api-key"
```

## Voice Options

The bot supports multiple voice options:
- Aoede (default)
- Puck
- Charon
- Kore
- Fenrir

## Rate Limiting

The service implements automatic rate limiting and retry mechanisms when interacting with Google's APIs to prevent quota exhaustion.
