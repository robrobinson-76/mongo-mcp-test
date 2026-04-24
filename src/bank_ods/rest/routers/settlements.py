from typing import Optional

from fastapi import APIRouter

import bank_ods.services.settlements as svc

router = APIRouter()


@router.get("/fails")
async def get_settlement_fails(from_date: str, to_date: str, account_id: Optional[str] = None):
    return await svc.get_settlement_fails(from_date, to_date, account_id)


@router.get("/by-transaction/{transaction_id}")
async def get_settlement_status(transaction_id: str):
    return await svc.get_settlement_status(transaction_id)


@router.get("/{settlement_id}")
async def get_settlement(settlement_id: str):
    return await svc.get_settlement(settlement_id)


@router.get("")
async def get_settlements(account_id: str, settlement_date: str, status: Optional[str] = None):
    return await svc.get_settlements(account_id, settlement_date, status)
