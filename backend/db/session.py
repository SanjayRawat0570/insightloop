from backend.db.mongo import get_mongo_db


async def get_async_session():
    # Compatibility dependency kept for route signatures; returns the Mongo database.
    yield get_mongo_db()
