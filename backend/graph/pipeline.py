from __future__ import annotations

from typing import TypedDict, List, Dict, Any
import asyncio
import os
from datetime import datetime

try:
    from backend.api.ws import manager
    from backend.agents.query_writer import generate_sql, QueryWriterError
    from backend.agents.analyst import analyze
    from backend.agents.chart_selector import select_chart
    from backend.agents.narrative import write_narrative
    from backend.agents.compiler import compile_report
    from backend.db.executor import run_sql_on_url
    from backend.db.models import DataSource, Query, AgentRun, SourceType
    from backend.db.mongo import (
        create_query,
        create_agent_run,
        get_data_source,
        update_query,
    )
    from backend.utils.crypto import decrypt_connection_config, build_connection_url
    from backend.utils.schema_parser import parse_schema_from_connection_async, schema_to_prompt
    from backend.utils.sql_guard import assert_read_only, UnsafeQueryError
    from backend.connectors import materialize_source, SourceLoadError
except ModuleNotFoundError:
    from api.ws import manager
    from agents.query_writer import generate_sql, QueryWriterError
    from agents.analyst import analyze
    from agents.chart_selector import select_chart
    from agents.narrative import write_narrative
    from agents.compiler import compile_report
    from db.executor import run_sql_on_url
    from db.models import DataSource, Query, AgentRun, SourceType
    from db.mongo import (
        create_query,
        create_agent_run,
        get_data_source,
        update_query,
    )
    from utils.crypto import decrypt_connection_config, build_connection_url
    from utils.schema_parser import parse_schema_from_connection_async, schema_to_prompt
    from utils.sql_guard import assert_read_only, UnsafeQueryError
    from connectors import materialize_source, SourceLoadError

try:
    from backend.utils.logging_config import get_logger
except ModuleNotFoundError:
    from utils.logging_config import get_logger

log = get_logger("pipeline")


class InsightState(TypedDict, total=False):
    question: str
    source_id: str
    schema: str
    dialect: str
    sql: str
    sql_result: List[Dict[str, Any]]
    analysis: Dict[str, Any]
    chart_config: Dict[str, Any]
    narrative: Dict[str, Any]
    report: Dict[str, Any]
    error: str
    current_node: str
    user: Dict[str, Any]
    query_id: str


