from pydantic import BaseModel
from typing import Dict, Any, List

class ChartRequest(BaseModel):
    sql_result: List[Dict[str, Any]]
    analysis: Dict[str, Any]
    question: str

class ChartResponse(BaseModel):
    chart_type: str
    x_axis: str | None
    y_axis: str | List[str] | None
    color_by: str | None
    title: str
    subtitle: str | None = None


def select_chart(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = ChartRequest(**payload)
    rows = req.sql_result
    if not rows:
        return ChartResponse(chart_type="table", x_axis=None, y_axis=None, color_by=None, title="Empty result").dict()
    cols = list(rows[0].keys())
    num_cols = sum(1 for c in cols if isinstance(rows[0][c], (int, float)))
    if any('date' in c.lower() for c in cols):
        chart = ChartResponse(chart_type="line", x_axis=cols[0], y_axis=cols[1] if len(cols)>1 else cols[0], color_by=None, title="Time Series")
    elif num_cols >=2:
        chart = ChartResponse(chart_type="scatter", x_axis=cols[0], y_axis=[cols[1]], color_by=None, title="Scatter")
    else:
        chart = ChartResponse(chart_type="table", x_axis=None, y_axis=None, color_by=None, title="Table")
    return chart.dict()
