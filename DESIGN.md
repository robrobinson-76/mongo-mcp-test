# Design — mongo-mcp-test

## Overview

A local prototype that puts a Python MCP server in front of a MongoDB database seeded with custodian-bank-style ODS data. The intent is to validate the MCP ↔ MongoDB pattern: can an LLM agent navigate operational banking data (transactions, positions, settlements) through well-designed tool calls?

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  VS Code + Claude Extension                                  │
│                                                             │
│   Claude Code ──── MCP tool calls ──────────────────────┐  │
└─────────────────────────────────────────────────────────│──┘
                                                          │
                                          stdio / HTTP SSE│
                                                          ▼
                                   ┌──────────────────────────┐
                                   │  Python MCP Server        │
                                   │  (fastmcp)                │
                                   │                           │
                                   │  tools/transactions.py    │
                                   │  tools/positions.py       │
                                   │  tools/settlements.py     │
                                   │  tools/balances.py        │
                                   │  tools/accounts.py        │
                                   │                           │
                                   │  db.py (pymongo client)   │
                                   └──────────────┬───────────┘
                                                  │
                                          pymongo │
                                                  ▼
                                   ┌──────────────────────────┐
                                   │  MongoDB (Docker)         │
                                   │  localhost:27017          │
                                   │  db: bank_ods             │
                                   │                           │
                                   │  accounts                 │
                                   │  securities               │
                                   │  transactions             │
                                   │  positions                │
                                   │  settlements              │
                                   │  cash_balances            │
                                   └──────────────────────────┘
