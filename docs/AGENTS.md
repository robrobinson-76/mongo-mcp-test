# Agents Guide — Bank ODS MCP Server

## Overview

This document covers how AI agents (Claude Code or any MCP-capable client) should interact with the `bank-ods` MCP server. It covers tool naming conventions, parameter formats, query patterns, error handling, and what to avoid.

---

## MCP Server Identity

**Server name:** `bank-ods`
**Transport:** controlled by `MCP_TRANSPORT` env var — `stdio` (default, Claude Desktop / VS Code) or `sse` (chatbot / K8s deployment)
**Start command:** `python -m bank_ods.mcp`

The server exposes 15 tools across five domains. All tools are read-only. There are no mutation tools.

---

## Tool Naming Convention

All tools follow the pattern `verb_noun` with snake_case:

```
get_<singular>     — fetch a single record by ID
list_<plural>      — enumerate records, usually with filters
get_<noun>_<qualifier> — query with a specific perspective
```

| Pattern | Examples |
|---|---|
| `get_<entity>` | `get_account`, `get_transaction`, `get_settlement` |
| `list_<entities>` | `list_accounts` |
| `get_<entities>` | `get_transactions`, `get_positions`, `get_settlements` |
| `get_<entity>_<qualifier>` | `get_settlement_status`, `get_settlement_fails`, `get_transaction_summary`, `get_position_history`, `get_projected_balance` |

When unsure whether to use singular or plural: singular (`get_account`) takes an ID and returns one record; plural (`get_transactions`) takes filter parameters and returns a list.

---

## Complete Tool Reference

### Accounts

#### `get_account`

Fetch a single account by its account ID.

**Parameters:**
- `account_id: str` — the account identifier (e.g., `"ACC-0001"`)

**Returns:** Full account document or `{"error": ..., "code": "NOT_FOUND"}`

**Example:**
```
get_account(account_id="ACC-0001")
```

---

#### `list_accounts`

List all accounts, with optional filters.

**Parameters:**
- `client_id: str` *(optional)* — filter to a specific client
- `status: str` *(optional)* — `"ACTIVE"`, `"SUSPENDED"`, or `"CLOSED"`
- `limit: int` *(optional, default 20, max 200)* — number of results
- `skip: int` *(optional, default 0)* — number of records to skip (for pagination)

**Returns:** `{"count": N, "data": [...]}`

**Example:**
```
list_accounts(status="ACTIVE", limit=10)
```

---

### Transactions

#### `get_transaction`

Fetch a single transaction by ID.

**Parameters:**
- `transaction_id: str`

**Returns:** Full transaction document or NOT_FOUND

---

#### `get_transactions`

Query transactions for an account over a date range.

**Parameters:**
- `account_id: str` — required
- `from_date: str` — ISO 8601 date, `"YYYY-MM-DD"`
- `to_date: str` — ISO 8601 date, `"YYYY-MM-DD"`
- `status: str` *(optional)* — `"PENDING"`, `"MATCHED"`, `"SETTLED"`, `"FAILED"`, `"CANCELLED"`
- `transaction_type: str` *(optional)* — `"BUY"`, `"SELL"`, `"DEPOSIT"`, `"WITHDRAWAL"`, `"TRANSFER_IN"`, `"TRANSFER_OUT"`, `"DIVIDEND"`, `"FX"`
- `limit: int` *(optional, default 50, max 200)*
- `skip: int` *(optional, default 0)* — number of records to skip (for pagination)

**Returns:** `{"count": N, "data": [...]}` sorted by tradeDate descending

**Example:**
```
get_transactions(account_id="ACC-0001", from_date="2025-01-01", to_date="2025-03-31", status="SETTLED")
```

---

#### `get_transaction_summary`

Aggregate transaction counts and net amounts grouped by type and status.

**Parameters:**
- `account_id: str`
- `from_date: str`
- `to_date: str`

**Returns:** `{"count": N, "data": [{transactionType, status, count, totalNetAmount}]}`

Use this for a quick financial summary instead of fetching and counting transactions manually.

---

### Positions

#### `get_position`

Fetch a single position for one account/security on a specific date.

**Parameters:**
- `account_id: str`
- `security_id: str`
- `as_of_date: str` — `"YYYY-MM-DD"`

**Returns:** Full position document or NOT_FOUND

---

#### `get_positions`

