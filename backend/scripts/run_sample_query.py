"""Create a test user+datasource, generate JWT, POST /api/query, and stream websocket events.

Prereqs: backend running at http://localhost:8000 and env configured (`MONGODB_URL`, `MONGODB_DB`, `SOURCE_DB_URL`, `JWT_SECRET`).
Install extras: `pip install httpx websockets python-jose` if not present.
Run: `python backend/scripts/run_sample_query.py`
"""
import os
import asyncio
import json
import uuid

from jose import jwt
from httpx import AsyncClient

try:
    from backend.db.models import User, DataSource, SourceType
    from backend.db.mongo import create_user, create_data_source
except ModuleNotFoundError:
    from db.models import User, DataSource, SourceType
    from db.mongo import create_user, create_data_source


async def ensure_test_data():
    user = await create_user(User(email=f"test+{uuid.uuid4().hex[:6]}@example.com", hashed_password="x"))
    ds = await create_data_source(
        DataSource(
            user_id=user.id,
            name="local-db",
            type=SourceType.postgres,
            connection_config={"connection_url": os.environ.get("SOURCE_DB_URL") or os.environ.get("DATABASE_URL")},
        )
    )
    return user, ds


async def main():
    api_base = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
    user, ds = await ensure_test_data()

    secret = os.environ.get("JWT_SECRET", "dev-secret")
    alg = os.environ.get("JWT_ALGORITHM", "HS256")
    token = jwt.encode({"sub": str(user.id)}, secret, algorithm=alg)

    print("Created test user:", str(user.id))
    print("Created data source:", str(ds.id))
    print("JWT (use as Bearer token):\n", token)

    payload = {"question": "select 1", "source_id": str(ds.id), "client_id": "sample-client"}

    async with AsyncClient() as c:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await c.post(f"{api_base}/api/query", json=payload, headers=headers, timeout=30)
        print("POST /api/query ->", resp.status_code, resp.text)

    # Optionally connect to websocket to stream events
    try:
        import websockets

        ws_url = (os.environ.get("WS_URL") or "ws://localhost:8000") + "/ws/sample-client"
        print("Connecting to websocket:", ws_url)

        async with websockets.connect(ws_url) as ws:
            print("Connected, listening for 10s of events...")
            for _ in range(20):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    print("WS:", msg)
                except asyncio.TimeoutError:
                    break
    except Exception as e:
        print("Websocket streaming skipped or failed:", e)


if __name__ == "__main__":
    asyncio.run(main())
