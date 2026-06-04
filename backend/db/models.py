from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class SourceType(str, enum.Enum):
    postgres = "postgres"
    mysql = "mysql"
    csv = "csv"
    api = "api"
    sheets = "sheets"
    mongodb = "mongodb"


class MongoDocument(BaseModel):
    id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utcnow)

    def mongo_doc(self) -> Dict[str, Any]:
        doc = self.model_dump()
        doc["_id"] = doc.pop("id")
        return doc

    @classmethod
    def from_mongo_doc(cls, doc: Dict[str, Any] | None):
        if not doc:
            return None
        payload = dict(doc)
        payload["id"] = str(payload.pop("_id", payload.get("id", new_id())))
        return cls(**payload)


class User(MongoDocument):
    email: str
    hashed_password: str
    plan: str = "free"


class DataSource(MongoDocument):
    user_id: str
    name: str
    type: SourceType
    connection_config: Dict[str, Any]
    is_active: bool = True


class Query(MongoDocument):
    user_id: str
    source_id: str
    natural_language: str
    generated_sql: str
    result_cache: Optional[List[Dict[str, Any]]] = None
    execution_ms: Optional[int] = None


class Dashboard(MongoDocument):
    user_id: str
    name: str
    layout_json: Dict[str, Any]


class Report(MongoDocument):
    user_id: str
    dashboard_id: Optional[str] = None
    name: str
    schedule_cron: Optional[str] = None
    last_run_at: Optional[datetime] = None
    output_s3_url: Optional[str] = None
    recipients: Optional[List[str]] = None
    is_active: bool = True


class AgentRun(MongoDocument):
    query_id: Optional[str] = None
    agent_name: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
