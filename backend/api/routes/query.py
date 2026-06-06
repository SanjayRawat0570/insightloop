from __future__ import annotations

import asyncio
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

try:
    from backend.graph.pipeline import run_pipeline
    from backend.api.auth import get_current_user
    from backend.db.mongo import get_query as mongo_get_query, list_queries_by_user
except ModuleNotFoundError:
    from graph.pipeline import run_pipeline
    from api.auth import get_current_user
    from db.mongo import get_query as mongo_get_query, list_queries_by_user

router = APIRouter()


# IMPORTANT: /query/history must be declared BEFORE /query/{query_id}
# so FastAPI doesn't treat "history" as a query_id path parameter.
@router.get("/query/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    items = await list_queries_by_user(user_id)
    return {"items": [item.model_dump() for item in items]}


@router.post("/query")
async def submit_query(body: Dict, current_user: dict = Depends(get_current_user)):
    question = body.get("question")
    source_id = body.get("source_id")
    client_id = body.get("client_id")
    if not all([question, source_id, client_id]):
        raise HTTPException(status_code=400, detail="question, source_id, and client_id are required")

    query_id = str(uuid4())
    state = {
        "question": question,
        "source_id": source_id,
        "schema": body.get("schema"),
        "dialect": body.get("dialect", "postgres"),
        "sql": None,
        "sql_result": None,
        "analysis": None,
        "chart_config": None,
        "narrative": None,
        "report": None,
        "error": None,
        "current_node": None,
        "user": current_user,
    }

    asyncio.create_task(run_pipeline(state, client_id, query_id))
    return {"query_id": query_id}


@router.get("/query/{query_id}")
async def get_query(query_id: str):
    query = await mongo_get_query(query_id)
    if not query:
        raise HTTPException(status_code=404, detail="query not found")
    return query.model_dump()
