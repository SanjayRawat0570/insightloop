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
    await manager.send_event(client_id, event)


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
    """Resolve the data source into (db_url, dialect, schema_text).

    Performs the ownership check and introspects the schema so the Query Writer
    has real tables/columns to work with. Raises RuntimeError on failure.
    """
    fallback_url = os.environ.get("SOURCE_DB_URL") or os.environ.get("DATABASE_URL")
    db_url = fallback_url
    dialect = state.get("dialect") or "postgres"
    schema_text = state.get("schema") or ""

    source_id = state.get("source_id")
    cfg: dict = {}
    has_live_connection = False
    if source_id:
        ds = await get_data_source(source_id)
        if ds:
            current_user_id = _current_user_id(state)
            if not current_user_id or str(ds.user_id) != str(current_user_id):
                raise PermissionError("unauthorized: data source does not belong to current user")
            dialect = ds.type.value if hasattr(ds.type, "value") else str(ds.type)
            cfg = decrypt_connection_config(ds.connection_config or {})
            source_url = cfg.get("connection_url") or build_connection_url(cfg, dialect)
            if source_url:
                db_url = source_url
                has_live_connection = True

    if not db_url:
        raise RuntimeError("No source database available. Configure the data source connection.")

    # When the source has no live DB of its own (e.g. a csv/api source in local
    # dev), we execute against the configured fallback database. Align the
    # dialect with that database so introspection and SQL generation target it.
    if not has_live_connection:
        dialect = _dialect_from_url(db_url)

    # Introspect schema for the Query Writer prompt (best-effort).
    if not schema_text:
        try:
            schema = await parse_schema_from_connection_async({**cfg, "connection_url": db_url, "dialect": dialect})
            schema_text = schema_to_prompt(schema)
        except Exception:
            schema_text = ""

    return db_url, dialect, schema_text


async def run_pipeline(state: InsightState, client_id: str, query_id: str | None = None):
    try:
        state["query_id"] = query_id or state.get("query_id") or None

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
