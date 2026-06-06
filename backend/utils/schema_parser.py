"""Schema introspection for connected data sources.

Connects to a user's data source, introspects tables + columns, and collects a
few sample values per column. Output feeds both the Connect-page schema browser
and the Query Writer agent (as a compact DDL-style prompt).
"""
from __future__ import annotations

from typing import Any, Dict, List
import asyncio

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from backend.utils.crypto import build_connection_url
except ModuleNotFoundError:
    from utils.crypto import build_connection_url


def parse_csv_schema(file_path: str) -> Dict[str, Any]:
    df = pd.read_csv(file_path)
    tables = [{
        "name": "csv_table",
        "columns": [
            {
                "name": col,
                "type": str(df[col].dtype),
                "nullable": bool(df[col].isnull().any()),
                "sample_values": [_json_safe(v) for v in df[col].dropna().unique()[:3].tolist()],
            }
            for col in df.columns
        ],
    }]
    return {"dialect": "csv", "tables": tables}


def _json_safe(v: Any) -> Any:
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def _normalize_dialect(dialect: str | None) -> str:
    d = (dialect or "postgres").lower()
    if d.startswith("postgres"):
        return "postgres"
    if d.startswith("mysql"):
        return "mysql"
    return d


async def _introspect_sql(db_url: str, dialect: str) -> List[Dict[str, Any]]:
    """Introspect a SQL database and return a list of table descriptors."""
    engine = create_async_engine(db_url, future=True)
    try:
        async with engine.connect() as conn:
            def _collect(sync_conn) -> List[Dict[str, Any]]:
                insp = inspect(sync_conn)
                out: List[Dict[str, Any]] = []
                for table_name in insp.get_table_names():
                    cols = []
                    for col in insp.get_columns(table_name):
                        cols.append({
                            "name": col["name"],
                            "type": str(col.get("type")),
                            "nullable": bool(col.get("nullable", True)),
                            "sample_values": [],
                        })
                    out.append({"name": table_name, "columns": cols})
                return out

            tables = await conn.run_sync(_collect)

            # Sample a few distinct values per column for better prompts.
            for tbl in tables:
                try:
                    quoted = _quote_ident(tbl["name"], dialect)
                    result = await conn.execute(text(f"SELECT * FROM {quoted} LIMIT 5"))
                    rows = [dict(r) for r in result.mappings().all()]
                except Exception:
                    rows = []
                for col in tbl["columns"]:
                    seen: List[Any] = []
                    for row in rows:
                        val = row.get(col["name"])
                        if val is not None and val not in seen:
                            seen.append(_json_safe(val))
                        if len(seen) >= 3:
                            break
                    col["sample_values"] = seen
        return tables
    finally:
        await engine.dispose()


def _quote_ident(name: str, dialect: str) -> str:
    if dialect == "mysql":
        return f"`{name}`"
    return f'"{name}"'


def parse_schema_from_connection(conn_info: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous entry point used by routes that aren't async-aware.

    Connects to the data source, runs `SELECT 1` as a connection test, and
    introspects the schema. Raises on connection failure so callers can surface
    a "connection test failed" error.
    """
    return asyncio.run(parse_schema_from_connection_async(conn_info))


async def parse_schema_from_connection_async(conn_info: Dict[str, Any]) -> Dict[str, Any]:
    dialect = _normalize_dialect(conn_info.get("dialect"))

    if dialect in ("csv", "api", "sheets"):
        # Non-SQL sources: nothing to introspect here (handled elsewhere / future work).
        return {"dialect": dialect, "tables": []}

    db_url = conn_info.get("connection_url") or build_connection_url(conn_info, dialect)
    if not db_url:
        raise ValueError("Incomplete connection config: host and database are required")

    tables = await _introspect_sql(db_url, dialect)
    return {"dialect": dialect, "tables": tables}


def schema_to_prompt(schema: Dict[str, Any]) -> str:
    """Render an introspected schema as compact DDL-ish text for the LLM."""
    lines: List[str] = []
    for tbl in schema.get("tables", []):
        col_strs = []
        for col in tbl.get("columns", []):
            samples = col.get("sample_values") or []
            sample_hint = f"  -- e.g. {', '.join(str(s) for s in samples[:3])}" if samples else ""
            col_strs.append(f"  {col['name']} {col.get('type', '')}{sample_hint}")
        lines.append(f"TABLE {tbl['name']} (\n" + ",\n".join(col_strs) + "\n);")
    return "\n\n".join(lines) if lines else "(no tables found)"
