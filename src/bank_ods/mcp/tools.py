from bank_ods.mcp.server import mcp
import bank_ods.services.accounts as svc_accounts
import bank_ods.services.transactions as svc_transactions
import bank_ods.services.positions as svc_positions
import bank_ods.services.settlements as svc_settlements
import bank_ods.services.balances as svc_balances


# ── Accounts ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_account(account_id: str) -> dict:
    """Fetch a single account by its account ID."""
    return await svc_accounts.get_account(account_id)


@mcp.tool()
async def list_accounts(
    client_id: str = None,
    status: str = None,
    limit: int = 20,
) -> dict:
    """List accounts with optional filters by client_id and/or status."""
    return await svc_accounts.list_accounts(client_id, status, limit)


# ── Transactions ───────────────────────────────────────────────────────────────

@mcp.tool()
async def get_transaction(transaction_id: str) -> dict:
    """Fetch a single transaction by its transaction ID."""
    return await svc_transactions.get_transaction(transaction_id)


@mcp.tool()
async def get_transactions(
    account_id: str,
    from_date: str,
    to_date: str,
    status: str = None,
    transaction_type: str = None,
    limit: int = 50,
) -> dict:
    """Query transactions for an account within a date range (YYYY-MM-DD)."""
    return await svc_transactions.get_transactions(account_id, from_date, to_date, status, transaction_type, limit)


@mcp.tool()
async def get_transaction_summary(account_id: str, from_date: str, to_date: str) -> dict:
    """Aggregate transaction count and netAmount grouped by transactionType and status."""
    return await svc_transactions.get_transaction_summary(account_id, from_date, to_date)


# ── Positions ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_position(account_id: str, security_id: str, as_of_date: str) -> dict:
    """Fetch a single position for an account/security on a given date (YYYY-MM-DD)."""
    return await svc_positions.get_position(account_id, security_id, as_of_date)


@mcp.tool()
async def get_positions(account_id: str, as_of_date: str) -> dict:
    """Fetch all positions for an account on a given date (YYYY-MM-DD)."""
    return await svc_positions.get_positions(account_id, as_of_date)


@mcp.tool()
async def get_position_history(
    account_id: str,
    security_id: str,
    from_date: str,
    to_date: str,
) -> dict:
    """Return EOD position history for an account/security over a date range."""
    return await svc_positions.get_position_history(account_id, security_id, from_date, to_date)


# ── Settlements ───────────────────────────────────────────────────────────────

@mcp.tool()
async def get_settlement(settlement_id: str) -> dict:
    """Fetch a settlement instruction by its settlement ID."""
    return await svc_settlements.get_settlement(settlement_id)


@mcp.tool()
async def get_settlement_status(transaction_id: str) -> dict:
    """Look up the settlement linked to a transaction ID."""
    return await svc_settlements.get_settlement_status(transaction_id)


@mcp.tool()
async def get_settlements(
    account_id: str,
    settlement_date: str,
    status: str = None,
) -> dict:
    """Query settlements for an account on a specific settlement date (YYYY-MM-DD)."""
    return await svc_settlements.get_settlements(account_id, settlement_date, status)


@mcp.tool()
async def get_settlement_fails(
    from_date: str,
    to_date: str,
    account_id: str = None,
) -> dict:
    """Find all FAILED settlements within a date window, optionally filtered by account."""
    return await svc_settlements.get_settlement_fails(from_date, to_date, account_id)


# ── Balances ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_cash_balance(account_id: str, currency: str, as_of_date: str) -> dict:
    """Fetch the cash balance for a specific account, currency, and date (YYYY-MM-DD)."""
    return await svc_balances.get_cash_balance(account_id, currency, as_of_date)


@mcp.tool()
async def get_cash_balances(account_id: str, as_of_date: str) -> dict:
    """Fetch all currency balances for an account on a given date (YYYY-MM-DD)."""
    return await svc_balances.get_cash_balances(account_id, as_of_date)


@mcp.tool()
async def get_projected_balance(account_id: str, currency: str, as_of_date: str) -> dict:
    """Return the projected balance (closing net of pending) for an account/currency/date."""
    return await svc_balances.get_projected_balance(account_id, currency, as_of_date)
