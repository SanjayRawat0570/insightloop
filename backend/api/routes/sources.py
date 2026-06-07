from __future__ import annotations

import json
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

try:
    from backend.api.auth import get_current_user
    from backend.db.models import DataSource, SourceType
    from backend.db.mongo import (
        create_data_source,
        get_data_source,
        get_mongo_db,
    )
    from backend.utils.crypto import encrypt_connection_config, decrypt_connection_config
    from backend.utils.schema_parser import parse_schema_from_connection_async
except ModuleNotFoundError:
    from api.auth import get_current_user
    from db.models import DataSource, SourceType
    from db.mongo import (
        create_data_source,
        get_data_source,
        get_mongo_db,
    )
    from utils.crypto import encrypt_connection_config, decrypt_connection_config
    from utils.schema_parser import parse_schema_from_connection_async

router = APIRouter()


async def _list_user_sources(user_id: str):
    db = get_mongo_db()
    docs = await db.data_sources.find({"user_id": user_id, "is_active": True}).to_list(length=200)
    return docs


@router.post("")
async def create_source(body: Dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    name = body.get("name")
    source_type = body.get("type")
    connection_config = body.get("connection_config") or {}

    if not name or not source_type:
        raise HTTPException(status_code=400, detail="name and type are required")

    try:
        SourceType(source_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"unsupported source type: {source_type}")

    # Best-effort connection test for SQL sources. We attempt it so a reachable
    # database gets validated, but a failure does NOT block saving — queries fall
    # back to the bundled sample database when a source is unreachable.
    connection_ok = None
    if source_type in ("postgres", "mysql"):
        try:
            await parse_schema_from_connection_async({**connection_config, "dialect": source_type})
            connection_ok = True
        except Exception:
            connection_ok = False

    encrypted = encrypt_connection_config(connection_config)
    ds = DataSource(
        user_id=user_id,
        name=name,
        type=SourceType(source_type),
        connection_config=encrypted,
    )
    await create_data_source(ds)
    return {
        "id": ds.id,
        "name": ds.name,
        "type": ds.type,
        "created_at": ds.created_at.isoformat(),
        "connection_ok": connection_ok,
    }


@router.get("")
async def list_sources(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    docs = await _list_user_sources(user_id)
    items = [
        {
            "id": str(d.get("_id")),
            "name": d.get("name"),
            "type": d.get("type"),
            "is_active": d.get("is_active"),
            "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
        }
        for d in docs
    ]
    return {"items": items}


@router.delete("/{source_id}")
async def delete_source(source_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    ds = await get_data_source(source_id)
    if not ds or str(ds.user_id) != str(user_id):
        raise HTTPException(status_code=404, detail="source not found")
    db = get_mongo_db()
    await db.data_sources.update_one({"_id": source_id}, {"$set": {"is_active": False}})
    return {"status": "deleted"}


@router.post("/{source_id}/schema")
async def get_schema(source_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    ds = await get_data_source(source_id)
    if not ds or str(ds.user_id) != str(user_id):
        raise HTTPException(status_code=404, detail="source not found")

    cfg = decrypt_connection_config(ds.connection_config or {})
    dialect = ds.type.value if hasattr(ds.type, "value") else str(ds.type)

    # Try the source's own connection first.
    schema = None
    if dialect in ("postgres", "mysql") or cfg.get("connection_url"):
        try:
            schema = await parse_schema_from_connection_async({**cfg, "dialect": dialect})
            if not schema.get("tables"):
                schema = None  # reachable but empty / non-SQL → use sample below
        except Exception:
            schema = None

    # Fall back to the bundled sample database so the schema browser always shows
    # the data that queries will actually run against (matches the query-time
    # fallback for unreachable sources).
    if schema is None:
        import os as _os
        fallback_url = _os.environ.get("SOURCE_DB_URL") or _os.environ.get("DATABASE_URL")
        if fallback_url:
            try:
                fb_dialect = "sqlite" if fallback_url.lower().startswith("sqlite") else "postgres"
                schema = await parse_schema_from_connection_async(
                    {"connection_url": fallback_url, "dialect": fb_dialect}
                )
                schema["fallback"] = True
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"schema fetch failed: {exc}")
        else:
            raise HTTPException(status_code=422, detail="schema unavailable and no fallback database configured")

    return schema