async def _send_node_event(client_id: str, event_type: str, node: str, payload: dict | None = None):
    event = {
        "event": event_type,
        "node": node,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if payload is not None:
        event["payload"] = payload

    # Mirror every WS event to the console so backend logs tell the same story.
    label = node or event_type
    if event_type in ("node_error", "pipeline_error"):
        log.error("[%s] FAILED: %s", label, (payload or {}).get("error"))
    elif event_type == "node_start":
        log.info("[%s] start", node)
    elif event_type == "node_complete":
        log.info("[%s] done %s", node, _summarize(payload))
    elif event_type == "pipeline_complete":
        log.info("pipeline complete")

    await manager.send_event(client_id, event)


def _summarize(payload: dict | None) -> str:
    """Compact one-line summary of a node_complete payload for the log."""
    if not payload:
        return ""
    parts = []
    for k, v in payload.items():
        s = str(v)
        if len(s) > 80:
            s = s[:77] + "…"
        parts.append(f"{k}={s}")
    return " ".join(parts)


def _current_user_id(state: InsightState) -> str | None:
    user = state.get("user") or {}
    return user.get("sub") or user.get("id")


async def _persist_agent_run(query_id: str | None, agent_name: str, input_data: dict | None, output_data: dict | None, duration_ms: int | None = None, tokens_used: int | None = None, error: str | None = None):
    await create_agent_run(
        AgentRun(
            query_id=query_id,
            agent_name=agent_name,
            input_data=input_data,
            output_data=output_data,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            error=error,
        )
    )


def _dialect_from_url(url: str) -> str:
    """Infer a SQL dialect from a SQLAlchemy URL scheme."""
    low = (url or "").lower()
    if low.startswith("sqlite"):
        return "sqlite"
    if low.startswith("mysql"):
        return "mysql"
    if low.startswith("postgres"):
        return "postgres"
    return "postgres"


async def _resolve_source(state: InsightState):
    """Resolve the selected data source into (db_url, dialect, schema_text).

    The connector layer materializes the source's REAL data (API/Sheets/CSV into
    a per-source SQLite store, SQL databases queried in place), enforces the
    ownership check, and introspects the schema so the Query Writer works against
    actual tables/columns. Raises on failure — we never silently substitute the
    bundled sample database for a selected source.
    """
    schema_text = state.get("schema") or ""
    source_id = state.get("source_id")

    # No source selected: fall back to the configured dev database, if any.
    if not source_id:
        fallback_url = os.environ.get("SOURCE_DB_URL") or os.environ.get("DATABASE_URL")
        if not fallback_url:
            raise RuntimeError("No data source selected. Connect a source and pick it before asking.")
        dialect = _dialect_from_url(fallback_url)
        if not schema_text:
            schema = await parse_schema_from_connection_async({"connection_url": fallback_url, "dialect": dialect})
            schema_text = schema_to_prompt(schema)
        return fallback_url, dialect, schema_text

    ds = await get_data_source(source_id)
    if not ds:
        raise RuntimeError("Selected data source was not found.")

    current_user_id = _current_user_id(state)
    if not current_user_id or str(ds.user_id) != str(current_user_id):
        raise PermissionError("unauthorized: data source does not belong to current user")

    source_type = ds.type.value if hasattr(ds.type, "value") else str(ds.type)
    cfg = decrypt_connection_config(ds.connection_config or {})

    # Materialize the source's real data (network/disk I/O — run off the loop).
    try:
        mat = await asyncio.to_thread(materialize_source, source_type, cfg, source_id)
    except SourceLoadError as e:
        raise RuntimeError(f"Could not load data from '{ds.name}': {e}")

    db_url, dialect = mat.db_url, mat.dialect
    log.info("source resolved name=%r type=%s dialect=%s live=%s", ds.name, source_type, dialect, mat.live)

    if not schema_text:
        try:
            schema = await parse_schema_from_connection_async(
                {**cfg, "connection_url": db_url, "dialect": dialect}
            )
            schema_text = schema_to_prompt(schema)
        except Exception as e:
            raise RuntimeError(f"Could not read schema for '{ds.name}': {e}")

    return db_url, dialect, schema_text


async def run_pipeline(state: InsightState, client_id: str, query_id: str | None = None):
    try:
        state["query_id"] = query_id or state.get("query_id") or None
        log.info(
            "query start id=%s source=%s q=%r",
            state["query_id"], state.get("source_id"), (state.get("question") or "")[:80],
        )

        # 0. Resolve data source + introspect schema (ownership enforced here).
        try:
            db_url, dialect, schema_text = await _resolve_source(state)
            state["_db_url"] = db_url
            state["dialect"] = dialect
            state["schema"] = schema_text
        except Exception as e:
            state["error"] = str(e)
            await _send_node_event(client_id, "node_error", "query_writer", {"error": str(e)})
            await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
            return

        # 1. Query writer
        state["current_node"] = "query_writer"
        await _send_node_event(client_id, "node_start", "query_writer")
        try:
            start = datetime.utcnow()
            sql_resp = await asyncio.to_thread(generate_sql, {"question": state.get("question", ""), "schema": state.get("schema", ""), "dialect": state.get("dialect", "postgres")})
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            state["sql"] = sql_resp.get("sql")
            await _send_node_event(client_id, "node_complete", "query_writer", {"sql": state["sql"]})
        except QueryWriterError as e:
            state["error"] = str(e)
            await _send_node_event(client_id, "node_error", "query_writer", {"error": str(e)})
            await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
            return

        # 1b. Read-only guardrail. Regardless of source type (Postgres, MySQL, or
        # the materialized SQLite that backs MongoDB/API/Sheets/CSV), the
        # generated SQL ultimately runs against a real database — so before it
        # gets anywhere near execution we hard-block any mutating/DDL statement
        # (UPDATE/DELETE/DROP/...) that the LLM may have produced.
        try:
            assert_read_only(state.get("sql") or "")
        except UnsafeQueryError as e:
            msg = f"Query blocked by safety guardrail: {e}"
            log.error("[query_guard] BLOCKED sql=%r reason=%s", state.get("sql"), str(e))
            state["error"] = msg
            await _send_node_event(client_id, "node_error", "query_writer", {"error": msg})
            await _send_node_event(client_id, "pipeline_error", "", {"error": msg})
            return

        try:
            current_user_id = _current_user_id(state)
            query_doc = Query(
                id=state["query_id"] or None,
                user_id=current_user_id or "",
                source_id=state.get("source_id") or "",
                natural_language=state.get("question", ""),
                generated_sql=state.get("sql", ""),
            )
            await create_query(query_doc)
            state["query_id"] = query_doc.id
            await _persist_agent_run(
                query_doc.id,
                "query_writer",
                {"question": state.get("question"), "schema": state.get("schema")},
                {"sql": state.get("sql")},
                duration_ms=duration_ms,
                tokens_used=sql_resp.get("tokens_used") if isinstance(sql_resp, dict) else None,
            )
        except Exception:
            await _send_node_event(client_id, "node_warning", "query_writer", {"note": "persistence failed"})

        # 2. SQL executor
        state["current_node"] = "sql_executor"
        await _send_node_event(client_id, "node_start", "sql_executor")
        try:
            db_url = state.get("_db_url") or os.environ.get("SOURCE_DB_URL") or os.environ.get("DATABASE_URL")
            if not db_url:
                raise RuntimeError("No source database URL available. Set SOURCE_DB_URL or configure the datasource connection.")

            sql_to_run = state.get("sql") or "SELECT 1 as placeholder"
            log.info("executing SQL: %s", " ".join(sql_to_run.split()))
            rows, exec_ms = await run_sql_on_url(db_url, sql_to_run)
            state["sql_result"] = rows
            state["execution_ms"] = exec_ms
            await _send_node_event(client_id, "node_complete", "sql_executor", {"rows": len(rows), "execution_ms": exec_ms})

            try:
                await update_query(state["query_id"], {"result_cache": rows, "execution_ms": exec_ms})
                await _persist_agent_run(
                    state["query_id"],
                    "sql_executor",
                    {"sql": state.get("sql")},
                    {"rows": len(rows)},
                    duration_ms=exec_ms,
                )
            except Exception:
                await _send_node_event(client_id, "node_warning", "sql_executor", {"note": "persistence failed"})
        except Exception as e:
            state["error"] = str(e)
            await _send_node_event(client_id, "node_error", "sql_executor", {"error": str(e)})
            await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
            return

        # 3. Data analyst
        state["current_node"] = "data_analyst"
        await _send_node_event(client_id, "node_start", "data_analyst")
        try:
            start = datetime.utcnow()
            analysis = await asyncio.to_thread(analyze, {"sql_result": state.get("sql_result", []), "question": state.get("question", "")})
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            state["analysis"] = analysis
            await _send_node_event(client_id, "node_complete", "data_analyst", {"summary": analysis.get("summary")})
            try:
                await _persist_agent_run(
                    state.get("query_id"),
                    "data_analyst",
                    {"sql_result": state.get("sql_result"), "question": state.get("question")},
                    analysis,
                    duration_ms=duration_ms,
                    tokens_used=analysis.get("tokens_used") if isinstance(analysis, dict) else None,
                )
            except Exception:
                await _send_node_event(client_id, "node_warning", "data_analyst", {"note": "persistence failed"})
        except Exception as e:
            state["error"] = str(e)
            await _send_node_event(client_id, "node_error", "data_analyst", {"error": str(e)})
            await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
            return

        # 4. Chart selector
        state["current_node"] = "chart_selector"
        await _send_node_event(client_id, "node_start", "chart_selector")
        try:
            start = datetime.utcnow()
            chart = await asyncio.to_thread(select_chart, {"sql_result": state.get("sql_result", []), "analysis": state.get("analysis", {}), "question": state.get("question", "")})
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            state["chart_config"] = chart
            await _send_node_event(client_id, "node_complete", "chart_selector", {"chart_type": chart.get("chart_type")})
            try:
                await _persist_agent_run(
                    state.get("query_id"),
                    "chart_selector",
                    {"analysis": state.get("analysis"), "sql_result": state.get("sql_result")},
                    chart,
                    duration_ms=duration_ms,
                    tokens_used=chart.get("tokens_used") if isinstance(chart, dict) else None,
                )
            except Exception:
                await _send_node_event(client_id, "node_warning", "chart_selector", {"note": "persistence failed"})
        except Exception as e:
            state["error"] = str(e)
            await _send_node_event(client_id, "node_error", "chart_selector", {"error": str(e)})
            await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
            return

        # 5. Narrative
        state["current_node"] = "narrative"
        await _send_node_event(client_id, "node_start", "narrative")
        try:
            start = datetime.utcnow()
            narrative = await asyncio.to_thread(write_narrative, {"analysis": state.get("analysis", {}), "chart_config": state.get("chart_config", {}), "question": state.get("question", "")})
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            state["narrative"] = narrative
            await _send_node_event(client_id, "node_complete", "narrative", {"headline": narrative.get("headline")})
            try:
                await _persist_agent_run(
                    state.get("query_id"),
                    "narrative",
                    {"analysis": state.get("analysis"), "chart_config": state.get("chart_config")},
                    narrative,
                    duration_ms=duration_ms,
                    tokens_used=narrative.get("tokens_used") if isinstance(narrative, dict) else None,
                )
            except Exception:
                await _send_node_event(client_id, "node_warning", "narrative", {"note": "persistence failed"})
        except Exception as e:
            state["error"] = str(e)
            await _send_node_event(client_id, "node_error", "narrative", {"error": str(e)})
            await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
            return

        # 6. Compiler
        state["current_node"] = "compiler"
        await _send_node_event(client_id, "node_start", "compiler")
        try:
            start = datetime.utcnow()
            report = await asyncio.to_thread(compile_report, state)
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            state["report"] = report
            await _send_node_event(client_id, "node_complete", "compiler", {"report_title": report.get("title")})
            try:
                await _persist_agent_run(
                    state.get("query_id"),
                    "compiler",
                    {"state": {k: state.get(k) for k in ["sql", "analysis", "chart_config", "narrative"]}},
                    report,
                    duration_ms=duration_ms,
                    tokens_used=report.get("tokens_used") if isinstance(report, dict) else None,
                )
            except Exception:
                await _send_node_event(client_id, "node_warning", "compiler", {"note": "persistence failed"})
        except Exception as e:
            state["error"] = str(e)
            await _send_node_event(client_id, "node_error", "compiler", {"error": str(e)})
            await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
            return

        # Build a frontend-renderable result object (QueryResult shape).
        result = {
            "id": state.get("query_id"),
            "natural_language": state.get("question"),
            "generated_sql": state.get("sql"),
            "result_cache": state.get("sql_result") or [],
            "execution_ms": state.get("execution_ms"),
            "analysis": state.get("analysis"),
            "chart_config": state.get("chart_config"),
            "narrative": state.get("narrative"),
            "report": state.get("report"),
        }

        # Persist the analysis/chart/narrative onto the stored query for history reloads.
        try:
            await update_query(
                state["query_id"],
                {
                    "analysis": state.get("analysis"),
                    "chart_config": state.get("chart_config"),
                    "narrative": state.get("narrative"),
                },
            )
        except Exception:
            pass

        await _send_node_event(client_id, "pipeline_complete", "", {"result": result, "report": state.get("report")})

    except Exception as e:
        await _send_node_event(client_id, "pipeline_error", "", {"error": str(e)})
