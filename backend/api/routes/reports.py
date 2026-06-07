from __future__ import annotations

import re
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

try:
    from backend.api.auth import get_current_user
    from backend.db.models import Report
    from backend.db.mongo import get_mongo_db
    from backend.tasks.scheduler import run_scheduled_report, report_pdf_path
except ModuleNotFoundError:
    from api.auth import get_current_user
    from db.models import Report
    from db.mongo import get_mongo_db
    from tasks.scheduler import run_scheduled_report, report_pdf_path

router = APIRouter()

_CRON_RE = re.compile(
    r"^(\*|[0-9,\-*/]+)\s+"
    r"(\*|[0-9,\-*/]+)\s+"
    r"(\*|[0-9,\-*/]+)\s+"
    r"(\*|[0-9,\-*/]+)\s+"
    r"(\*|[0-9,\-*/]+)$"
)


def _validate_cron(expr: str | None) -> None:
    if expr and not _CRON_RE.match(expr.strip()):
        raise HTTPException(status_code=400, detail=f"invalid cron expression: {expr!r}")


async def _get_user_report(report_id: str, user_id: str) -> Dict:
    db = get_mongo_db()
    doc = await db.reports.find_one({"_id": report_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="report not found")
    return doc


def _serialize(doc: Dict) -> Dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id", doc.get("id", "")))
    if "created_at" in doc and doc["created_at"]:
        doc["created_at"] = doc["created_at"].isoformat()
    if "last_run_at" in doc and doc["last_run_at"]:
        doc["last_run_at"] = doc["last_run_at"].isoformat()
    return doc


@router.post("")
async def create_report(body: Dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    _validate_cron(body.get("schedule_cron"))

    report = Report(
        user_id=user_id,
        name=name,
        dashboard_id=body.get("dashboard_id"),
        schedule_cron=body.get("schedule_cron"),
        recipients=body.get("recipients") or [],
    )
    db = get_mongo_db()
    await db.reports.insert_one(report.mongo_doc())
    return _serialize({"_id": report.id, **report.model_dump()})


@router.get("")
async def list_reports(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    db = get_mongo_db()
    docs = await db.reports.find({"user_id": user_id}).sort("created_at", -1).to_list(length=200)
    return {"items": [_serialize(d) for d in docs]}


@router.get("/{report_id}")
async def get_report(report_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    doc = await _get_user_report(report_id, user_id)
    return _serialize(doc)


@router.post("/{report_id}/run")
async def run_report(report_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    await _get_user_report(report_id, user_id)
    result = await run_scheduled_report(report_id)
    return {"status": "triggered", "result": result}


@router.get("/{report_id}/download")
async def download_report(report_id: str):
    """Serve the generated PDF.

    Public by report id (an unguessable UUID) so it can be opened directly from
    an <a href> link without an Authorization header — mirroring the presigned
    S3 URL pattern in the original design.
    """
    path = report_pdf_path(report_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="report PDF not generated yet — run the report first")
    return FileResponse(
        str(path),
        media_type="application/pdf",
        filename=f"{report_id}.pdf",
    )


@router.delete("/{report_id}")
async def delete_report(report_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub") or current_user.get("id")
    await _get_user_report(report_id, user_id)
    db = get_mongo_db()
    await db.reports.delete_one({"_id": report_id, "user_id": user_id})
    return {"status": "deleted"}
