import os
import time
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def run_sql_on_url(db_url: str, sql: str) -> Tuple[List[Dict[str, Any]], int]:
    """Execute read-only SQL against db_url and return rows and execution_ms."""
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed")

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
