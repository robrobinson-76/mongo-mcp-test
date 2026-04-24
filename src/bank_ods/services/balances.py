import pymongo.errors
from bank_ods.db.client import get_collection
from bank_ods.services._common import clamp_skip, parse_date, serialize_doc

_PAGE_SIZE = 50


async def get_cash_balance(account_id: str, currency: str, as_of_date: str) -> dict:
    """Fetch the cash balance for a specific account, currency, and date (YYYY-MM-DD)."""
    try:
        col = get_collection("cash_balances")
        doc = await col.find_one(
            {
                "accountId": account_id,
                "currency": currency,
                "asOfDate": parse_date(as_of_date),
            },
            {"_id": 0},
        )
        if doc is None:
            return {"error": "Not found", "code": "NOT_FOUND"}
        return serialize_doc(doc)
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def get_cash_balances(account_id: str, as_of_date: str, skip: int = 0) -> dict:
    """Fetch all currency balances for an account on a given date (YYYY-MM-DD)."""
    try:
        col = get_collection("cash_balances")
        cursor = (
            col.find(
                {"accountId": account_id, "asOfDate": parse_date(as_of_date)},
                {"_id": 0},
            )
            .skip(clamp_skip(skip))
            .limit(_PAGE_SIZE)
        )
        docs = await cursor.to_list(length=_PAGE_SIZE)
        return {"count": len(docs), "data": [serialize_doc(d) for d in docs]}
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}


async def get_projected_balance(account_id: str, currency: str, as_of_date: str) -> dict:
    """Return the projected balance (closing net of pending) for an account/currency/date."""
    try:
        col = get_collection("cash_balances")
        doc = await col.find_one(
            {
                "accountId": account_id,
                "currency": currency,
                "asOfDate": parse_date(as_of_date),
            },
            {"_id": 0},
        )
        if doc is None:
            return {"error": "Not found", "code": "NOT_FOUND"}
        s = serialize_doc(doc)
        return {
            "accountId": s["accountId"],
            "currency": s["currency"],
            "asOfDate": s["asOfDate"],
            "closingBalance": s.get("closingBalance"),
            "pendingCredits": s.get("pendingCredits"),
            "pendingDebits": s.get("pendingDebits"),
            "projectedBalance": s.get("projectedBalance"),
        }
    except pymongo.errors.PyMongoError as e:
        return {"error": str(e), "code": "MONGO_ERROR"}
