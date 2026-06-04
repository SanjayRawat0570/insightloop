from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime

class InsightState(BaseModel):
    question: str
    source_id: str
    schema: str | None = None
    dialect: str | None = None
    sql: str | None = None
    sql_result: List[Dict[str, Any]] | None = None
    analysis: Dict[str, Any] | None = None
    chart_config: Dict[str, Any] | None = None
    narrative: Dict[str, Any] | None = None

class ReportSection(BaseModel):
    title: str
    chart_config: Dict[str, Any]
    narrative: Dict[str, Any]
    data_table: List[Dict[str, Any]]
    sql_used: str

class Report(BaseModel):
    title: str
    generated_at: datetime
    executive_summary: str
    sections: List[ReportSection]


def compile_report(state: Dict[str, Any]) -> Dict[str, Any]:
    s = InsightState(**state)
    sections = []
    if s.chart_config and s.narrative:
        sections.append(ReportSection(title=s.question or "Section", chart_config=s.chart_config, narrative=s.narrative, data_table=s.sql_result or [], sql_used=s.sql or "").dict())
    report = Report(title=s.question or "Report", generated_at=datetime.utcnow(), executive_summary=(s.narrative or {}).get('headline',''), sections=sections)
    return report.dict()
