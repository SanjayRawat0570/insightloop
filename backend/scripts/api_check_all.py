"""Live per-endpoint check of EVERY route, including the WebSocket.

Maps each declared route -> live status. Run with the backend up on :8000.
"""
import os
import asyncio
import json
import uuid

import httpx
import websockets

API = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
WS = API.replace("http", "ws")

rows = []


def rec(method, path, ok, detail=""):
    rows.append((method, path, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {method:6} {path:34} {detail}")


async def main():
    email = f"chk+{uuid.uuid4().hex[:6]}@example.com"
    pw = "password123"
    client_id = f"chk-{uuid.uuid4().hex[:6]}"
    ws_events = []

    async with httpx.AsyncClient(timeout=40) as c:
        r = await c.get(f"{API}/health")
        rec("GET", "/health", r.status_code == 200, str(r.status_code))

        r = await c.post(f"{API}/api/auth/register", json={"email": email, "password": pw})
        ok = r.status_code == 200 and "access_token" in r.json()
        rec("POST", "/api/auth/register", ok, str(r.status_code))
        token = r.json().get("access_token")
        uid = r.json().get("user", {}).get("id")
        H = {"Authorization": f"Bearer {token}"}

        r = await c.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
        rec("POST", "/api/auth/login", r.status_code == 200 and "access_token" in r.json(), str(r.status_code))

        r = await c.post(f"{API}/api/sources", headers=H,
                         json={"name": "chk", "type": "csv", "connection_config": {}})
        src_id = r.json().get("id")
        rec("POST", "/api/sources", r.status_code == 200 and bool(src_id), str(r.status_code))

        r = await c.get(f"{API}/api/sources", headers=H)
        rec("GET", "/api/sources", r.status_code == 200, f"{r.status_code}, {len(r.json().get('items', []))} items")

        r = await c.post(f"{API}/api/sources/{src_id}/schema", headers=H)
        rec("POST", "/api/sources/{id}/schema", r.status_code == 200, str(r.status_code))

        # real sqlite source for the pipeline
        try:
            from db.models import DataSource, SourceType
            from db.mongo import create_data_source
        except ModuleNotFoundError:
            from backend.db.models import DataSource, SourceType
            from backend.db.mongo import create_data_source
        ds = await create_data_source(DataSource(
            user_id=uid, name="chk-sqlite", type=SourceType.postgres,
            connection_config={"connection_url": os.environ.get("SOURCE_DB_URL"), "dialect": "sqlite"},
        ))

        # open WS, then fire the query so we capture live events
        async with websockets.connect(f"{WS}/ws/{client_id}") as sock:
            r = await c.post(f"{API}/api/query", headers=H,
                             json={"question": "total revenue by month", "source_id": ds.id,
                                   "client_id": client_id, "dialect": "sqlite"})
            qid = r.json().get("query_id")
            rec("POST", "/api/query", r.status_code == 200 and bool(qid), str(r.status_code))

            try:
                for _ in range(40):
                    msg = await asyncio.wait_for(sock.recv(), timeout=30)
                    ev = json.loads(msg)
                    ws_events.append(ev.get("type") or ev.get("event") or "msg")
                    if (ev.get("type") in ("complete", "done", "error")
                            or ev.get("status") in ("complete", "done")):
                        break
            except asyncio.TimeoutError:
                pass
        rec("WS", "/ws/{client_id}", len(ws_events) > 0,
            f"{len(ws_events)} events: {ws_events}")

        # poll the query result
        populated = False
        for _ in range(30):
            r = await c.get(f"{API}/api/query/{qid}", headers=H)
            j = r.json()
            if r.status_code == 200 and (j.get("result_cache") or j.get("chart_config")):
                populated = True
                break
            await asyncio.sleep(1)
        rec("GET", "/api/query/{id}", populated,
            f"rows={len(j.get('result_cache') or [])}, sql={bool(j.get('generated_sql'))}")

        r = await c.get(f"{API}/api/query/history", headers=H)
        rec("GET", "/api/query/history", r.status_code == 200, f"{r.status_code}, {len(r.json().get('items', []))} items")

        r = await c.post(f"{API}/api/reports", headers=H,
                         json={"name": "chk-rep", "schedule_cron": "0 9 * * 1", "recipients": ["a@b.com"]})
        rep_id = r.json().get("id")
        rec("POST", "/api/reports", r.status_code == 200 and bool(rep_id), str(r.status_code))

        r = await c.get(f"{API}/api/reports", headers=H)
        rec("GET", "/api/reports", r.status_code == 200, f"{r.status_code}, {len(r.json().get('items', []))} items")

        r = await c.get(f"{API}/api/reports/{rep_id}", headers=H)
        rec("GET", "/api/reports/{id}", r.status_code == 200, str(r.status_code))

        r = await c.post(f"{API}/api/reports/{rep_id}/run", headers=H)
        run_ok = r.status_code == 200 and (r.json().get("result", {}).get("status") == "completed")
        rec("POST", "/api/reports/{id}/run", run_ok,
            f"{r.status_code}, {r.json().get('result', {}).get('pdf_bytes', 0)} pdf bytes")

        r = await c.get(f"{API}/api/reports/{rep_id}/download")
        pdf_ok = r.status_code == 200 and r.content[:4] == b"%PDF"
        rec("GET", "/api/reports/{id}/download", pdf_ok,
            f"{r.status_code}, {len(r.content)} bytes, {r.headers.get('content-type')}")

        r = await c.delete(f"{API}/api/reports/{rep_id}", headers=H)
        rec("DELETE", "/api/reports/{id}", r.status_code == 200, str(r.status_code))

        r = await c.delete(f"{API}/api/sources/{src_id}", headers=H)
        rec("DELETE", "/api/sources/{id}", r.status_code == 200, str(r.status_code))

    passed = sum(1 for *_, ok, _ in [(m, p, ok, d) for m, p, ok, d in rows])  # noqa
    passed = sum(1 for _, _, ok, _ in rows)
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{len(rows)} endpoints working")
    for m, p, ok, d in rows:
        if not ok:
            print(f"  FAIL {m} {p}  ({d})")


if __name__ == "__main__":
    asyncio.run(main())
