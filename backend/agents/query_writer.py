"""Query Writer agent: natural language -> SQL using Claude.

Falls back to a schema-aware heuristic when no LLM is available so the pipeline
still runs end-to-end.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from backend.agents.llm import call_text, backend_label
except ModuleNotFoundError:
    from agents.llm import call_text, backend_label


class QueryWriterError(Exception):
    pass


class QueryRequest(BaseModel):
    question: str
    schema: str = ""
    dialect: str = "postgres"


class QueryResponse(BaseModel):
    sql: str
    explanation: Optional[str] = None


SYSTEM_PROMPT = """You are an expert SQL engineer. Convert the user's question into a single, correct, read-only SQL SELECT query.

Rules:
- Target dialect: {dialect}. Use ONLY syntax valid for that dialect.
- CRITICAL: Only reference tables and columns that appear in the schema below. Never invent table or column names. Do not use tables like "orders" or "customers" unless they are in the schema.
- ALWAYS use short table aliases (e.g. FROM sales s).
- NEVER use SELECT * — always list explicit columns.
- Add LIMIT 1000 to prevent runaway queries (unless an aggregate returns a single row).
- Use aggregations (SUM/COUNT/AVG), GROUP BY, JOINs and ORDER BY where appropriate.
- For SQLite, do NOT use date_trunc — group by the raw date/month column instead.
- Return ONLY the SQL query. No markdown fences, no commentary, no explanation.

