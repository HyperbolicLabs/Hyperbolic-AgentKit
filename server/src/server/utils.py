from typing import AsyncIterator
from starlette.websockets import WebSocket, WebSocketDisconnect


async def websocket_stream(websocket: WebSocket) -> AsyncIterator[str]:
    while True:
        try:
            data = await websocket.receive_text()
            yield data
        except WebSocketDisconnect:
            break
        except Exception as e:
            print(f"WebSocket error: {e}")
            break
