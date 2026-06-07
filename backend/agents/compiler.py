"""Compiler agent: assembles the final report JSON.

Writes a 2-sentence executive summary across all sections (via Claude when
available) and structures the report. PDF generation is handled separately.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from backend.agents.llm import call_text, fast_pipeline
except ModuleNotFoundError:
    from agents.llm import call_text, fast_pipeline


class InsightState(BaseModel):
    question: str
    source_id: Optional[str] = None
    schema: Optional[str] = None
    dialect: Optional[str] = None
    sql: Optional[str] = None
    sql_result: Optional[List[Dict[str, Any]]] = None
    analysis: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
    narrative: Optional[Dict[str, Any]] = None


class ReportSection(BaseModel):
    title: str
    chart_config: Dict[str, Any]
    narrative: Dict[str, Any]
    data_table: List[Dict[str, Any]]
    sql_used: str


class Report(BaseModel):
    title: str
    generated_at: str
    executive_summary: str
    sections: List[ReportSection]


SYSTEM_PROMPT = """You write executive summaries for BI reports. Given the question and the key findings, write exactly two sentences summarizing the takeaways for a busy executive. Direct, no jargon. Return ONLY the two sentences, no preamble."""


def _exec_summary(state: InsightState) -> str:
    narrative = state.narrative or {}
    analysis = state.analysis or {}

    # Deterministic stitch of the already-generated narrative/analysis.
    def _stitched() -> str:
        head = (narrative.get("headline") or "Report generated").rstrip(".")
        summary = (analysis.get("summary") or "").strip()
        rec = (narrative.get("recommendation") or "").strip()
        parts = [f"{head}."]
        if summary:
            parts.append(summary if summary.endswith(".") else summary + ".")
        elif rec:
            parts.append(rec if rec.endswith(".") else rec + ".")
        return " ".join(parts).strip()

    # In fast mode, skip the LLM — the summary is derivable from prior agents.
    if fast_pipeline():
        return _stitched()

    user = (
        f"Question: {state.question}\n"
        f"Headline: {narrative.get('headline', '')}\n"
        f"Summary: {analysis.get('summary', '')}\n"
        f"Recommendation: {narrative.get('recommendation', '')}"
    )
    text = call_text(SYSTEM_PROMPT, user, temperature=0.3, max_tokens=200)
    if text:
        return text.strip()
    return _stitched()


def compile_report(state: Dict[str, Any]) -> Dict[str, Any]:
    s = InsightState(**{k: state.get(k) for k in InsightState.model_fields})
    sections: List[ReportSection] = []
    if s.chart_config and s.narrative:
        sections.append(
            ReportSection(
                title=s.question or "Section",
                chart_config=s.chart_config,
                narrative=s.narrative,
                data_table=(s.sql_result or [])[:50],
                sql_used=s.sql or "",
            )
        )

    report = Report(
        title=s.question or "InsightLoop Report",
        generated_at=datetime.utcnow().isoformat() + "Z",
        executive_summary=_exec_summary(s),
        sections=sections,
    )
    return report.model_dump()