Schema:
{schema}
"""

NUMERIC_TYPES = (
    "int", "integer", "bigint", "smallint", "real", "float", "double",
    "numeric", "decimal", "money",
)


def _is_numeric(col_type: str) -> bool:
    t = (col_type or "").lower()
    return any(n in t for n in NUMERIC_TYPES)


def _build_few_shot(tables: List[Dict[str, Any]]) -> str:
    """Construct a few-shot example grounded in the REAL schema.

    Small local models tend to copy example queries verbatim, so the example
    must reference tables/columns that actually exist — otherwise the model
    parrots a phantom `orders` table. We synthesize one realistic aggregate
    query from the first table that has a numeric column to group on.
    """
    for t in tables:
        cols = t.get("columns") or []
        numeric = next((c["name"] for c in cols if _is_numeric(c.get("type", ""))), None)
        group = next(
            (c["name"] for c in cols if not _is_numeric(c.get("type", "")) and c["name"].lower() != "id"),
            None,
        )
        if numeric and group:
            name = t["name"]
            return (
                "Example (uses the real schema above):\n"
                f"Q: total {numeric} by {group}\n"
                f"A: SELECT t.{group}, SUM(t.{numeric}) AS total_{numeric} "
                f"FROM {name} t GROUP BY t.{group} ORDER BY t.{group} LIMIT 1000\n"
            )
    return "Only use the tables and columns listed in the schema above.\n"


def _strip_fences(sql: str) -> str:
    sql = sql.strip()
    m = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", sql, re.DOTALL)
    if m:
        sql = m.group(1).strip()
    return sql.rstrip(";").strip()


def validate_sql(sql: str) -> bool:
    low = sql.strip().lower()
    if not low.startswith("select") and not low.startswith("with"):
        return False
    if re.search(r"select\s+\*", low):
        return False
    forbidden = (" insert ", " update ", " delete ", " drop ", " alter ", " truncate ", " create ")
    padded = f" {low} "
    if any(tok in padded for tok in forbidden):
        return False
    return True


def _ensure_limit(sql: str) -> str:
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql
    return sql + " LIMIT 1000"


def _parse_schema_tables(schema: str) -> List[Dict[str, Any]]:
    """Parse the DDL-ish schema text produced by schema_parser.schema_to_prompt.

    Each table is {"name": str, "columns": [{"name": str, "type": str}]}.
    """
    tables: List[Dict[str, Any]] = []
    for block in re.finditer(r"TABLE\s+(\w+)\s*\((.*?)\);", schema, re.DOTALL):
        name = block.group(1)
        cols = []
        for line in block.group(2).splitlines():
            # Drop trailing comments (e.g. "-- e.g. ...") and commas.
            line = line.split("--")[0].strip().rstrip(",").strip()
            if not line:
                continue
            parts = line.split()
            if parts:
                cols.append({"name": parts[0], "type": parts[1] if len(parts) > 1 else ""})
        tables.append({"name": name, "columns": cols})
    return tables


def _referenced_tables(sql: str) -> set[str]:
    """Table names referenced after FROM/JOIN, lowercased."""
    return {
        m.group(1).lower()
        for m in re.finditer(r"\b(?:from|join)\s+([A-Za-z_][\w]*)", sql, re.IGNORECASE)
    }


def _tables_exist(sql: str, tables: List[Dict[str, Any]]) -> bool:
    """True if every table referenced in the SQL exists in the schema.

    When the schema is unknown we cannot validate, so we accept (True).
    """
    known = {t["name"].lower() for t in tables}
    if not known:
        return True
    return _referenced_tables(sql).issubset(known)


def _heuristic_sql(question: str, schema: str, dialect: str) -> str:
    """Schema-aware fallback: select real columns from the most relevant table."""
    tables = _parse_schema_tables(schema)
    if not tables:
        # Last resort: try to find a table name mentioned in the question.
        m = re.search(r"\bfrom\s+(\w+)", question, re.IGNORECASE)
        table = m.group(1) if m else None
        if not table:
            raise QueryWriterError(
                "No schema available to generate SQL. Connect a source with tables and try again."
            )
        return f"SELECT 1 AS placeholder FROM {table} LIMIT 1000"

    # Pick the table whose name best matches words in the question, else the first.
    q_words = set(re.findall(r"\w+", question.lower()))
    best = max(
        tables,
        key=lambda t: len(q_words & {t["name"].lower(), t["name"].lower().rstrip("s")}),
    )
    cols = best["columns"] or []
    col_names = [c["name"] for c in cols]

    # If the question implies an aggregation and the table has a numeric column
    # plus a categorical/date column to group by, produce a real GROUP BY query.
    agg_intent = bool(
        q_words & {"total", "sum", "count", "average", "avg", "by", "per", "revenue", "trend", "top"}
    )
    numeric = next((c["name"] for c in cols if _is_numeric(c.get("type", ""))), None)
    group = next(
        (c["name"] for c in cols if not _is_numeric(c.get("type", "")) and c["name"].lower() != "id"),
        None,
    )
    # Prefer a group-by column whose name is mentioned in the question.
    mentioned_group = next(
        (c["name"] for c in cols
         if c["name"].lower() in q_words and not _is_numeric(c.get("type", ""))),
        None,
    )
    group = mentioned_group or group
    if agg_intent and numeric and group:
        return (
            f"SELECT t.{group}, SUM(t.{numeric}) AS total_{numeric} "
            f"FROM {best['name']} t GROUP BY t.{group} ORDER BY t.{group} LIMIT 1000"
        )

    if not col_names:
        col_list = "1 AS placeholder"
    else:
        col_list = ", ".join(f"t.{c}" for c in col_names[:6])
    return f"SELECT {col_list} FROM {best['name']} t LIMIT 1000"


def generate_sql(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = QueryRequest(**{**payload, "schema": payload.get("schema") or ""})

    tables = _parse_schema_tables(req.schema)
    system = SYSTEM_PROMPT.format(dialect=req.dialect, schema=req.schema or "(schema unavailable)")
    few_shot = _build_few_shot(tables)
    user = f"{few_shot}\nNow answer this question using only the schema above.\nQ: {req.question}\nA:"

    raw = call_text(system, user, temperature=0.0, max_tokens=350)

    if raw:
        sql = _ensure_limit(_strip_fences(raw))
        # Accept only syntactically valid SQL that references real tables. A weak
        # model may hallucinate tables (e.g. "orders"); reject and fall back.
        if validate_sql(sql) and _tables_exist(sql, tables):
            return QueryResponse(sql=sql, explanation=f"Generated by {backend_label()}").model_dump()

    # Fallback heuristic (no key, model failure, invalid SQL, or hallucinated tables).
    sql = _ensure_limit(_heuristic_sql(req.question, req.schema, req.dialect))
    if not validate_sql(sql):
        raise QueryWriterError("Could not generate a valid SQL query for that question.")
    return QueryResponse(sql=sql, explanation="Generated by schema-aware fallback").model_dump()
