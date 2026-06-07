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
    from backend.agents.llm import call_json, fast_pipeline
except ModuleNotFoundError:
    from agents.llm import call_json, fast_pipeline


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
    top_label: Optional[str] = None
    top_share: Optional[float] = None


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


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:,}"
    return str(v)


def _heuristic(inp: AnalystInput) -> Dict[str, Any]:
    rows = inp.sql_result
    if not rows:
        return AnalystOutput(trend="no_data", anomalies=[], summary="No data returned for this question.", key_metric="", key_value=None).model_dump()

    cols = list(rows[0].keys())
    num_fields = _numeric_fields(rows)
    cat_fields = [c for c in cols if c not in num_fields]
    n = len(rows)

    if not num_fields:
        return AnalystOutput(
            trend="stable", anomalies=[],
            summary=f"{n} {'row' if n == 1 else 'rows'} returned with no numeric column to analyze.",
            key_metric=cols[0] if cols else "", key_value=n,
        ).model_dump()

    key = num_fields[0]
    metric = key.replace("_", " ")
    total = sum((r.get(key) or 0) for r in rows)
    anomalies = detect_outliers(rows, key)

    # Top contributor (when there's a category/label column).
    top_label = top_value = top_share = None
    label_col = cat_fields[0] if cat_fields else None
    if label_col:
        top_row = max(rows, key=lambda r: r.get(key) or 0)
        top_label = str(top_row.get(label_col))
        top_value = top_row.get(key)
        if total:
            top_share = round((top_value / total) * 100, 1)

    # Percent change across the ordered series (time-ish data).
    series = [r.get(key) for r in rows if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)]
    pct = None
    if len(series) >= 2 and series[0]:
        pct = round((series[-1] - series[0]) / abs(series[0]) * 100, 1)
    trend = "stable"
    if pct is not None:
        trend = "rising" if pct > 1 else "falling" if pct < -1 else "stable"

    # Natural-language summary.
    if n == 1:
        summary = f"{metric.capitalize()} is {_fmt(total)}."
    elif top_label is not None and top_share is not None:
        summary = (
            f"{metric.capitalize()} sums to {_fmt(total)} across {n} {label_col.replace('_', ' ')}s; "
            f"{top_label} leads at {_fmt(top_value)} ({top_share:.0f}%)."
        )
    else:
        summary = f"{metric.capitalize()} sums to {_fmt(total)} across {n} rows."

    return AnalystOutput(
        trend=trend,
        anomalies=anomalies,
        summary=summary,
        key_metric=key,
        key_value=total,
        pct_change=pct,
        top_label=top_label,
        top_share=top_share,
    ).model_dump()


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    inp = AnalystInput(**payload)
    rows = inp.sql_result

    if not rows:
        return _heuristic(inp)

    # Fast mode: the heuristic computes real statistics (totals, % change,
    # std-dev outliers) deterministically — accurate and instant.
    if fast_pipeline():
        return _heuristic(inp)

    # Cap rows sent to the model to keep token usage reasonable.
    sample = rows[:100]
    user = (
        f"Question: {inp.question}\n\n"
        f"Result rows ({len(rows)} total, showing up to 100):\n{json.dumps(sample, default=str)}"
    )
    data = call_json(SYSTEM_PROMPT, user, temperature=0.0, max_tokens=350)
    if data is not None:
        try:
            return AnalystOutput(**data).model_dump()
        except Exception:
            pass

    return _heuristic(inp)
