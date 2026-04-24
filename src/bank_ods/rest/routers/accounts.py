from typing import Optional

from fastapi import APIRouter

import bank_ods.services.accounts as svc

router = APIRouter()


@router.get("/{account_id}")
async def get_account(account_id: str):
    return await svc.get_account(account_id)


@router.get("")
async def list_accounts(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
):
    return await svc.list_accounts(client_id, status, limit)
