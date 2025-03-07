import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from dotenv import load_dotenv
import os
import json
import psutil

load_dotenv(override=True)

from langchain_openai_voice.utils import (
    amerge,
)  # First import utils to check if the path is correct
from langchain_openai_voice import OpenAIVoiceReactAgent

from server.utils import websocket_stream

# from server.prompt import INSTRUCTIONS
from server.tools import TOOLS

from chatbot import loadCharacters, process_character_config
import os
from server.prompt import BASE_INSTRUCTIONS
from chatbot import loadCharacters, process_character_config
import os

# Track active connections
active_connections = 0
MAX_CONNECTIONS_PER_INSTANCE = 10


async def websocket_endpoint(websocket: WebSocket):
    global active_connections

    # Connection limiting
    if active_connections >= MAX_CONNECTIONS_PER_INSTANCE:
        await websocket.accept()
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "message": "Server at capacity. Please try again later.",
                }
            )
        )
        await websocket.close()
        return

    active_connections += 1
    try:
        await websocket.accept()

        browser_receive_stream = websocket_stream(websocket)

        # Load character configuration
        print("Loading character configuration")
        character = loadCharacters(os.getenv("CHARACTER_FILE", "rolypoly.json"))[0]
        personality = process_character_config(character)

        # Combine base instructions with character config
        full_instructions = BASE_INSTRUCTIONS.format(
            character_instructions=personality,
            character_name=character["name"],
            adjectives=", ".join(character.get("adjectives", [])),
            topics=", ".join(character.get("topics", [])),
        )
        print("Full instructions:", full_instructions)
        for tool in TOOLS:
            print(tool.name)

        agent = OpenAIVoiceReactAgent(
            model="gpt-4o-realtime-preview",
            tools=TOOLS,
            instructions=full_instructions,
            voice="verse",  # "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", and "verse"
        )

        await agent.aconnect(browser_receive_stream, websocket.send_text)
    finally:
        active_connections -= 1


async def homepage(request):
    with open("server/src/server/static/index.html") as f:
        html = f.read()
        return HTMLResponse(html)


async def health_check(request):
    # Get system metrics
    memory = psutil.virtual_memory()

    # Check if we're in a healthy state
    is_healthy = (
        memory.percent < 90 and active_connections < MAX_CONNECTIONS_PER_INSTANCE
    )

    # Return detailed health information
    return JSONResponse(
        {
            "status": "healthy" if is_healthy else "unhealthy",
            "memory": {
                "used_percent": memory.percent,
                "available_mb": memory.available / (1024 * 1024),
            },
            "connections": {
                "active": active_connections,
                "max": MAX_CONNECTIONS_PER_INSTANCE,
            },
        },
        status_code=200 if is_healthy else 503,
    )


routes = [
    Route("/", homepage),
    Route("/health", health_check),
    WebSocketRoute("/ws", websocket_endpoint),
]

app = Starlette(debug=True, routes=routes)

app.mount("/", StaticFiles(directory="server/src/server/static"), name="static")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
