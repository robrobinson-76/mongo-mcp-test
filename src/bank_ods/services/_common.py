from datetime import datetime
from typing import Any

import pymongo.errors
from bson import ObjectId


def parse_date(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str)


def clamp_limit(limit: int, maximum: int = 200) -> int:
    return min(max(1, limit), maximum)


def clamp_skip(skip: int) -> int:
    return max(0, skip)


def serialize_doc(doc: dict) -> dict:
    return _serialize({k: v for k, v in doc.items() if k != "_id"})


def _serialize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj
