import pymongo.errors
from bank_ods.db.client import get_collection
from bank_ods.services._common import parse_date, serialize_doc


async def get_position(account_id: str, security_id: str, as_of_date: str) -> dict:
    """Fetch a single position for an account/security on a given date (YYYY-MM-DD)."""
    try:
        col = get_collection("positions")
        doc = await col.find_one(
            {
                "accountId": account_id,
                "securityId": security_id,
                "asOfDate": parse_date(as_of_date),
            },
            {"_id": 0},
        )
        if doc is None:
            return {"error": "Not found", "code": "NOT_FOUND"}
        return serialize_doc(doc)
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def get_positions(account_id: str, as_of_date: str) -> dict:
    """Fetch all positions for an account on a given date (YYYY-MM-DD)."""
    try:
        col = get_collection("positions")
        cursor = col.find(
            {"accountId": account_id, "asOfDate": parse_date(as_of_date)},
            {"_id": 0},
        ).limit(200)
        docs = await cursor.to_list(length=200)
        return {"count": len(docs), "data": [serialize_doc(d) for d in docs]}
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def get_position_history(
    account_id: str,
    security_id: str,
    from_date: str,
    to_date: str,
) -> dict:
    """Return EOD position history for an account/security over a date range."""
    try:
        col = get_collection("positions")
        cursor = (
            col.find(
                {
                    "accountId": account_id,
                    "securityId": security_id,
                    "asOfDate": {
                        "$gte": parse_date(from_date),
                        "$lte": parse_date(to_date),
                    },
                },
                {"_id": 0},
            )
            .sort("asOfDate", 1)
            .limit(200)
        )
        docs = await cursor.to_list(length=200)
        return {"count": len(docs), "data": [serialize_doc(d) for d in docs]}
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}
