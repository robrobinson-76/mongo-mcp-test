"""GraphQL layer tests."""
import pytest
from tests.conftest import gql_query

pytestmark = pytest.mark.asyncio


async def test_gql_list_accounts(gql_client):
    result = await gql_query(
        gql_client,
        "{ list_accounts(limit: 3) { count data { accountId clientName status } } }",
    )
    assert "errors" not in result
    payload = result["data"]["list_accounts"]
    assert payload["count"] > 0
    assert len(payload["data"]) <= 3


async def test_gql_get_account(gql_client, first_account):
    result = await gql_query(
        gql_client,
        f'{{ get_account(accountId: "{first_account["accountId"]}") {{ accountId clientName }} }}',
    )
    assert "errors" not in result
    acct = result["data"]["get_account"]
    assert acct["accountId"] == first_account["accountId"]


async def test_gql_get_transactions(gql_client, first_account):
    result = await gql_query(
        gql_client,
        f'{{ get_transactions(accountId: "{first_account["accountId"]}", fromDate: "2020-01-01", toDate: "2030-01-01", limit: 5) {{ count data {{ transactionId status }} }} }}',
    )
    assert "errors" not in result
    assert "count" in result["data"]["get_transactions"]


async def test_gql_settlement_fails(gql_client):
    result = await gql_query(
        gql_client,
        '{ get_settlement_fails(fromDate: "2020-01-01", toDate: "2030-01-01") { count } }',
    )
    assert "errors" not in result
    assert result["data"]["get_settlement_fails"]["count"] >= 0


async def test_gql_cash_balances(gql_client, first_balance):
    as_of = first_balance["asOfDate"].strftime("%Y-%m-%d")
    result = await gql_query(
        gql_client,
        f'{{ get_cash_balances(accountId: "{first_balance["accountId"]}", asOfDate: "{as_of}") {{ count data {{ currency closingBalance }} }} }}',
    )
    assert "errors" not in result
    assert result["data"]["get_cash_balances"]["count"] > 0