Fetch all security holdings for an account on a given date.

**Parameters:**
- `account_id: str`
- `as_of_date: str` — `"YYYY-MM-DD"`

**Returns:** `{"count": N, "data": [...]}` — all securities held that day

---

#### `get_position_history`

Return EOD position snapshots for one security over a date range.

**Parameters:**
- `account_id: str`
- `security_id: str`
- `from_date: str`
- `to_date: str`

**Returns:** `{"count": N, "data": [...]}` sorted ascending by `asOfDate`

Use this to observe how a holding changed over time (quantity, market value, unrealizedPnL).

---

### Settlements

#### `get_settlement`

Fetch a settlement instruction by its settlement ID.

**Parameters:**
- `settlement_id: str`

---

#### `get_settlement_status`

Look up the settlement linked to a transaction. Use this when you have a transaction ID and want to know its settlement outcome.

**Parameters:**
- `transaction_id: str`

**Returns:** Full settlement document (including statusHistory) or NOT_FOUND

---

#### `get_settlements`

Query settlements for an account on a specific settlement date.

**Parameters:**
- `account_id: str`
- `settlement_date: str` — `"YYYY-MM-DD"`
- `status: str` *(optional)* — `"PENDING"`, `"INSTRUCTED"`, `"MATCHED"`, `"SETTLED"`, `"FAILED"`, `"CANCELLED"`, `"RECYCLED"`

**Returns:** `{"count": N, "data": [...]}`

---

#### `get_settlement_fails`

Find all failed settlements within a date window.

**Parameters:**
- `from_date: str`
- `to_date: str`
- `account_id: str` *(optional)* — scope to one account

**Returns:** `{"count": N, "data": [...]}` sorted by settlementDate descending

This is a direct operational query — use it to identify risk or reconciliation issues.

---

### Balances

#### `get_cash_balance`

Fetch the cash balance for a specific account, currency, and date.

**Parameters:**
- `account_id: str`
- `currency: str` — ISO 4217 (e.g., `"USD"`, `"CAD"`)
- `as_of_date: str` — `"YYYY-MM-DD"`

**Returns:** Full balance document including opening, closing, pending, and projected amounts

---

#### `get_cash_balances`

Fetch all currency balances for an account on a given date.

**Parameters:**
- `account_id: str`
- `as_of_date: str`

**Returns:** `{"count": N, "data": [...]}` — one entry per currency

---

#### `get_projected_balance`

Return the projected balance for one account/currency/date.

**Parameters:**
- `account_id: str`
- `currency: str`
- `as_of_date: str`

**Returns:** `{accountId, currency, asOfDate, closingBalance, pendingCredits, pendingDebits, projectedBalance}`

`projectedBalance = closingBalance + pendingCredits − pendingDebits`

Use this when you need a forward-looking view that includes unsettled cash flows.

---

## Parameter Formats

### Dates

Always use ISO 8601 format: `"YYYY-MM-DD"`

```
✓  "2025-03-31"
✗  "31/03/2025"
✗  "March 31, 2025"
✗  "2025-3-31"
```

### IDs

IDs are strings that match the data. Seed data uses patterns like:
- Accounts: `"ACC-XXXX"` (4-digit numeric suffix)
- Transactions: `"TXN-XXXXXXXX"` (8-character alphanumeric)
- Securities: `"SEC-XXXX"`
- Settlements: `"SET-XXXXXXXX"`

When you don't know an ID, use a list tool first (`list_accounts`, `get_transactions`) to discover valid IDs before fetching a specific record.

### Status Values

Status values are uppercase strings matching the literals defined in the models. Never guess or abbreviate:

| Domain | Valid Status Values |
|---|---|
| Account | ACTIVE, SUSPENDED, CLOSED |
| Transaction | PENDING, MATCHED, SETTLED, FAILED, CANCELLED |
| Settlement | PENDING, INSTRUCTED, MATCHED, SETTLED, FAILED, CANCELLED, RECYCLED |
| Position | n/a (filter by date, not status) |
| Cash Balance | n/a (filter by date) |

### Transaction Types

`BUY`, `SELL`, `DEPOSIT`, `WITHDRAWAL`, `TRANSFER_IN`, `TRANSFER_OUT`, `DIVIDEND`, `FX`

### Asset Classes

`EQUITY`, `GOVT_BOND`, `CORP_BOND`, `FUND`, `CASH`

