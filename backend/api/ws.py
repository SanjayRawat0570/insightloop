from fastapi import WebSocket
from typing import Dict


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_event(self, client_id: str, event: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(event)
            except Exception:
                # ignore send errors; client may have disconnected
                pass


manager = ConnectionManager()
