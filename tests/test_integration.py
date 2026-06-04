import os
import asyncio
import uuid
import pytest
from httpx import AsyncClient
from jose import jwt

from backend.api.main import app
from backend.db.models import User, DataSource, Query, AgentRun, SourceType
from backend.db.mongo import create_user, create_data_source, get_query as mongo_get_query, list_agent_runs_by_query


@pytest.mark.asyncio
async def test_full_pipeline_creates_query_and_agent_runs():
    # create test user and datasource in MongoDB
    user = await create_user(User(email=f"test+{uuid.uuid4().hex[:6]}@example.com", hashed_password="x"))
    ds = await create_data_source(
        DataSource(
            user_id=user.id,
            name="test-db",
            type=SourceType.postgres,
            connection_config={"connection_url": os.environ.get("SOURCE_DB_URL") or os.environ.get("DATABASE_URL")},
        )
    )

    secret = os.environ.get("JWT_SECRET", "dev-secret")
    alg = os.environ.get("JWT_ALGORITHM", "HS256")
    token = jwt.encode({"sub": str(user.id)}, secret, algorithm=alg)

    payload = {"question": "select 1", "source_id": str(ds.id), "client_id": "pytest-client"}

    async with AsyncClient(app=app, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/query", json=payload, headers=headers, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "query_id" in data

    # give background pipeline a moment to run
    await asyncio.sleep(1)

    query = await mongo_get_query(data["query_id"])
    assert query is not None
    runs = await list_agent_runs_by_query(query.id)
    assert len(runs) >= 1
