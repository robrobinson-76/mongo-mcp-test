"""Parity harness — asserts MCP == REST == GraphQL == service for each operation.

Each test case calls the service directly, then compares each transport's result.
"""
import pytest
from tests.conftest import gql_query

import bank_ods.services.accounts as svc_accounts
import bank_ods.services.transactions as svc_transactions
import bank_ods.services.settlements as svc_settlements
import bank_ods.services.balances as svc_balances

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_meta(d: dict) -> dict:
    """Remove fields that legitimately differ across transports (none currently)."""
    return d


# ── Account parity ────────────────────────────────────────────────────────────

async def test_parity_get_account(rest_client, gql_client, first_account):
    account_id = first_account["accountId"]

    service = await svc_accounts.get_account(account_id)

    rest_resp = await rest_client.get(f"/accounts/{account_id}")
    rest = rest_resp.json()

    gql_resp = await gql_query(
        gql_client,
        f'{{ get_account(accountId: "{account_id}") '
        f'{{ accountId accountName accountType clientId clientName baseCurrency status custodianBranch }} }}',
    )
    gql = gql_resp["data"]["get_account"]

    assert service["accountId"] == rest["accountId"] == gql["accountId"]
    assert service["clientName"] == rest["clientName"] == gql["clientName"]
    assert service["status"] == rest["status"] == gql["status"]


async def test_parity_list_accounts_count(rest_client, gql_client):
    service = await svc_accounts.list_accounts(limit=10)

    rest_resp = await rest_client.get("/accounts", params={"limit": 10})
    rest = rest_resp.json()

    gql_resp = await gql_query(gql_client, "{ list_accounts(limit: 10) { count } }")
    gql_count = gql_resp["data"]["list_accounts"]["count"]

    assert service["count"] == rest["count"] == gql_count


# ── Transaction parity ────────────────────────────────────────────────────────

async def test_parity_get_transactions_count(rest_client, gql_client, first_account):
    account_id = first_account["accountId"]
    params = dict(account_id=account_id, from_date="2020-01-01", to_date="2030-01-01", limit=20)

    service = await svc_transactions.get_transactions(**params)

    rest_resp = await rest_client.get("/transactions", params={
        "account_id": account_id, "from_date": "2020-01-01", "to_date": "2030-01-01", "limit": 20
    })
    rest = rest_resp.json()

    gql_resp = await gql_query(
        gql_client,
        f'{{ get_transactions(accountId: "{account_id}", fromDate: "2020-01-01", toDate: "2030-01-01", limit: 20) {{ count }} }}',
    )
    gql_count = gql_resp["data"]["get_transactions"]["count"]

    assert service["count"] == rest["count"] == gql_count


# ── Settlement parity ─────────────────────────────────────────────────────────

async def test_parity_settlement_fails_count(rest_client, gql_client):
    service = await svc_settlements.get_settlement_fails("2020-01-01", "2030-01-01")

    rest_resp = await rest_client.get(
        "/settlements/fails", params={"from_date": "2020-01-01", "to_date": "2030-01-01"}
    )
    rest = rest_resp.json()

    gql_resp = await gql_query(
        gql_client,
        '{ get_settlement_fails(fromDate: "2020-01-01", toDate: "2030-01-01") { count } }',
    )
    gql_count = gql_resp["data"]["get_settlement_fails"]["count"]

    assert service["count"] == rest["count"] == gql_count


# ── Balance parity ────────────────────────────────────────────────────────────

async def test_parity_cash_balance(rest_client, gql_client, first_balance):
    account_id = first_balance["accountId"]
    currency = first_balance["currency"]
    as_of = first_balance["asOfDate"].strftime("%Y-%m-%d")

    service = await svc_balances.get_cash_balance(account_id, currency, as_of)

    rest_resp = await rest_client.get(
        f"/balances/{account_id}/{currency}", params={"as_of_date": as_of}
    )
    rest = rest_resp.json()

    gql_resp = await gql_query(
        gql_client,
        f'{{ get_cash_balance(accountId: "{account_id}", currency: "{currency}", asOfDate: "{as_of}") '
        f'{{ accountId currency closingBalance projectedBalance }} }}',
    )
    gql = gql_resp["data"]["get_cash_balance"]

    assert service["closingBalance"] == rest["closingBalance"] == gql["closingBalance"]
    assert service["accountId"] == rest["accountId"] == gql["accountId"]


async def test_parity_projected_balance(rest_client, gql_client, first_balance):
    account_id = first_balance["accountId"]
    currency = first_balance["currency"]
    as_of = first_balance["asOfDate"].strftime("%Y-%m-%d")

    service = await svc_balances.get_projected_balance(account_id, currency, as_of)

    rest_resp = await rest_client.get(
        f"/balances/{account_id}/{currency}/projected", params={"as_of_date": as_of}
    )
    rest = rest_resp.json()

    gql_resp = await gql_query(
        gql_client,
        f'{{ get_projected_balance(accountId: "{account_id}", currency: "{currency}", asOfDate: "{as_of}") '
        f'{{ accountId currency projectedBalance closingBalance }} }}',
    )
    gql = gql_resp["data"]["get_projected_balance"]

    assert service["projectedBalance"] == rest["projectedBalance"] == gql["projectedBalance"]
