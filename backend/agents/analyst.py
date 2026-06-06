"""Data Analyst agent: finds the single most important insight in a result set.

Detects statistical outliers deterministically, then asks Claude to identify the
key finding. Falls back to a heuristic summary when no LLM is available.
"""
from __future__ import annotations

import json
import statistics
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from backend.agents.llm import call_json
except ModuleNotFoundError:
    from agents.llm import call_json


class AnalystInput(BaseModel):
    sql_result: List[Dict[str, Any]]
    question: str


class AnalystOutput(BaseModel):
    trend: str
    anomalies: List[str]
    summary: str
    key_metric: str
    key_value: Any = None
    pct_change: Optional[float] = None


def _numeric_fields(rows: List[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []
    return [k for k, v in rows[0].items() if isinstance(v, (int, float)) and not isinstance(v, bool)]


def detect_outliers(rows: List[Dict[str, Any]], field: str) -> List[str]:
    values = [r[field] for r in rows if isinstance(r.get(field), (int, float)) and not isinstance(r.get(field), bool)]
    if len(values) < 3:
        return []
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return []
    return [str(v) for v in values if abs(v - mean) > 2 * stdev]


SYSTEM_PROMPT = """You are a senior data analyst. Given a question and a query result (JSON rows), identify the single most important finding.

Return ONLY a JSON object with exactly these keys:
{
  "trend": "<one of: rising, falling, stable, mixed, no_data>",
  "anomalies": ["<short strings describing outliers, may be empty>"],
  "summary": "<one tight sentence stating the key finding with the actual numbers>",
  "key_metric": "<the most important column/metric name>",
  "key_value": <the headline number or string>,
  "pct_change": <number or null — percent change if a clear time comparison exists>
}
No markdown, no commentary — JSON only."""


def _heuristic(inp: AnalystInput) -> Dict[str, Any]:
    rows = inp.sql_result
    if not rows:
        return AnalystOutput(trend="no_data", anomalies=[], summary="No data returned for this question.", key_metric="", key_value=None).model_dump()
    num_fields = _numeric_fields(rows)
    if not num_fields:
        return AnalystOutput(trend="stable", anomalies=[], summary=f"{len(rows)} rows returned.", key_metric="", key_value=len(rows)).model_dump()
    key = num_fields[0]
    total = sum(r.get(key, 0) for r in rows)
    anomalies = detect_outliers(rows, key)
    pct = None
    series = [r.get(key) for r in rows if isinstance(r.get(key), (int, float))]
    if len(series) >= 2 and series[0]:
        pct = round((series[-1] - series[0]) / abs(series[0]) * 100, 1)
    trend = "stable"
    if pct is not None:
        trend = "rising" if pct > 1 else "falling" if pct < -1 else "stable"
    return AnalystOutput(
        trend=trend,
        anomalies=anomalies,
        summary=f"{key} totals {total:,} across {len(rows)} rows.",
        key_metric=key,
        key_value=total,
        pct_change=pct,
    ).model_dump()


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    inp = AnalystInput(**payload)
    rows = inp.sql_result

    if not rows:
        return _heuristic(inp)

    # Cap rows sent to the model to keep token usage reasonable.
    sample = rows[:100]
    user = (
        f"Question: {inp.question}\n\n"
        f"Result rows ({len(rows)} total, showing up to 100):\n{json.dumps(sample, default=str)}"
    )
    data = call_json(SYSTEM_PROMPT, user, temperature=0.0, max_tokens=600)
    if data is not None:
        try:
            return AnalystOutput(**data).model_dump()
        except Exception:
            pass

    return _heuristic(inp)
