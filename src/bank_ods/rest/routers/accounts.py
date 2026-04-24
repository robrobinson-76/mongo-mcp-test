from typing import Optional

from fastapi import APIRouter

import bank_ods.services.accounts as svc
from bank_ods.rest.errors import check

router = APIRouter()


@router.get("/{account_id}")
async def get_account(account_id: str):
    return check(await svc.get_account(account_id))


@router.get("")
async def list_accounts(
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
):
    return check(await svc.list_accounts(client_id, status, limit, skip))
