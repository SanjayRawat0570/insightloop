from __future__ import annotations

import asyncio
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
    from backend.connectors import materialize_source, SourceLoadError
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
    from connectors import materialize_source, SourceLoadError

try:
    from backend.utils.logging_config import get_logger
except ModuleNotFoundError:
    from utils.logging_config import get_logger

router = APIRouter()
log = get_logger("sources")


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

    # Best-effort connection test. SQL sources are validated by introspecting the
    # schema; API/Sheets/CSV sources by actually fetching + materializing their
    # data. A failure does NOT block saving (the user may be fixing config), but
    # the flag tells the UI whether the real data is reachable.
    log.info("connect request name=%r type=%s user=%s", name, source_type, user_id)
    connection_ok = None
    try:
        if source_type in ("postgres", "mysql"):
            await parse_schema_from_connection_async({**connection_config, "dialect": source_type})
        else:
            await asyncio.to_thread(materialize_source, source_type, connection_config, None)
        connection_ok = True
    except Exception as exc:
        connection_ok = False
        log.warning("connection test failed type=%s: %s", source_type, exc)

    log.info("connect saved type=%s connection_ok=%s", source_type, connection_ok)
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
    log.info("delete source=%s user=%s", source_id, user_id)
    return {"status": "deleted"}


@router.post("/{source_id}/schema")
async def get_schema(source_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    ds = await get_data_source(source_id)
    if not ds or str(ds.user_id) != str(user_id):
        raise HTTPException(status_code=404, detail="source not found")

    cfg = decrypt_connection_config(ds.connection_config or {})
    source_type = ds.type.value if hasattr(ds.type, "value") else str(ds.type)
    log.info("schema request source=%s type=%s name=%r", source_id, source_type, ds.name)

    # Materialize the source's REAL data, then introspect that store so the
    # schema browser shows exactly what queries will run against.
    try:
        mat = await asyncio.to_thread(materialize_source, source_type, cfg, source_id)
    except SourceLoadError as exc:
        log.warning("schema materialize failed source=%s: %s", source_id, exc)
        raise HTTPException(status_code=422, detail=f"could not load source data: {exc}")
    except Exception as exc:
        log.warning("schema materialize failed source=%s: %s", source_id, exc)
        raise HTTPException(status_code=422, detail=f"could not load source data: {exc}")

    try:
        schema = await parse_schema_from_connection_async(
            {**cfg, "connection_url": mat.db_url, "dialect": mat.dialect}
        )
    except Exception as exc:
        log.warning("schema introspect failed source=%s: %s", source_id, exc)
        raise HTTPException(status_code=422, detail=f"schema fetch failed: {exc}")

    if not schema.get("tables"):
        log.warning("schema empty source=%s type=%s", source_id, source_type)
        raise HTTPException(status_code=422, detail="source has no tables to query")

    log.info("schema ready source=%s tables=%d", source_id, len(schema.get("tables", [])))
    schema["source_type"] = source_type
    schema["live"] = mat.live
    return schema
