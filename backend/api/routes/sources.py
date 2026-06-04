from fastapi import APIRouter, HTTPException
from typing import Dict

router = APIRouter()

@router.post("")
async def create_source(body: Dict):
    # Validate and attempt test connection
    return {"id": "source-id", "name": body.get('name')}

@router.get("")
async def list_sources():
    return {"items": []}

@router.delete("/{source_id}")
async def delete_source(source_id: str):
    return {"status": "deleted"}

@router.post("/{source_id}/schema")
async def get_schema(source_id: str):
    return {"tables": []}
