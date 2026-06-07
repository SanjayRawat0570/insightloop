"""Report generation tasks (synchronous — no Celery/Redis dependency).

`run_scheduled_report` compiles a PDF report from the user's completed queries,
stores it on disk, links it on the report document, and (optionally) emails it.
It is awaited directly by the API route and by any future scheduler.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from backend.db.mongo import get_mongo_db
    from backend.utils.pdf_gen import render_pdf
except ModuleNotFoundError:
    from db.mongo import get_mongo_db
    from utils.pdf_gen import render_pdf

# Where generated PDFs are written. Served back via /api/reports/{id}/download.
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "reports_output"
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")


def report_pdf_path(report_id: str) -> Path:
    return OUTPUT_DIR / f"{report_id}.pdf"


def _exec_summary(sections: List[Dict[str, Any]]) -> str:
    """Two-sentence summary stitched from the first section's findings."""
    if not sections:
        return "No completed queries were available to include in this report."
    narrative = sections[0].get("narrative") or {}
    head = (narrative.get("headline") or sections[0].get("title") or "Report generated").rstrip(".")
    support = (narrative.get("supporting") or [""])[0].strip()
    parts = [f"{head}."]
    if support:
        parts.append(support if support.endswith(".") else support + ".")
    if len(sections) > 1:
        parts.append(f"This report covers {len(sections)} analyses.")
    return " ".join(parts).strip()


async def run_scheduled_report(report_id: str) -> Dict[str, Any]:
    """Compile and persist a PDF report. Returns a status dict."""
    db = get_mongo_db()
    report = await db.reports.find_one({"_id": report_id})
    if not report:
        return {"report_id": report_id, "status": "error", "error": "report not found"}

    user_id = report.get("user_id")

    # Gather the user's completed queries (those with a chart + narrative). These
    # are the analyses that make up the report. In production this would be scoped
    # to the report's dashboard tiles; here we use the user's recent results.
    cursor = (
        db.queries.find({"user_id": user_id, "chart_config": {"$ne": None}})
        .sort("created_at", -1)
    )
    queries = await cursor.to_list(length=10)

    sections: List[Dict[str, Any]] = []
    for q in queries:
        sections.append(
            {
                "title": q.get("natural_language") or "Query",
                "chart_config": q.get("chart_config") or {},
                "narrative": q.get("narrative") or {},
                "data_table": (q.get("result_cache") or [])[:50],
                "sql_used": q.get("generated_sql") or "",
            }
        )

    report_json = {
        "title": report.get("name") or "InsightLoop Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executive_summary": _exec_summary(sections),
        "sections": sections,
    }

    # Render and persist the PDF.
    pdf_bytes = render_pdf(report_json)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_pdf_path(report_id).write_bytes(pdf_bytes)

    download_url = f"{PUBLIC_API_URL}/api/reports/{report_id}/download"
    ran_at = datetime.now(timezone.utc)
    await db.reports.update_one(
        {"_id": report_id},
        {"$set": {"last_run_at": ran_at, "output_s3_url": download_url}},
    )

    # Optional email delivery (only if SendGrid configured and recipients set).
    emailed = False
    recipients = report.get("recipients") or []
    if recipients and os.environ.get("SENDGRID_API_KEY"):
        try:
            try:
                from backend.utils.email import send_report_email
            except ModuleNotFoundError:
                from utils.email import send_report_email
            send_report_email(
                recipients,
                report_json["title"],
                download_url,
                report_json["executive_summary"],
            )
            emailed = True
        except Exception:
            emailed = False

    return {
        "report_id": report_id,
        "status": "completed",
        "sections": len(sections),
        "pdf_bytes": len(pdf_bytes),
        "download_url": download_url,
        "emailed": emailed,
        "last_run_at": ran_at.isoformat(),
    }


def cleanup_old_results() -> bool:
    # Placeholder: delete cached results older than retention.
    return True
