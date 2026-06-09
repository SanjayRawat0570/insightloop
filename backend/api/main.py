from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything else reads env vars.
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)
load_dotenv(BACKEND_DIR.parent / ".env", override=False)

try:
    from backend.utils.logging_config import setup_logging, get_logger
    from backend.db.mongo import ensure_indexes
    from backend.api.ws import manager
    from backend.api.routes import auth, query, sources, reports
except ModuleNotFoundError:
    from utils.logging_config import setup_logging, get_logger
    from db.mongo import ensure_indexes
    from api.ws import manager
    from api.routes import auth, query, sources, reports

# Configure logging before anything logs.
setup_logging()
logger = get_logger("api")
req_log = get_logger("request")

app = FastAPI(title="InsightLoop API", version="1.0.0")

# CORS — allow frontend origin
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    # Accept localhost / 127.0.0.1 on any port in dev so a preflight from
    # http://127.0.0.1:3000 or a fallback port (3001, …) isn't rejected with 400.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One concise line per HTTP call: method, path, status, duration."""
    # Skip CORS preflight noise.
    if request.method == "OPTIONS":
        return await call_next(request)

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # unhandled error in a handler
        ms = int((time.perf_counter() - start) * 1000)
        req_log.error("%-6s %s -> 500 in %dms (%s)", request.method, request.url.path, ms, exc)
        raise

    ms = int((time.perf_counter() - start) * 1000)
    status = response.status_code
    line = "%-6s %s -> %d in %dms"
    args = (request.method, request.url.path, status, ms)
    if status >= 500:
        req_log.error(line, *args)
    elif status >= 400:
        req_log.warning(line, *args)
    else:
        req_log.info(line, *args)
    return response


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
    try:
        from backend.agents.llm import llm_status
    except ModuleNotFoundError:
        from agents.llm import llm_status
    return {"status": "ok", "llm": llm_status()}


# WebSocket — streams agent events to frontend
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    logger.info("ws connect client=%s (%d active)", client_id, len(manager.active_connections))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info("ws disconnect client=%s (%d active)", client_id, len(manager.active_connections))


# Mount all API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