```

---

## MongoDB Collection Schemas

All collections live in the `bank_ods` database. Field naming is camelCase. Dates are stored as MongoDB `Date` objects (use `datetime` in Python). Monetary amounts are stored as `Decimal128` or plain `float` (float is fine for this prototype). IDs are application-generated strings — no reliance on `_id` ObjectId for business keys.

### `accounts`

Models client accounts held at the custodian.

```json
{
  "_id": ObjectId,
  "accountId":       "ACC-000123",
  "accountName":     "Maple Pension Fund - Equity",
  "accountType":     "CUSTODY",          // CUSTODY | PROPRIETARY | OMNIBUS
  "clientId":        "CLT-000042",
  "clientName":      "Maple Pension Fund",
  "baseCurrency":    "CAD",
  "status":          "ACTIVE",           // ACTIVE | SUSPENDED | CLOSED
  "openDate":        ISODate("2018-03-01"),
  "closeDate":       null,
  "custodianBranch": "Toronto",
  "createdAt":       ISODate,
  "updatedAt":       ISODate
}
```

Indexes: `accountId` (unique), `clientId`, `status`.

---

### `securities`

Security master. Covers equities, government bonds, corporate bonds, and funds.

```json
{
  "_id": ObjectId,
  "securityId":    "SEC-000001",
  "isin":          "US0378331005",
  "cusip":         "037833100",
  "ticker":        "AAPL",
  "description":   "Apple Inc Common Stock",
  "assetClass":    "EQUITY",            // EQUITY | GOVT_BOND | CORP_BOND | FUND | CASH
  "subType":       "COMMON_STOCK",
  "currency":      "USD",
  "exchange":      "NASDAQ",
  "issuer":        "Apple Inc",
  "country":       "US",
  "maturityDate":  null,                // populated for bonds
  "couponRate":    null,                // populated for bonds
  "status":        "ACTIVE",           // ACTIVE | MATURED | DELISTED
  "createdAt":     ISODate,
  "updatedAt":     ISODate
}
```

Indexes: `securityId` (unique), `isin` (unique), `ticker`, `assetClass`.

---

### `transactions`

Trade and cash movement records. This is the highest-volume collection in a real ODS.

```json
{
  "_id": ObjectId,
  "transactionId":   "TXN-20240115-001234",
  "transactionType": "BUY",             // BUY | SELL | DEPOSIT | WITHDRAWAL | TRANSFER_IN | TRANSFER_OUT | DIVIDEND | FX
  "tradeDate":       ISODate("2024-01-15"),
  "settlementDate":  ISODate("2024-01-17"),
  "accountId":       "ACC-000123",
  "securityId":      "SEC-000001",      // null for pure cash transactions
  "quantity":        100.0,             // null for pure cash
  "price":           185.50,
  "currency":        "USD",
  "grossAmount":     18550.00,
  "fees":            25.00,
  "netAmount":       18575.00,          // grossAmount + fees (buy side)
  "fxRate":          1.3450,            // USD/CAD rate if applicable, else 1.0
  "counterpartyId":  "CPTY-GOLDM",
  "status":          "SETTLED",         // PENDING | MATCHED | SETTLED | FAILED | CANCELLED
  "settlementRef":   "STL-20240117-000789",
  "sourceSystem":    "ORDER_MGMT",
  "internalRef":     "ORD-2024-056789",
  "createdAt":       ISODate,
  "updatedAt":       ISODate
}
```

Indexes: `transactionId` (unique), `accountId + tradeDate`, `status`, `settlementDate`, `securityId`.

---

### `positions`

Point-in-time security holdings. A new document is written for each position snapshot (daily EOD) rather than updating in place — this preserves history.

```json
{
  "_id": ObjectId,
  "positionId":    "POS-ACC000123-SEC000001-20240115",
  "accountId":     "ACC-000123",
  "securityId":    "SEC-000001",
  "asOfDate":      ISODate("2024-01-15"),
  "quantity":      500.0,
  "currency":      "USD",
  "costBasis":     89750.00,
  "marketPrice":   185.50,
  "marketValue":   92750.00,
  "unrealizedPnL": 3000.00,
  "positionType":  "LONG",              // LONG | SHORT
  "snapshotType":  "EOD",              // EOD | INTRADAY | SETTLEMENT
  "createdAt":     ISODate,
  "updatedAt":     ISODate
}
```

Indexes: `accountId + securityId + asOfDate` (unique compound), `asOfDate`, `accountId`.

---

### `settlements`

Settlement instruction lifecycle. Each document tracks a settlement from instruction through completion or failure.

```json
{
  "_id": ObjectId,
  "settlementId":       "STL-20240117-000789",
  "transactionId":      "TXN-20240115-001234",
  "accountId":          "ACC-000123",
  "securityId":         "SEC-000001",
  "settlementDate":     ISODate("2024-01-17"),
  "deliveryType":       "DVP",            // DVP (delivery vs payment) | FOP (free of payment) | RVP | RFP
  "quantity":           100.0,
  "currency":           "USD",
  "settlementAmount":   18575.00,
  "counterpartyId":     "CPTY-GOLDM",
  "counterpartyAccount":"GB29NWBK60161331926819",
  "custodianAccount":   "CA99RBCC0000000123456",
  "status":             "SETTLED",        // PENDING | INSTRUCTED | MATCHED | SETTLED | FAILED | CANCELLED | RECYCLED
  "statusHistory": [
    { "status": "PENDING",     "timestamp": ISODate("2024-01-15T14:00:00Z") },
    { "status": "INSTRUCTED",  "timestamp": ISODate("2024-01-15T16:00:00Z") },
    { "status": "MATCHED",     "timestamp": ISODate("2024-01-16T09:00:00Z") },
    { "status": "SETTLED",     "timestamp": ISODate("2024-01-17T10:23:00Z") }
  ],
  "failReason":         null,             // populated if status = FAILED
  "csdRef":             "DTCC-2024-XYZ", // central securities depository ref
  "swiftRef":           "MT54X-REF",
  "createdAt":          ISODate,
  "updatedAt":          ISODate
}
```

Indexes: `settlementId` (unique), `transactionId`, `accountId + settlementDate`, `status`.

---

### `cash_balances`

Cash position per account per currency. One document per account/currency pair; overwritten on update.

```json
{
  "_id": ObjectId,
  "balanceId":    "BAL-ACC000123-USD-20240115",
  "accountId":    "ACC-000123",
  "currency":     "USD",
  "asOfDate":     ISODate("2024-01-15"),
  "openingBalance":  1250000.00,
  "credits":          18575.00,         // sum of inflows on asOfDate
  "debits":               0.00,         // sum of outflows on asOfDate
  "closingBalance":  1268575.00,
  "pendingCredits":      0.00,          // unsettled inflows
  "pendingDebits":   18575.00,          // unsettled outflows
  "projectedBalance": 1250000.00,       // closingBalance net of pending
  "snapshotType":   "EOD",
  "createdAt":     ISODate,
  "updatedAt":     ISODate
}
```

Indexes: `accountId + currency + asOfDate` (unique compound), `asOfDate`.

---

## Seed Data

`scripts/seed_data.py` uses `faker` to generate realistic-looking data. Target volumes:

| Collection | Documents |
|---|---|
| accounts | 20 |
| securities | 50 |
| transactions | 2 000 |
| positions | 1 000 |
| settlements | 1 800 |
| cash_balances | 400 |

Referential consistency: transactions reference real `accountId` and `securityId` values. Settlements reference real `transactionId` values. Positions and balances are date-ranged over the last 90 days.

---

## MCP Server Design

### Library: `fastmcp`

`fastmcp` wraps the MCP protocol and lets you define tools as decorated Python functions. It handles the JSON-RPC transport (stdio by default, HTTP SSE for remote).

```python
# server.py sketch
from fastmcp import FastMCP