---

## Error Handling

All tools return errors as plain dicts, never as exceptions. Always check the response before using it.

```python
# Good: check for error before accessing fields
result = get_account(account_id="ACC-0001")
if "error" in result:
    # result["code"] is "NOT_FOUND" or "MONGO_ERROR"
    # result["error"] has a description
else:
    account_name = result["accountName"]
```

**Error codes:**
- `"NOT_FOUND"` — the record does not exist
- `"MONGO_ERROR"` — database-level error (connection issue, query failure)

For list tools, an empty result is not an error: `{"count": 0, "data": []}` is a valid response meaning "no records matched."

---

## Common Query Patterns

### Discover then fetch

When you don't have an ID, list first:

```
1. list_accounts(status="ACTIVE", limit=5)
   → pick an account_id from result["data"][0]["accountId"]

2. get_account(account_id="ACC-0001")
   → full account details
```

### Transaction investigation

```
1. get_transactions(account_id, from_date, to_date, status="FAILED")
   → identify failed transactions

2. get_settlement_status(transaction_id=txn["transactionId"])
   → inspect the settlement record and statusHistory
```

### Portfolio snapshot

```
1. get_positions(account_id, as_of_date)
   → all securities held

2. get_cash_balances(account_id, as_of_date)
   → cash positions across currencies
```

### Cash flow analysis

```
1. get_transaction_summary(account_id, from_date, to_date)
   → aggregated counts and net amounts by type/status

2. get_projected_balance(account_id, currency, as_of_date)
   → forward-looking cash position
```

### Settlement risk

```
1. get_settlement_fails(from_date, to_date)
   → all fails across all accounts in the window

2. get_settlement_fails(from_date, to_date, account_id=target_account)
   → scoped to one account
```

### Position time series

```
get_position_history(account_id, security_id, from_date, to_date)
→ track how quantity, marketValue, and unrealizedPnL evolved
```

---

## Limits and Performance

| Tool | Default Limit | Max Limit | Supports skip |
|---|---|---|---|
| list_accounts | 20 | 200 | yes |
| get_transactions | 50 | 200 | yes |
| get_positions | 200 | 200 | yes |
| get_position_history | 200 | 200 | yes |
| get_settlements | 200 | 200 | yes |
| get_settlement_fails | 200 | 200 | yes |
| get_cash_balances | 50 | 50 | yes |

When `count` in the result equals your `limit`, there may be more records. Use `skip` to page forward, or narrow the date range and add filters.

---

## What This Server Does Not Do

- **No mutations.** There are no create, update, or delete tools. This is a read-only ODS view.
- **No cross-account aggregation.** There is no "all accounts" summary tool; iterate `list_accounts` if you need portfolio-wide data.
- **No security master search.** There is no `search_securities` or `get_security` tool in the current implementation. Security data is embedded in position and transaction results.
- **No real-time prices.** All prices are EOD snapshots from seed data. `marketPrice` and `marketValue` reflect the seeded values, not live market data.
- **No authentication.** The server connects to a local MongoDB instance with no credentials.

---

## Package and Module Naming

### Python Package: `bank_ods`

The root package is `bank_ods` (underscore). The distribution name in `pyproject.toml` is `bank-ods` (hyphen).

```
import bank_ods.services.accounts    # ✓ correct
import bank-ods.services.accounts    # ✗ invalid Python
```

### Module Layout Conventions

| Module path | Role |
|---|---|
| `bank_ods.config` | Env loading only — no logic |
| `bank_ods.models.*` | Pydantic models + `COLLECTION` + `INDEXES` constants |
| `bank_ods.models.registry` | `ENTITIES` list — import this to iterate all models |
| `bank_ods.db.client` | `get_client()`, `get_db()`, `get_collection(name)` |
| `bank_ods.db.indexes` | `ensure_indexes()` — call once on startup, idempotent |
| `bank_ods.services.*` | All async business logic — single source of truth |
| `bank_ods.mcp.server` | `mcp = FastMCP("bank-ods")` instance |
| `bank_ods.mcp.tools` | `@mcp.tool()` decorators — thin wrappers only |
| `bank_ods.rest.app` | `app = FastAPI(...)` — import target for uvicorn |
| `bank_ods.rest.routers.*` | `APIRouter` instances — no business logic |
| `bank_ods.graphql.app` | `app = create_app()` — import target for uvicorn |
| `bank_ods.graphql.sdl` | `generate_sdl()` — called once at startup |
| `bank_ods.graphql.resolvers` | `query = QueryType()` — thin resolvers only |

