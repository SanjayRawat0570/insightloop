"""End-to-end flow test against a running backend.

Registers a user via the API, creates a SQLite data source directly in Mongo,
submits a query, and streams the agent pipeline events over the WebSocket until
pipeline_complete / pipeline_error.
"""
import os
import asyncio
import json
import uuid

import httpx
import websockets

try:
    from backend.db.models import User, DataSource, SourceType
    from backend.db.mongo import find_user_by_email, create_data_source
except ModuleNotFoundError:
    from db.models import User, DataSource, SourceType
    from db.mongo import find_user_by_email, create_data_source

API = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
WS = os.environ.get("WS_URL", "ws://localhost:8000")
SOURCE_DB_URL = os.environ.get("SOURCE_DB_URL")


async def main():
    email = f"flow+{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    client_id = f"flow-{uuid.uuid4().hex[:6]}"

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API}/api/auth/register", json={"email": email, "password": password})
        print("REGISTER ->", r.status_code)
        data = r.json()
        token = data["access_token"]
        user_id = data["user"]["id"]
        print("  user:", email, user_id)

        # Create a data source owned by this user, pointing at the SQLite sample DB.
        ds = await create_data_source(
            DataSource(
                user_id=user_id,
                name="sample-sqlite",
                type=SourceType.postgres,  # dialect override handled via connection_url
                connection_config={"connection_url": SOURCE_DB_URL, "dialect": "sqlite"},
            )
        )
        print("  source:", ds.id)

        # Open the WS BEFORE submitting so we catch every event.
        ws_url = f"{WS}/ws/{client_id}"
        async with websockets.connect(ws_url) as ws:
            print("WS connected ->", ws_url)

            payload = {
                "question": "What is total revenue by month?",
                "source_id": ds.id,
                "client_id": client_id,
                "dialect": "sqlite",
            }
            headers = {"Authorization": f"Bearer {token}"}
            qr = await c.post(f"{API}/api/query", json=payload, headers=headers)
            print("POST /api/query ->", qr.status_code, qr.text)

            final = None
            for _ in range(60):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    print("  (timeout waiting for events)")
                    break
                evt = json.loads(msg)
                etype = evt.get("event")
                node = evt.get("node", "")
                pl = evt.get("payload")
                line = f"  EVENT {etype:18s} {node}"
                if pl and etype in ("node_complete", "pipeline_error"):
                    line += "  " + json.dumps(pl)[:160]
                print(line)
                if etype in ("pipeline_complete", "pipeline_error"):
                    final = evt
                    break

    print("\n===== FINAL =====")
    if final and final.get("event") == "pipeline_complete":
        res = final["payload"]["result"]
        print("SQL        :", res.get("generated_sql"))
        print("Rows       :", len(res.get("result_cache") or []))
        print("Chart type :", (res.get("chart_config") or {}).get("chart_type"))
        print("Headline   :", (res.get("narrative") or {}).get("headline"))
        print("Report     :", (res.get("report") or {}).get("title"))
    else:
        print(json.dumps(final, indent=2) if final else "no final event")


if __name__ == "__main__":
    asyncio.run(main())