mcp = FastMCP("bank-ods")

# tool modules self-register
from mcp_server.tools import transactions, positions, settlements, balances, accounts

if __name__ == "__main__":
    mcp.run()  # stdio by default
```

---

### Tool inventory

#### `accounts` module

| Tool | Signature | Description |
|---|---|---|
| `get_account` | `account_id: str` | Fetch a single account by ID |
| `list_accounts` | `client_id: str = None, status: str = None, limit: int = 20` | List accounts with optional filters |

#### `transactions` module

| Tool | Signature | Description |
|---|---|---|
| `get_transaction` | `transaction_id: str` | Fetch a single transaction |
| `get_transactions` | `account_id: str, from_date: str, to_date: str, status: str = None, transaction_type: str = None, limit: int = 50` | Filtered transaction query |
| `get_transaction_summary` | `account_id: str, from_date: str, to_date: str` | Aggregate count/value by type and status |

#### `positions` module

| Tool | Signature | Description |
|---|---|---|
| `get_position` | `account_id: str, security_id: str, as_of_date: str` | Single holding as-of a date |
| `get_positions` | `account_id: str, as_of_date: str` | All holdings for an account on a date |
| `get_position_history` | `account_id: str, security_id: str, from_date: str, to_date: str` | EOD history for a holding |

#### `settlements` module

| Tool | Signature | Description |
|---|---|---|
| `get_settlement` | `settlement_id: str` | Fetch a settlement by ID |
| `get_settlement_status` | `transaction_id: str` | Look up settlement linked to a transaction |
| `get_settlements` | `account_id: str, settlement_date: str, status: str = None` | Query settlements by date/status |
| `get_settlement_fails` | `from_date: str, to_date: str, account_id: str = None` | Find all FAILED settlements in a window |

#### `balances` module

| Tool | Signature | Description |
|---|---|---|
| `get_cash_balance` | `account_id: str, currency: str, as_of_date: str` | Single account/currency balance |
| `get_cash_balances` | `account_id: str, as_of_date: str` | All currency balances for an account |
| `get_projected_balance` | `account_id: str, currency: str, as_of_date: str` | Projected balance net of pending |

---

### Tool design rules

1. **Date inputs are ISO 8601 strings** (`"2024-01-15"`). The tool converts to `datetime` before querying.
2. **All tools return plain dicts or lists of dicts** — no ObjectId, no datetime objects. Serialize to strings before returning.
3. **Limit all list tools** — default to 50 records, max 200. Never return unbounded result sets.
4. **Return empty list, not None** for zero-result queries.
5. **Include a `count` key** in list responses alongside the `data` array.
6. **Error handling** — catch `pymongo.errors` and return `{"error": "...", "code": "..."}` rather than raising.

---

## VS Code Integration

### Transport

For local VS Code use, run the MCP server in **stdio** mode. Claude Code in VS Code launches it as a subprocess and communicates over stdin/stdout.

### Registration

Edit (or create) `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bank-ods": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\dev\\clio-git\\mongo-mcp-test",
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "bank_ods"
      }
    }
  }
}
```

If using `uv`:
```json
{
  "mcpServers": {
    "bank-ods": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "C:\\dev\\clio-git\\mongo-mcp-test",
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "bank_ods"
      }
    }
  }
}
```

Restart VS Code after editing. Verify the MCP server appears in the Claude extension's server list.

---

## Docker Compose (MongoDB)

```yaml
# docker-compose.yml
services:
  mongodb:
    image: mongo:7.0
    container_name: bank-ods-mongo
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: bank_ods

volumes:
  mongo_data:
```

No auth — local prototype only.

---

## Key Dependencies

```toml
# pyproject.toml
[project]
name = "bank-ods-mcp"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=0.4",
    "pymongo>=4.6",
    "python-dotenv>=1.0",
    "faker>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
]
```

---

## Design Decisions

**Why `fastmcp` over the raw `mcp` SDK?** fastmcp removes boilerplate (JSON schema generation from type hints, transport setup) and is well-maintained. The raw SDK is fine but adds noise for a prototype.

**Why sync `pymongo` not `motor` (async)?** fastmcp runs tools synchronously by default. Motor would require an event loop and async tool functions — more complexity for no gain here.

**Why flat documents, not nested?** Simpler queries, simpler tool responses. In a real ODS the document model would reflect the natural entity shape more aggressively; here we prioritise queryability from an LLM tool perspective.

**Why EOD snapshots for positions/balances?** Avoids update-in-place semantics and gives the LLM tools a simple `asOfDate` filter to reason about history.

**Why no authentication on MongoDB?** Local prototype, Docker only. Adding auth (SCRAM-SHA-256) is a one-line change to the URI.
