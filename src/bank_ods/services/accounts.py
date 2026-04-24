import pymongo.errors
from bank_ods.db.client import get_collection
from bank_ods.services._common import clamp_limit, clamp_skip, serialize_doc


async def get_account(account_id: str) -> dict:
    """Fetch a single account by its account ID."""
    try:
        col = get_collection("accounts")
        doc = await col.find_one({"accountId": account_id}, {"_id": 0})
        if doc is None:
            return {"error": "Not found", "code": "NOT_FOUND"}
        return serialize_doc(doc)
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def list_accounts(
    client_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    skip: int = 0,
) -> dict:
    """List accounts with optional filters by client_id and/or status."""
    try:
        col = get_collection("accounts")
        query: dict = {}
        if client_id:
            query["clientId"] = client_id
        if status:
            query["status"] = status
        n = clamp_limit(limit)
        cursor = col.find(query, {"_id": 0}).skip(clamp_skip(skip)).limit(n)
        docs = await cursor.to_list(length=n)
        return {"count": len(docs), "data": [serialize_doc(d) for d in docs]}
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}
