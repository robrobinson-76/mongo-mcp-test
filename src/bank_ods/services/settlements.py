import pymongo.errors
from bank_ods.db.client import get_collection
from bank_ods.services._common import parse_date, serialize_doc


async def get_settlement(settlement_id: str) -> dict:
    """Fetch a settlement instruction by its settlement ID."""
    try:
        col = get_collection("settlements")
        doc = await col.find_one({"settlementId": settlement_id}, {"_id": 0})
        if doc is None:
            return {"error": "Not found", "code": "NOT_FOUND"}
        return serialize_doc(doc)
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def get_settlement_status(transaction_id: str) -> dict:
    """Look up the settlement linked to a transaction ID."""
    try:
        col = get_collection("settlements")
        doc = await col.find_one({"transactionId": transaction_id}, {"_id": 0})
        if doc is None:
            return {"error": "Not found", "code": "NOT_FOUND"}
        return serialize_doc(doc)
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def get_settlements(
    account_id: str,
    settlement_date: str,
    status: str | None = None,
) -> dict:
    """Query settlements for an account on a specific settlement date (YYYY-MM-DD)."""
    try:
        col = get_collection("settlements")
        query: dict = {
            "accountId": account_id,
            "settlementDate": parse_date(settlement_date),
        }
        if status:
            query["status"] = status
        docs = await col.find(query, {"_id": 0}).to_list(length=200)
        return {"count": len(docs), "data": [serialize_doc(d) for d in docs]}
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def get_settlement_fails(
    from_date: str,
    to_date: str,
    account_id: str | None = None,
) -> dict:
    """Find all FAILED settlements within a date window, optionally filtered by account."""
    try:
        col = get_collection("settlements")
        query: dict = {
            "status": "FAILED",
            "settlementDate": {
                "$gte": parse_date(from_date),
                "$lte": parse_date(to_date),
            },
        }
        if account_id:
            query["accountId"] = account_id
        cursor = col.find(query, {"_id": 0}).sort("settlementDate", -1).limit(200)
        docs = await cursor.to_list(length=200)
        return {"count": len(docs), "data": [serialize_doc(d) for d in docs]}
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}
