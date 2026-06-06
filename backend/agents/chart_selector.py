"""Chart Selector agent: picks the best visualization for a result set.

Uses Claude with explicit charting rules, falling back to the same rules encoded
deterministically when no LLM is available.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, field_validator

try:
    from backend.agents.llm import call_json
except ModuleNotFoundError:
    from agents.llm import call_json

VALID_CHARTS = {"line", "bar", "pie", "scatter", "heatmap", "table"}


class ChartRequest(BaseModel):
    sql_result: List[Dict[str, Any]]
    analysis: Dict[str, Any] = {}
    question: str = ""


class ChartResponse(BaseModel):
    chart_type: str
    x_axis: Optional[str] = None
    y_axis: Optional[Union[str, List[str]]] = None
    color_by: Optional[str] = None
    title: str
    subtitle: Optional[str] = None

    @field_validator("chart_type")
    @classmethod
    def _valid_chart(cls, v: str) -> str:
        return v if v in VALID_CHARTS else "table"


SYSTEM_PROMPT = """You select the best chart for a dataset. Apply these rules:
- time series data (a date/time column) -> "line"
- comparison across a small number of categories (<=8) -> "bar"
- part of a whole with <=6 slices -> "pie"
- two numeric columns with no category -> "scatter"
- more than 5 columns or pivot-like data -> "heatmap"
- anything else -> "table"

Return ONLY JSON with exactly these keys:
{"chart_type": "...", "x_axis": "col or null", "y_axis": "col or [cols] or null", "color_by": "col or null", "title": "short title", "subtitle": "one line or null"}
No markdown, JSON only."""


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _heuristic(req: ChartRequest) -> Dict[str, Any]:
    rows = req.sql_result
    if not rows:
        return ChartResponse(chart_type="table", title="Empty result").model_dump()

    cols = list(rows[0].keys())
    num_cols = [c for c in cols if _is_number(rows[0].get(c))]
    cat_cols = [c for c in cols if c not in num_cols]
    date_cols = [c for c in cols if any(t in c.lower() for t in ("date", "month", "day", "time", "year", "week"))]
    n = len(rows)
    title = (req.question[:60] or "Result").strip()

    if date_cols and num_cols:
        return ChartResponse(chart_type="line", x_axis=date_cols[0], y_axis=num_cols[0], title=title).model_dump()
    if len(cols) > 5:
        return ChartResponse(chart_type="table", title=title).model_dump()
    if cat_cols and num_cols and n <= 8:
        if n <= 6:
            return ChartResponse(chart_type="pie", x_axis=cat_cols[0], y_axis=num_cols[0], title=title).model_dump()
        return ChartResponse(chart_type="bar", x_axis=cat_cols[0], y_axis=num_cols[0], title=title).model_dump()
    if cat_cols and num_cols:
        return ChartResponse(chart_type="bar", x_axis=cat_cols[0], y_axis=num_cols[0], title=title).model_dump()
    if len(num_cols) >= 2 and not cat_cols:
        return ChartResponse(chart_type="scatter", x_axis=num_cols[0], y_axis=num_cols[1], title=title).model_dump()
    return ChartResponse(chart_type="table", title=title).model_dump()


def select_chart(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = ChartRequest(**payload)
    if not req.sql_result:
        return ChartResponse(chart_type="table", title="Empty result").model_dump()

    cols = list(req.sql_result[0].keys())
    user = (
        f"Question: {req.question}\n"
        f"Columns: {cols}\n"
        f"Row count: {len(req.sql_result)}\n"
        f"Sample rows: {json.dumps(req.sql_result[:5], default=str)}\n"
        f"Analysis: {json.dumps(req.analysis, default=str)}"
    )
    data = call_json(SYSTEM_PROMPT, user, temperature=0.0, max_tokens=300)
    if data is not None:
        try:
            resp = ChartResponse(**data)
            # Guard: if the model picked axes that don't exist, fall back.
            if resp.x_axis and resp.x_axis not in cols and resp.chart_type != "table":
                return _heuristic(req)
            return resp.model_dump()
        except Exception:
            pass

    return _heuristic(req)
