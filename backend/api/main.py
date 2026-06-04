from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from jose import JWTError, jwt
import os

from fastapi import APIRouter
from backend.db.mongo import ensure_indexes

app = FastAPI(title="InsightLoop API")


@app.on_event("startup")
async def _startup_indexes():
    await ensure_indexes()

# Simple in-memory websocket manager
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
            await ws.send_json(event)

manager = ConnectionManager()

# CORS
frontend = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT dependency
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")

async def verify_jwt(token: str = Depends(lambda: None)):
    # Minimal placeholder dependency. Real routes should replace this.
    return None


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            # Keep alive; receive messages optionally
            data = await websocket.receive_text()
            # echo back for now
            await manager.send_event(client_id, {"event": "echo", "message": data})
    except WebSocketDisconnect:
        manager.disconnect(client_id)


@app.get("/health")
async def health():
    return {"status": "ok"}

# Mount routers (placeholder)
from fastapi import APIRouter

api_router = APIRouter()

@api_router.post("/auth/login")
async def login():
    return {"access_token": "devtoken"}

app.include_router(api_router, prefix="/api")
