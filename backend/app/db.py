"""MongoDB access helpers."""
from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection

from app.config import settings


@lru_cache
def get_client() -> MongoClient:
    return MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000, tz_aware=False)


def get_collection() -> Collection:
    return get_client()[settings.mongo_db][settings.mongo_collection]
