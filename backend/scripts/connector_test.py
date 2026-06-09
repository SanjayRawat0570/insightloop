"""Multi-source connector validation (offline, no running server).

For every source type we can exercise without external credentials (REST API,
inline CSV, and MongoDB when MONGODB_URL is set) this:

  1. materializes the source's REAL data into the queryable store,
  2. introspects the resulting schema,
  3. asks the Query Writer for SQL and executes it,
  4. runs the analyst / chart / narrative agents over the rows.

Run with the backend venv:
    PYTHONPATH=<backend> python scripts/connector_test.py
"""
import asyncio
import os

from dotenv import load_dotenv

from connectors import materialize_source, SourceLoadError
from utils.schema_parser import parse_schema_from_connection_async, schema_to_prompt
from db.executor import run_sql_on_url
from agents.query_writer import generate_sql
from agents.analyst import analyze
from agents.chart_selector import select_chart
from agents.narrative import write_narrative

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SAMPLE_CSV = """region,month,revenue,units
North,2025-01,12000,120
North,2025-02,15000,150
South,2025-01,8000,80
South,2025-02,9500,95
"""


async def exercise(label: str, source_type: str, cfg: dict, question: str, source_id: str):
    print(f"\n===== {label} ({source_type}) =====")
    try:
        mat = await asyncio.to_thread(materialize_source, source_type, cfg, source_id)
    except SourceLoadError as e:
        print(f"  SKIP/FAIL materialize: {e}")
        return False
    print("  tables :", mat.table_names, "| dialect:", mat.dialect, "| live:", mat.live)

    schema = await parse_schema_from_connection_async(
        {**cfg, "connection_url": mat.db_url, "dialect": mat.dialect}
    )
    schema_text = schema_to_prompt(schema)
    if not schema.get("tables"):
        print("  FAIL: no tables introspected")
        return False

    sql = generate_sql({"question": question, "schema": schema_text, "dialect": mat.dialect}).get("sql")
    print("  SQL    :", sql)
    rows, ms = await run_sql_on_url(mat.db_url, sql)
    print(f"  rows   : {len(rows)} in {ms}ms")
    if not rows:
        print("  WARN: query returned no rows")

    analysis = analyze({"sql_result": rows, "question": question})
    chart = select_chart({"sql_result": rows, "analysis": analysis, "question": question})
    narrative = write_narrative({"analysis": analysis, "chart_config": chart, "question": question})
    print("  chart  :", chart.get("chart_type"))
    print("  insight:", narrative.get("headline"))
    return True


async def main():
    results = {}

    results["REST API"] = await exercise(
        "REST API", "api",
        {"url": "https://jsonplaceholder.typicode.com/users"},
        "How many users are there per company?", "test_api",
    )

    results["CSV"] = await exercise(
        "CSV", "csv",
        {"content": SAMPLE_CSV},
        "What is total revenue by region?", "test_csv",
    )

    mongo_uri = os.environ.get("MONGODB_URL")
    if mongo_uri:
        results["MongoDB"] = await exercise(
            "MongoDB", "mongodb",
            {"uri": mongo_uri, "database": os.environ.get("MONGODB_DB", "insightloop")},
            "How many queries are there per source_id?", "test_mongo",
        )
    else:
        print("\n(skipping MongoDB — MONGODB_URL not set)")

    print("\n===== SUMMARY =====")
    for k, v in results.items():
        print(f"  {k:10s}: {'PASS' if v else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
