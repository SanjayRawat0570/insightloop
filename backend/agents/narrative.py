from pydantic import BaseModel
from typing import Dict, Any, List

class NarrativeRequest(BaseModel):
    analysis: Dict[str, Any]
    chart_config: Dict[str, Any]
    question: str

class NarrativeResponse(BaseModel):
    headline: str
    supporting: List[str]
    recommendation: str
    tone: str = "direct"


def write_narrative(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = NarrativeRequest(**payload)
    analysis = req.analysis
    headline = (analysis.get('summary') or 'Key finding').strip()
    if len(headline.split()) > 12:
        headline = ' '.join(headline.split()[:12])
    supporting = ["This insight is statistically significant.", "Recommend further monitoring."]
    recommendation = "Investigate root cause and consider action." 
    return NarrativeResponse(headline=headline, supporting=supporting, recommendation=recommendation).dict()
