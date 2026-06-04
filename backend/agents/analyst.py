from pydantic import BaseModel, Field
from typing import List, Dict, Any
import statistics

class AnalystInput(BaseModel):
    sql_result: List[Dict[str, Any]]
    question: str

class AnalystOutput(BaseModel):
    trend: str
    anomalies: List[str]
    summary: str
    key_metric: str
    key_value: Any
    pct_change: float | None = None


def detect_outliers(rows, field):
    values = [r[field] for r in rows if isinstance(r.get(field), (int, float))]
    if len(values) < 2:
        return []
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    return [str(v) for v in values if abs(v - mean) > 2 * stdev]


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    inp = AnalystInput(**payload)
    rows = inp.sql_result
    if not rows:
        return AnalystOutput(trend="no_data", anomalies=[], summary="No data returned.", key_metric="", key_value=None).dict()

    # pick first numeric column as key metric
    sample = rows[0]
    num_fields = [k for k,v in sample.items() if isinstance(v, (int, float))]
    if not num_fields:
        return AnalystOutput(trend="no_numeric", anomalies=[], summary="No numeric columns found.", key_metric="", key_value=None).dict()
    key = num_fields[0]
    key_value = sum([r.get(key,0) for r in rows])
    anomalies = detect_outliers(rows, key)
    summary = f"Top finding: {key} total = {key_value}"
    return AnalystOutput(trend="stable", anomalies=anomalies, summary=summary, key_metric=key, key_value=key_value).dict()
