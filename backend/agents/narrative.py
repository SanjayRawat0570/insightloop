"""Narrative agent: executive-level commentary on a finding.

Headline <= 12 words, at most two supporting sentences, one recommended action.
Falls back to a heuristic when no LLM is available.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from pydantic import BaseModel

try:
    from backend.agents.llm import call_json
except ModuleNotFoundError:
    from agents.llm import call_json


class NarrativeRequest(BaseModel):
    analysis: Dict[str, Any] = {}
    chart_config: Dict[str, Any] = {}
    question: str = ""


class NarrativeResponse(BaseModel):
    headline: str
    supporting: List[str]
    recommendation: str
    tone: str = "direct"


SYSTEM_PROMPT = """You are an executive communications expert writing BI commentary.
Tone: direct, no jargon, action-oriented.

Return ONLY JSON with exactly these keys:
{
  "headline": "<<= 12 words, states the key takeaway>",
  "supporting": ["<sentence 1>", "<sentence 2>"],
  "recommendation": "<one clear recommended action>",
  "tone": "direct"
}
Rules: headline at most 12 words; at most two supporting sentences; exactly one recommendation. JSON only."""


def _trim_headline(text: str) -> str:
    words = text.split()
    return " ".join(words[:12]) if len(words) > 12 else text


def _heuristic(req: NarrativeRequest) -> Dict[str, Any]:
    analysis = req.analysis or {}
    summary = (analysis.get("summary") or "Key finding from your data").strip()
    headline = _trim_headline(summary)
    trend = analysis.get("trend", "stable")
    pct = analysis.get("pct_change")
    supporting = []
    if pct is not None:
        supporting.append(f"The metric changed {pct}% over the observed range ({trend}).")
    if analysis.get("anomalies"):
        supporting.append(f"{len(analysis['anomalies'])} outlier(s) detected worth reviewing.")
    if not supporting:
        supporting = ["This reflects the current state of your data."]
    return NarrativeResponse(
        headline=headline,
        supporting=supporting[:2],
        recommendation="Review the top contributors and decide whether action is needed.",
    ).model_dump()


def write_narrative(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = NarrativeRequest(**payload)
    user = (
        f"Question: {req.question}\n"
        f"Analysis: {json.dumps(req.analysis, default=str)}\n"
        f"Chart: {json.dumps(req.chart_config, default=str)}"
    )
    data = call_json(SYSTEM_PROMPT, user, temperature=0.3, max_tokens=400)
    if data is not None:
        try:
            resp = NarrativeResponse(**data)
            resp.headline = _trim_headline(resp.headline)
            resp.supporting = resp.supporting[:2]
            return resp.model_dump()
        except Exception:
            pass
    return _heuristic(req)
