"""Narrative agent: executive-level commentary on a finding.

Headline <= 12 words, at most two supporting sentences, one recommended action.
Falls back to a heuristic when no LLM is available.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from pydantic import BaseModel

try:
    from backend.agents.llm import call_json, fast_pipeline
except ModuleNotFoundError:
    from agents.llm import call_json, fast_pipeline


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
    metric = (analysis.get("key_metric") or "the metric").replace("_", " ")
    trend = analysis.get("trend", "stable")
    pct = analysis.get("pct_change")
    top_label = analysis.get("top_label")
    top_share = analysis.get("top_share")
    summary = (analysis.get("summary") or "").strip()

    # Headline (<= 12 words), distinct from the factual summary.
    if top_label and isinstance(top_share, (int, float)):
        headline = f"{top_label} accounts for {top_share:.0f}% of {metric}"
    elif pct is not None and trend in ("rising", "falling"):
        headline = f"{metric.capitalize()} is {trend} {abs(pct):.0f}% across the range"
    elif trend == "no_data":
        headline = "No data available for this question"
    else:
        headline = f"{metric.capitalize()} is broadly {trend}"
    headline = _trim_headline(headline)

    # Supporting sentences.
    supporting: List[str] = []
    if summary:
        supporting.append(summary)
    if pct is not None and not top_label:
        supporting.append(f"It moved {pct:+.0f}% from first to last ({trend}).")
    if analysis.get("anomalies"):
        count = len(analysis["anomalies"])
        supporting.append(f"{count} outlier{'s' if count != 1 else ''} stand out and may warrant a closer look.")
    if not supporting:
        supporting = ["This reflects the current state of your data."]

    # Contextual recommendation.
    if top_label and isinstance(top_share, (int, float)) and top_share >= 50:
        recommendation = f"{metric.capitalize()} is concentrated in {top_label} — grow other segments to reduce dependence."
    elif top_label:
        recommendation = f"Double down on {top_label} while investigating the lagging segments."
    elif trend == "falling":
        recommendation = f"Investigate the decline in {metric} and address its main drivers."
    elif trend == "rising":
        recommendation = f"Sustain the momentum in {metric} and reinforce what is working."
    else:
        recommendation = "Review the top contributors and decide whether action is needed."

    return NarrativeResponse(
        headline=headline,
        supporting=supporting[:2],
        recommendation=recommendation,
    ).model_dump()


def write_narrative(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = NarrativeRequest(**payload)

    # Fast mode: build commentary deterministically from the analysis.
    if fast_pipeline():
        return _heuristic(req)

    user = (
        f"Question: {req.question}\n"
        f"Analysis: {json.dumps(req.analysis, default=str)}\n"
        f"Chart: {json.dumps(req.chart_config, default=str)}"
    )
    data = call_json(SYSTEM_PROMPT, user, temperature=0.3, max_tokens=250)
    if data is not None:
        try:
            resp = NarrativeResponse(**data)
            resp.headline = _trim_headline(resp.headline)
            resp.supporting = resp.supporting[:2]
            return resp.model_dump()
        except Exception:
            pass
    return _heuristic(req)
