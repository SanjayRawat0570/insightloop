from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything else reads env vars.
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)
load_dotenv(BACKEND_DIR.parent / ".env", override=False)

try:
    from backend.db.mongo import ensure_indexes
    from backend.api.ws import manager
    from backend.api.routes import auth, query, sources, reports
except ModuleNotFoundError:
    from db.mongo import ensure_indexes
    from api.ws import manager
    from api.routes import auth, query, sources, reports

logger = logging.getLogger(__name__)

app = FastAPI(title="InsightLoop API", version="1.0.0")

# CORS — allow frontend origin
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    try:
        await ensure_indexes()
        logger.info("MongoDB indexes ensured")
    except Exception as exc:
        logger.warning("Skipping Mongo index initialization: %s", exc)


@app.on_event("shutdown")
async def _shutdown():
    pass


# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}


# WebSocket — streams agent events to frontend
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)


# Mount all API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
