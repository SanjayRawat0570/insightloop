import os
import time
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

try:
    from backend.utils.sql_guard import assert_read_only
except ModuleNotFoundError:
    from utils.sql_guard import assert_read_only


async def run_sql_on_url(db_url: str, sql: str) -> Tuple[List[Dict[str, Any]], int]:
    """Execute read-only SQL against db_url and return rows and execution_ms."""
    # Final safety net: reject any mutating/DDL statement (UPDATE/DELETE/DROP/...)
    # with the same regex guardrail the pipeline applies, so no caller can run a
    # destructive query against the user's Postgres/MySQL/SQLite store.
    assert_read_only(sql)

    # enforce LIMIT 1000
    lowered = sql.lower()
    if "limit" not in lowered:
        sql = sql.rstrip("; ") + " LIMIT 1000"

    engine = create_async_engine(db_url, future=True)
    start = time.time()
    async with engine.connect() as conn:
        result = await conn.execute(text(sql))
        rows = [dict(r) for r in result.mappings().all()]
    execution_ms = int((time.time() - start) * 1000)
    await engine.dispose()
    return rows, execution_ms
