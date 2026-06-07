"""Full API smoke test for InsightLoop.

Exercises every endpoint and prints a PASS/FAIL table. Requires the backend
running on http://localhost:8000 with MONGODB_URL + SOURCE_DB_URL configured.
"""
import os
import asyncio
import uuid

import httpx

try:
    from backend.db.models import DataSource, SourceType
    from backend.db.mongo import create_data_source
except ModuleNotFoundError:
    from db.models import DataSource, SourceType
    from db.mongo import create_data_source

API = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
SOURCE_DB_URL = os.environ.get("SOURCE_DB_URL")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  -> {detail}" if detail else ""))


async def main():
    email = f"smoke+{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    async with httpx.AsyncClient(timeout=40) as c:
        # 1. health
        r = await c.get(f"{API}/health")
        check("GET /health", r.status_code == 200 and r.json().get("status") == "ok", str(r.status_code))

        # 2. register
        r = await c.post(f"{API}/api/auth/register", json={"email": email, "password": password})
        ok = r.status_code == 200 and "access_token" in r.json()
        check("POST /api/auth/register", ok, str(r.status_code))
        token = r.json().get("access_token") if ok else None
        user_id = r.json().get("user", {}).get("id") if ok else None

        # 2b. register duplicate -> 409
        r = await c.post(f"{API}/api/auth/register", json={"email": email, "password": password})
        check("POST /api/auth/register (dup -> 409)", r.status_code == 409, str(r.status_code))

        # 2c. register short password -> 400
        r = await c.post(f"{API}/api/auth/register", json={"email": f"x{uuid.uuid4().hex[:5]}@e.com", "password": "short"})
        check("POST /api/auth/register (short pw -> 400)", r.status_code == 400, str(r.status_code))

        # 3. login
        r = await c.post(f"{API}/api/auth/login", json={"email": email, "password": password})
        check("POST /api/auth/login", r.status_code == 200 and "access_token" in r.json(), str(r.status_code))

        # 3b. login wrong password -> 401
        r = await c.post(f"{API}/api/auth/login", json={"email": email, "password": "wrongpass1"})
        check("POST /api/auth/login (bad pw -> 401)", r.status_code == 401, str(r.status_code))

        H = {"Authorization": f"Bearer {token}"}

        # 4. auth guard: no token -> 401/403
        r = await c.get(f"{API}/api/sources")
        check("GET /api/sources (no auth -> 401/403)", r.status_code in (401, 403), str(r.status_code))

        # 5. create source (csv, skips live connection test)
        r = await c.post(f"{API}/api/sources", headers=H,
                         json={"name": "smoke-csv", "type": "csv", "connection_config": {}})
        ok = r.status_code == 200 and r.json().get("id")
        check("POST /api/sources (csv)", ok, str(r.status_code))
        csv_source_id = r.json().get("id") if ok else None

        # 5b. create source bad type -> 400
        r = await c.post(f"{API}/api/sources", headers=H,
                         json={"name": "bad", "type": "oracle", "connection_config": {}})
        check("POST /api/sources (bad type -> 400)", r.status_code == 400, str(r.status_code))

        # 6. list sources
        r = await c.get(f"{API}/api/sources", headers=H)
        ok = r.status_code == 200 and any(s["id"] == csv_source_id for s in r.json().get("items", []))
        check("GET /api/sources", ok, f"{r.status_code}, {len(r.json().get('items', []))} items")

        # 7. schema endpoint (csv -> empty tables, valid 200)
        r = await c.post(f"{API}/api/sources/{csv_source_id}/schema", headers=H)
        check("POST /api/sources/{id}/schema", r.status_code == 200 and "tables" in r.json(), str(r.status_code))

        # 8. create a real (sqlite) source directly in Mongo for the pipeline
        ds = await create_data_source(DataSource(
            user_id=user_id, name="smoke-sqlite", type=SourceType.postgres,
            connection_config={"connection_url": SOURCE_DB_URL, "dialect": "sqlite"},
        ))
        check("create sqlite source (mongo)", bool(ds.id), ds.id)

        # 9. submit query
        client_id = f"smoke-{uuid.uuid4().hex[:6]}"
        r = await c.post(f"{API}/api/query", headers=H,
                         json={"question": "total revenue by month", "source_id": ds.id,
                               "client_id": client_id, "dialect": "sqlite"})
        ok = r.status_code == 200 and r.json().get("query_id")
        check("POST /api/query", ok, str(r.status_code))
        query_id = r.json().get("query_id") if ok else None

        # 9b. submit query missing fields -> 400
        r = await c.post(f"{API}/api/query", headers=H, json={"question": "x"})
        check("POST /api/query (missing fields -> 400)", r.status_code == 400, str(r.status_code))

        # 10. poll GET /api/query/{id} until pipeline populates it
        populated = False
        for _ in range(30):
            r = await c.get(f"{API}/api/query/{query_id}", headers=H)
            if r.status_code == 200 and (r.json().get("chart_config") or r.json().get("result_cache")):
                populated = True
                break
            await asyncio.sleep(1)
        detail = ""
        if populated:
            j = r.json()
            detail = f"sql set={bool(j.get('generated_sql'))}, rows={len(j.get('result_cache') or [])}, chart={(j.get('chart_config') or {}).get('chart_type')}"
        check("GET /api/query/{id} (pipeline result)", populated, detail)

        # 11. query history
        r = await c.get(f"{API}/api/query/history", headers=H)
        check("GET /api/query/history", r.status_code == 200 and "items" in r.json(),
              f"{r.status_code}, {len(r.json().get('items', []))} items")

        # 12. reports: create valid
        r = await c.post(f"{API}/api/reports", headers=H,
                         json={"name": "smoke-report", "schedule_cron": "0 9 * * 1", "recipients": ["a@b.com"]})
        ok = r.status_code == 200 and r.json().get("id")
        check("POST /api/reports", ok, str(r.status_code))
        report_id = r.json().get("id") if ok else None

        # 12b. reports: bad cron -> 400
        r = await c.post(f"{API}/api/reports", headers=H,
                         json={"name": "bad-cron", "schedule_cron": "not a cron"})
        check("POST /api/reports (bad cron -> 400)", r.status_code == 400, str(r.status_code))

        # 13. list reports
        r = await c.get(f"{API}/api/reports", headers=H)
        check("GET /api/reports", r.status_code == 200 and "items" in r.json(),
              f"{r.status_code}, {len(r.json().get('items', []))} items")

        # 14. get report
        r = await c.get(f"{API}/api/reports/{report_id}", headers=H)
        check("GET /api/reports/{id}", r.status_code == 200 and r.json().get("id") == report_id, str(r.status_code))

        # 15. run report
        r = await c.post(f"{API}/api/reports/{report_id}/run", headers=H)
        check("POST /api/reports/{id}/run", r.status_code == 200 and r.json().get("status") == "triggered", str(r.status_code))

        # 16. delete report
        r = await c.delete(f"{API}/api/reports/{report_id}", headers=H)
        check("DELETE /api/reports/{id}", r.status_code == 200, str(r.status_code))

        # 17. delete source
        r = await c.delete(f"{API}/api/sources/{csv_source_id}", headers=H)
        check("DELETE /api/sources/{id}", r.status_code == 200, str(r.status_code))

    # summary
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 50)
    print(f"RESULT: {passed}/{total} checks passed")
    if passed != total:
        print("FAILURES:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}  ({detail})")


if __name__ == "__main__":
    asyncio.run(main())
