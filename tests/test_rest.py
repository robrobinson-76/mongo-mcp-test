"""REST layer tests — assert each endpoint returns same shape as service layer."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_rest_get_account(rest_client, first_account):
    resp = await rest_client.get(f"/accounts/{first_account['accountId']}")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" not in data
    assert data["accountId"] == first_account["accountId"]


async def test_rest_get_account_not_found(rest_client):
    resp = await rest_client.get("/accounts/ACC-DOES-NOT-EXIST")
    assert resp.status_code == 200
    assert resp.json().get("code") == "NOT_FOUND"


async def test_rest_list_accounts(rest_client):
    resp = await rest_client.get("/accounts", params={"limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert isinstance(data["data"], list)


async def test_rest_get_transactions(rest_client, first_account):
    resp = await rest_client.get(
        "/transactions",
        params={
            "account_id": first_account["accountId"],
            "from_date": "2020-01-01",
            "to_date": "2030-01-01",
            "limit": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data


async def test_rest_transaction_summary(rest_client, first_account):
    resp = await rest_client.get(
        "/transactions/summary",
        params={
            "account_id": first_account["accountId"],
            "from_date": "2020-01-01",
            "to_date": "2030-01-01",
        },
    )
    assert resp.status_code == 200
    assert "count" in resp.json()


async def test_rest_settlement_fails(rest_client):
    resp = await rest_client.get(
        "/settlements/fails",
        params={"from_date": "2020-01-01", "to_date": "2030-01-01"},
    )
    assert resp.status_code == 200
    assert "count" in resp.json()


async def test_rest_cash_balances(rest_client, first_balance):
    resp = await rest_client.get(
        f"/balances/{first_balance['accountId']}",
        params={"as_of_date": first_balance["asOfDate"].strftime("%Y-%m-%d")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data


async def test_rest_projected_balance(rest_client, first_balance):
    resp = await rest_client.get(
        f"/balances/{first_balance['accountId']}/{first_balance['currency']}/projected",
        params={"as_of_date": first_balance["asOfDate"].strftime("%Y-%m-%d")},
    )
    assert resp.status_code == 200
    assert "projectedBalance" in resp.json()
