import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_openai_voice.utils import amerge  # First import utils to check if the path is correct
from langchain_openai_voice import OpenAIVoiceReactAgent

from server.utils import websocket_stream
# from server.prompt import INSTRUCTIONS
from server.tools import TOOLS

from chatbot import loadCharacters, process_character_config
import os
from server.prompt import BASE_INSTRUCTIONS
from chatbot import loadCharacters, process_character_config
import os


async def websocket_endpoint(websocket: WebSocket):
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
        topics=", ".join(character.get("topics", []))
    )
    print("Full instructions:", full_instructions)
    for tool in TOOLS:
        print(tool.name)

    
    agent = OpenAIVoiceReactAgent(
        model="gpt-4o-realtime-preview",
        tools=TOOLS,
        instructions=full_instructions,
        voice="verse" #"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", and "verse"
    )

    await agent.aconnect(browser_receive_stream, websocket.send_text)


async def homepage(request):
    with open("server/src/server/static/index.html") as f:
        html = f.read()
        return HTMLResponse(html)

routes = [Route("/", homepage), WebSocketRoute("/ws", websocket_endpoint)]

app = Starlette(debug=True, routes=routes)

app.mount("/", StaticFiles(directory="server/src/server/static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)