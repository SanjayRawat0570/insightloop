from fastapi import APIRouter
from typing import Dict

router = APIRouter()

@router.post("")
async def create_report(body: Dict):
    return {"id": "report-id"}

@router.get("")
async def list_reports():
    return {"items": []}

@router.get("/{report_id}")
async def get_report(report_id: str):
    return {"id": report_id}

@router.post("/{report_id}/run")
async def run_report(report_id: str):
    return {"status": "running"}

@router.delete("/{report_id}")
async def delete_report(report_id: str):
    return {"status": "deleted"}