### Naming Rules

- **Service functions:** `snake_case` matching the tool names: `get_account`, `list_accounts`, `get_cash_balance`
- **Model classes:** `PascalCase`: `Account`, `Transaction`, `CashBalance`
- **Collection names:** `snake_case` plural: `accounts`, `cash_balances`, `transactions`
- **Field names in models:** `camelCase` (MongoDB convention): `accountId`, `asOfDate`, `netAmount`
- **REST endpoint paths:** kebab-case where needed, otherwise match model names: `/by-transaction/{id}`, `/projected`
- **GraphQL field names:** `camelCase` in schema and resolver arguments: `accountId`, `fromDate`, `asOfDate`
- **MCP tool parameters:** `snake_case` at the Python level, exposed as-is to the LLM: `account_id`, `from_date`

---

## Best Practices for Agents

### Always check `count` before iterating `data`

```python
result = get_positions(account_id="ACC-0001", as_of_date="2025-03-31")
if result.get("count", 0) == 0:
    # no positions on that date — try a different date
```

### Prefer summary tools for analytics

`get_transaction_summary` runs a MongoDB aggregation pipeline. It is far faster than calling `get_transactions` and counting/summing client-side. Use it whenever you need totals.

### Use `get_settlement_status` when you have a transaction ID

Do not construct settlement IDs from transaction IDs. Use `get_settlement_status(transaction_id=...)` which looks up by the `transactionId` field on the settlement document.

### Positions are date-anchored

`get_positions` and `get_position` require an exact `as_of_date`. If you get NOT_FOUND, the account had no positions on that specific date (e.g., a weekend or a date before the account was active). Try the most recent business day.

### Cash balances require both account and currency

`get_cash_balance` requires all three: `account_id`, `currency`, and `as_of_date`. Use `get_cash_balances` (no currency argument) to discover which currencies an account holds before fetching a specific one.

### Settlement fails are cross-account by default

`get_settlement_fails` returns fails across all accounts in the date range unless you pass `account_id`. Start broad (all accounts) for operational monitoring, then narrow to investigate a specific account.

### Date range queries: use explicit YYYY-MM-DD strings

The service layer calls `datetime.fromisoformat()` on date strings. Partial ISO formats (e.g., `"2025-03"`) will fail. Always use full `"YYYY-MM-DD"` strings.

### Pagination

All list tools support a `skip: int = 0` parameter for offset-based pagination. Use `skip` + `limit` together:

```
# Page 1: first 50 transactions
get_transactions(account_id, from_date, to_date, limit=50, skip=0)

# Page 2: next 50
get_transactions(account_id, from_date, to_date, limit=50, skip=50)
```

The page size cap is 200 records per call. If `count` in the response equals your `limit`, there may be more records — either paginate with `skip` or narrow your date range and filters.

### Do not infer IDs

IDs like `accountId`, `transactionId`, `securityId` are opaque strings from seed data. Do not construct them by pattern-matching or guessing. Always discover them from list/query results first.

---

## MCP Configuration (VS Code / Claude Desktop)

Register the server in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bank-ods": {
      "command": "python",
      "args": ["-m", "bank_ods.mcp"],
      "cwd": "C:/dev/clio-git/mongo-mcp-test",
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "bank_ods"
      }
    }
  }
}
```

The server name `bank-ods` in the config corresponds to `FastMCP("bank-ods")` in `server.py`. Tools appear in Claude Code as `mcp__bank-ods__<tool_name>`.

---

## Extending the Server

To add a new tool:

1. Add the service function to the appropriate `bank_ods/services/<domain>.py` as `async def`.
2. Add a one-line `@mcp.tool()` wrapper in `bank_ods/mcp/tools.py`.
3. Add a corresponding REST endpoint in `bank_ods/rest/routers/<domain>.py`.
4. Add a GraphQL resolver in `bank_ods/graphql/resolvers.py` and ensure the SDL includes the new query field.
5. Add service tests in `tests/test_services.py` and a parity assertion in `tests/test_parity.py`.

Do not add MongoDB query logic to any layer other than `bank_ods/services/*`. Do not add new collections without discussion (see CLAUDE.md constraints).
