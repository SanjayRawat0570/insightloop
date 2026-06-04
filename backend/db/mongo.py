from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from backend.db.models import AgentRun, DataSource, Query, Report, User

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://mongo:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "insightloop")

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URL)
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    return get_mongo_client()[MONGODB_DB]


async def ensure_indexes() -> None:
    db = get_mongo_db()
    await db.users.create_index("email", unique=True)
    await db.data_sources.create_index([("user_id", 1), ("name", 1)])
    await db.queries.create_index([("user_id", 1), ("created_at", -1)])
    await db.agent_runs.create_index([("query_id", 1), ("created_at", -1)])


async def create_user(user: User) -> User:
    doc = user.mongo_doc()
    await get_mongo_db().users.insert_one(doc)
    return user


async def find_user_by_email(email: str) -> Optional[User]:
    doc = await get_mongo_db().users.find_one({"email": email})
    return User.from_mongo_doc(doc)


async def create_data_source(data_source: DataSource) -> DataSource:
    await get_mongo_db().data_sources.insert_one(data_source.mongo_doc())
    return data_source


async def get_data_source(source_id: str) -> Optional[DataSource]:
    doc = await get_mongo_db().data_sources.find_one({"_id": source_id})
    return DataSource.from_mongo_doc(doc)


async def create_query(query: Query) -> Query:
    await get_mongo_db().queries.insert_one(query.mongo_doc())
    return query


async def update_query(query_id: str, patch: Dict[str, Any]) -> None:
    await get_mongo_db().queries.update_one({"_id": query_id}, {"$set": patch})


async def list_queries_by_user(user_id: str) -> List[Query]:
    rows = await get_mongo_db().queries.find({"user_id": user_id}).sort("created_at", -1).to_list(length=100)
    return [Query.from_mongo_doc(row) for row in rows if row]


async def get_query(query_id: str) -> Optional[Query]:
    doc = await get_mongo_db().queries.find_one({"_id": query_id})
    return Query.from_mongo_doc(doc)


async def create_agent_run(agent_run: AgentRun) -> AgentRun:
    await get_mongo_db().agent_runs.insert_one(agent_run.mongo_doc())
    return agent_run


async def list_agent_runs_by_query(query_id: str) -> List[AgentRun]:
    rows = await get_mongo_db().agent_runs.find({"query_id": query_id}).sort("created_at", -1).to_list(length=100)
    return [AgentRun.from_mongo_doc(row) for row in rows if row]
