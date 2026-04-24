from fastapi import APIRouter

import bank_ods.services.balances as svc

router = APIRouter()


@router.get("/{account_id}/{currency}/projected")
async def get_projected_balance(account_id: str, currency: str, as_of_date: str):
    return await svc.get_projected_balance(account_id, currency, as_of_date)


@router.get("/{account_id}/{currency}")
async def get_cash_balance(account_id: str, currency: str, as_of_date: str):
    return await svc.get_cash_balance(account_id, currency, as_of_date)


@router.get("/{account_id}")
async def get_cash_balances(account_id: str, as_of_date: str):
    return await svc.get_cash_balances(account_id, as_of_date)
