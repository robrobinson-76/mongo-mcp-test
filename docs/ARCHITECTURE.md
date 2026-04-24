# Architecture — Bank ODS Prototype

## Purpose

A local prototype demonstrating how a Python MCP server can expose a MongoDB-backed custodian bank ODS to an LLM via structured, tool-driven access. The same data layer also serves a REST API and a GraphQL API, all sharing a single async service core.

This is not a production system. The goal is to validate the MCP ↔ MongoDB interaction pattern and explore what useful tooling looks like for an AI agent querying operational bank data.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       Transport Layer                            │
│                                                                  │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│   │  MCP Server  │   │  REST API    │   │  GraphQL API     │   │
│   │  (fastmcp)   │   │  (FastAPI)   │   │  (Ariadne)       │   │
│   │  stdio       │   │  port 8000   │   │  port 8001       │   │
│   └──────┬───────┘   └──────┬───────┘   └────────┬─────────┘   │
└──────────┼─────────────────┼───────────────────┼──────────────┘
           │                 │                   │
           └─────────────────┴───────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Service Layer  │
                    │  bank_ods.      │
                    │  services.*     │
                    │  (15 async fns) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  DB Layer       │
                    │  motor (async)  │
                    │  + index mgmt   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   MongoDB 7.0   │
                    │   (Docker)      │
                    │   6 collections │
                    └─────────────────┘
```

**Core invariant:** MongoDB is only touched through `bank_ods.services.*`. No transport layer contains query logic.

---

## Tech Stack

| Layer | Library | Version |
|---|---|---|
| MCP server | fastmcp | ≥0.4 |
| REST framework | FastAPI + uvicorn | ≥0.110 / ≥0.29 |
| GraphQL | Ariadne | ≥0.23 |
| MongoDB driver | motor (async) | ≥3.4 |
| Data models | Pydantic v2 | via fastmcp/fastapi |
| Seed data | pymongo + faker | ≥4.6 / ≥24.0 |
| HTTP test client | httpx | ≥0.27 |
| Package manager | uv (preferred) | — |
| Database | MongoDB | 7.0 (Docker) |
| Runtime | Python | ≥3.11 |

---

## Project Layout

```
mongo-mcp-test/
├── docs/
│   ├── ARCHITECTURE.md         ← this file
│   ├── DESIGN.md               ← schema and detailed design decisions (reference, do not modify)
│   ├── PLAN.md                 ← original phased implementation plan (reference, do not modify)
│   └── PLAN-multilayer.md      ← unified MCP/REST/GraphQL plan (reference, do not modify)
│
├── docker-compose.yml           ← MongoDB 7.0, port 27017, no auth
│
├── src/
│   └── bank_ods/
│       ├── __init__.py
│       ├── config.py            ← MONGODB_URI, MONGODB_DB from env
│       │
│       ├── models/              ← Pydantic v2 entity models (single source of truth)
│       │   ├── base.py          ← BankDocument, IndexSpec, serialize_doc
│       │   ├── account.py
│       │   ├── security.py
│       │   ├── transaction.py
│       │   ├── position.py
│       │   ├── settlement.py
│       │   ├── cash_balance.py
│       │   └── registry.py      ← ENTITIES list — used by index creation + SDL generation
│       │
│       ├── db/
│       │   ├── client.py        ← Motor singleton: get_client(), get_db(), get_collection()
│       │   └── indexes.py       ← ensure_indexes() — idempotent, called on startup
│       │
│       ├── services/            ← 15 async business logic functions (only MongoDB access here)
│       │   ├── _common.py       ← parse_date(), clamp_limit(), serialize_doc()
│       │   ├── accounts.py      ← get_account, list_accounts
│       │   ├── transactions.py  ← get_transaction, get_transactions, get_transaction_summary
│       │   ├── positions.py     ← get_position, get_positions, get_position_history
│       │   ├── settlements.py   ← get_settlement, get_settlement_status, get_settlements, get_settlement_fails
│       │   └── balances.py      ← get_cash_balance, get_cash_balances, get_projected_balance
│       │
│       ├── mcp/
│       │   ├── server.py        ← FastMCP("bank-ods"), lifespan → ensure_indexes()
│       │   └── tools.py         ← 15 @mcp.tool() wrappers; each is a one-liner delegating to services
│       │
│       ├── rest/
│       │   ├── app.py           ← FastAPI app, router inclusion, lifespan → ensure_indexes()
│       │   └── routers/
│       │       ├── accounts.py
│       │       ├── transactions.py
│       │       ├── positions.py
│       │       ├── settlements.py
│       │       └── balances.py
│       │
│       └── graphql/
│           ├── app.py           ← Ariadne + FastAPI; DateTime scalar; /graphql mount
│           ├── sdl.py           ← Dynamic SDL generation from ENTITIES registry
│           └── resolvers.py     ← 15 QueryType field resolvers → services
│
├── scripts/
│   └── seed_data.py             ← Loads ~5,200 realistic documents using faker (seed=42)
│
├── tests/
│   ├── conftest.py              ← Session-scoped fixtures: db, first_account, rest_client, gql_client
│   ├── test_services.py         ← Direct service function tests (happy path + not-found + filters)
│   ├── test_mcp.py              ← MCP tool tests
│   ├── test_rest.py             ← REST endpoint tests (status codes, response shapes)
│   ├── test_graphql.py          ← GraphQL query validation
│   └── test_parity.py           ← Cross-layer equivalence: MCP == REST == GraphQL == service
│
├── pyproject.toml
├── .env.example
└── CLAUDE.md
```

---

## Domain Model

Six MongoDB collections model a simplified custodian bank ODS. All field names are camelCase. Dates are stored as MongoDB `Date` objects and serialized to ISO 8601 strings at the service boundary.

### Collections

#### `accounts` — Account master

| Field | Type | Notes |
|---|---|---|
| accountId | str | Unique |
| accountName | str | |
| accountType | CUSTODY \| PROPRIETARY \| OMNIBUS | |
| clientId | str | |
| clientName | str | |
| baseCurrency | str | ISO 4217 |
| status | ACTIVE \| SUSPENDED \| CLOSED | |
| openDate | datetime | |
| closeDate | datetime? | |
| custodianBranch | str | |
| createdAt / updatedAt | datetime | |

Indexes: `accountId` (unique), `clientId`, `status`

#### `securities` — Security master

| Field | Type | Notes |
|---|---|---|
| securityId | str | Unique |
| isin | str? | Unique, sparse |
| cusip | str? | |
| ticker | str? | |
| description | str | |
| assetClass | EQUITY \| GOVT_BOND \| CORP_BOND \| FUND \| CASH | |
| subType | str | e.g., COMMON_STOCK, ETF, FIXED_RATE |
| currency | str | |
| exchange | str? | |
| issuer | str | |
| country | str | |
| maturityDate | datetime? | Bonds only |
| couponRate | float? | Bonds only |
| status | ACTIVE \| MATURED \| DELISTED | |

Indexes: `securityId` (unique), `isin` (unique, sparse), `ticker`, `assetClass`

#### `transactions` — Trade and cash movements (highest volume)

| Field | Type | Notes |
|---|---|---|
| transactionId | str | Unique |
| transactionType | BUY \| SELL \| DEPOSIT \| WITHDRAWAL \| TRANSFER_IN \| TRANSFER_OUT \| DIVIDEND \| FX | |
| tradeDate | datetime | |
| settlementDate | datetime | T+2 for equities |
| accountId | str | |
| securityId | str? | Null for cash transactions |
| quantity | float? | |
| price | float? | |
| currency | str | |
| grossAmount | float | |
| fees | float | |
| netAmount | float | grossAmount ± fees |
| fxRate | float | |
| counterpartyId | str | |
| status | PENDING \| MATCHED \| SETTLED \| FAILED \| CANCELLED | |
| settlementRef | str? | |
| sourceSystem | str | |
| internalRef | str | |

Indexes: `transactionId` (unique), `(accountId, tradeDate)` desc, `status`, `settlementDate`, `securityId`

#### `positions` — EOD security holdings (append-only snapshots)

| Field | Type | Notes |
|---|---|---|
| positionId | str | |
| accountId | str | |
| securityId | str | |
| asOfDate | datetime | EOD date |
| quantity | float | |
| currency | str | |
| costBasis | float | |
| marketPrice | float | |
| marketValue | float | quantity × marketPrice |
| unrealizedPnL | float | marketValue − costBasis |
| positionType | LONG \| SHORT | |
| snapshotType | EOD \| INTRADAY \| SETTLEMENT | |

Indexes: `(accountId, securityId, asOfDate)` compound unique, `asOfDate`, `accountId`

#### `settlements` — Settlement instruction lifecycle

| Field | Type | Notes |
|---|---|---|
| settlementId | str | Unique |
| transactionId | str | FK to transactions |
| accountId | str | |
| securityId | str? | |
| settlementDate | datetime | |
| deliveryType | DVP \| FOP \| RVP \| RFP | |
| quantity | float? | |
| currency | str | |
| settlementAmount | float | |
| counterpartyId | str | |
| counterpartyAccount | str | |
| custodianAccount | str | |
| status | PENDING \| INSTRUCTED \| MATCHED \| SETTLED \| FAILED \| CANCELLED \| RECYCLED | |
| statusHistory | StatusHistoryEntry[] | Embedded lifecycle progression |
| failReason | str? | Set when status = FAILED |
| csdRef | str? | CSD reference |
| swiftRef | str? | SWIFT reference |

`StatusHistoryEntry`: `{ status: str, timestamp: datetime }`

Indexes: `settlementId` (unique), `transactionId`, `(accountId, settlementDate)`, `status`

#### `cash_balances` — Daily cash positions (append-only snapshots)

| Field | Type | Notes |
|---|---|---|
| balanceId | str | |
| accountId | str | |
| currency | str | ISO 4217 |
| asOfDate | datetime | EOD date |
| openingBalance | float | |
| credits | float | |
| debits | float | |
| closingBalance | float | openingBalance + credits − debits |
| pendingCredits | float | Unsettled inflows |
| pendingDebits | float | Unsettled outflows |
| projectedBalance | float | closingBalance + pendingCredits − pendingDebits |
| snapshotType | EOD \| INTRADAY | |

Indexes: `(accountId, currency, asOfDate)` compound unique, `asOfDate`

### Temporal Data Pattern

Positions and cash balances are **append-only snapshots**, not in-place updates. Each EOD creates a new document. This preserves history and makes time-range queries straightforward. Queries always filter by `asOfDate` to retrieve a specific snapshot.

---

## Service Layer — Function Reference

All service functions are `async def`. All accept and return plain Python dicts (JSON-safe after `serialize_doc()`). Dates are passed as ISO 8601 strings (`"YYYY-MM-DD"`).

### Error Envelope

Every service function returns one of:
- `{...data fields...}` — success (single item)
- `{"count": N, "data": [...]}` — success (list)
- `{"error": "...", "code": "NOT_FOUND"}` — item not found
- `{"error": "...", "code": "MONGO_ERROR"}` — database error

Functions never raise exceptions to callers.

### Accounts

```python
get_account(account_id: str) → dict
list_accounts(client_id: str | None, status: str | None, limit: int = 20) → dict
```

### Transactions

```python
get_transaction(transaction_id: str) → dict
get_transactions(account_id, from_date, to_date, status=None, transaction_type=None, limit=50) → dict
get_transaction_summary(account_id, from_date, to_date) → dict
# summary returns: {count, data: [{transactionType, status, count, totalNetAmount}]}
```

### Positions

```python
get_position(account_id, security_id, as_of_date) → dict
get_positions(account_id, as_of_date) → dict
get_position_history(account_id, security_id, from_date, to_date) → dict
# history is sorted ascending by asOfDate
```

### Settlements

```python
get_settlement(settlement_id) → dict
get_settlement_status(transaction_id) → dict   # lookup by transaction, not settlement ID
get_settlements(account_id, settlement_date, status=None) → dict
get_settlement_fails(from_date, to_date, account_id=None) → dict
```

### Balances

```python
get_cash_balance(account_id, currency, as_of_date) → dict
get_cash_balances(account_id, as_of_date) → dict
get_projected_balance(account_id, currency, as_of_date) → dict
# projected returns subset: {accountId, currency, asOfDate, closingBalance, pendingCredits, pendingDebits, projectedBalance}
```

### Limit Enforcement

All list operations clamp results to `[1, 200]` via `clamp_limit()`. Default limits: accounts 20, transactions 50, others 200 (hard max).

---

## Transport Layers

### MCP — `bank_ods.mcp`

- Server ID: `bank-ods`
- Transport: stdio (Claude Code / VS Code extension)
- Entry point: `python -m bank_ods.mcp`
- Tools: 15 `@mcp.tool()` functions in `tools.py`, each a single-line delegate to services
- Startup: `ensure_indexes()` via lifespan context manager
- Tool docstrings are LLM-visible tool descriptions

### REST — `bank_ods.rest`

- Framework: FastAPI
- Entry point: `uvicorn bank_ods.rest:app --port 8000`
- Docs: `http://localhost:8000/docs` (Swagger UI)
- 5 routers: accounts, transactions, positions, settlements, balances
- ~18 GET endpoints total
- Startup: `ensure_indexes()` via lifespan

**Endpoint summary:**

| Prefix | Endpoints |
|---|---|
| `/accounts` | GET `/{id}`, GET `?client_id&status&limit` |
| `/transactions` | GET `/{id}`, GET `?account_id&from_date&to_date&...`, GET `/summary?...` |
| `/positions` | GET `/{account_id}?as_of_date`, GET `/{account_id}/{security_id}?as_of_date`, GET `/{account_id}/{security_id}/history?from_date&to_date` |
| `/settlements` | GET `/{id}`, GET `/by-transaction/{txn_id}`, GET `?account_id&settlement_date&status`, GET `/fails?from_date&to_date&account_id` |
| `/balances` | GET `/{account_id}?as_of_date`, GET `/{account_id}/{currency}?as_of_date`, GET `/{account_id}/{currency}/projected?as_of_date` |

### GraphQL — `bank_ods.graphql`

- Framework: Ariadne (ASGI)
- Entry point: `uvicorn bank_ods.graphql:app --port 8001`
- Endpoint: `POST http://localhost:8001/graphql`
- SDL generated at runtime from the ENTITIES registry by `sdl.py`
- 15 query fields matching service function names
- DateTime custom scalar serializes datetime to ISO string
- Startup: `ensure_indexes()` via lifespan

GraphQL parameter names use camelCase (`fromDate`, `asOfDate`); resolvers map these to service snake_case parameters.

---

## Data Models — Design Principles

### `BankDocument` Base Class

All six entity models inherit from `BankDocument`:

```python
class BankDocument(BaseModel):
    COLLECTION: ClassVar[str]          # MongoDB collection name
    INDEXES: ClassVar[list[IndexSpec]] # Index specifications

    @classmethod
    def from_mongo(cls, doc: dict) -> "BankDocument": ...
    def to_response(self) -> dict: ...  # JSON-safe dict
```

`IndexSpec = tuple[str | list[tuple[str, int]], dict[str, Any]]`

### Entity Registry

`bank_ods.models.registry.ENTITIES` is the single list of all six model classes. It drives:
1. Index creation (`db/indexes.py`)
2. GraphQL SDL generation (`graphql/sdl.py`)

Adding a new entity requires only adding it to this list.

### SDL Generation

`graphql/sdl.py` introspects Pydantic field types and generates the full GraphQL SDL at startup. Python → GraphQL type mapping:

| Python | GraphQL |
|---|---|
| str | String! |
| int | Int! |
| float | Float! |
| bool | Boolean! |
| datetime | DateTime! |
| Optional[T] | T (nullable) |
| list[T] | [T!]! |
| Literal[...] | String! |

---

## Index Strategy

| Collection | Indexes |
|---|---|
| accounts | accountId (unique), clientId, status |
| securities | securityId (unique), isin (unique sparse), ticker, assetClass |
| transactions | transactionId (unique), (accountId, tradeDate desc), status, settlementDate, securityId |
| positions | (accountId, securityId, asOfDate) compound unique, asOfDate, accountId |
| settlements | settlementId (unique), transactionId, (accountId, settlementDate), status |
| cash_balances | (accountId, currency, asOfDate) compound unique, asOfDate |

The compound unique index on `positions` and `cash_balances` enforces that only one snapshot exists per (account, security/currency, date).

---

## Testing Strategy

Tests require a running MongoDB with seeded data (`python scripts/seed_data.py`).

| File | What it tests |
|---|---|
| `test_services.py` | Service functions directly — happy paths, NOT_FOUND, filters, aggregation |
| `test_rest.py` | REST endpoint status codes and response shapes via ASGI transport |
| `test_graphql.py` | GraphQL query structure and field presence |
| `test_parity.py` | **Cross-layer equivalence** — asserts MCP == REST == GraphQL == service for every operation |
| `test_mcp.py` | MCP tool invocation |

### Parity Test Pattern

```python
async def test_parity_get_account(rest_client, gql_client, first_account):
    account_id = first_account["accountId"]
    service = await svc_accounts.get_account(account_id)
    rest    = (await rest_client.get(f"/accounts/{account_id}")).json()
    gql     = (await gql_query(gql_client, f'{{ get_account(accountId: "{account_id}") {{ accountId }} }}'))["data"]["get_account"]
    assert service["accountId"] == rest["accountId"] == gql["accountId"]
```

The parity harness is the primary contract enforcement mechanism. All three transport layers must return identical data for identical inputs.

### Session-Scoped Fixtures

`conftest.py` establishes session-scoped fixtures:
- `db` — Motor database handle; triggers `ensure_indexes()`
- `first_account` — fetched from seeded DB; used as known-good test anchor
- `first_balance`, `first_settled_txn` — similar
- `rest_client` — `httpx.AsyncClient` with ASGI transport (no network)
- `gql_client` — same for GraphQL app

Tests assume seeded data exists. If the DB is empty, fixtures assert and fail early with a clear message.

---

## Seed Data

`scripts/seed_data.py` uses sync `pymongo` with `faker` (seed=42 for reproducibility).

| Collection | Count | Notes |
|---|---|---|
| accounts | 20 | 10 clients; CUSTODY/PROPRIETARY/OMNIBUS mix; weighted ACTIVE |
| securities | 50 | 30 equities, 15 bonds, 5 ETFs; real-ish tickers |
| transactions | 2,000 | Last 90 days; 70% BUY/SELL; 80% SETTLED |
| settlements | 1,800 | One per trade transaction; full statusHistory |
| positions | 1,000 | EOD snapshots; account × security × date |
| cash_balances | 400 | EOD snapshots; account × currency (CAD/USD) × 10 days |

Settlement `statusHistory` tracks lifecycle progression: `PENDING → INSTRUCTED → MATCHED → SETTLED/FAILED`.

---

## Environment Variables

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=bank_ods
MCP_SERVER_HOST=localhost     # documentation only; not read by server code
MCP_SERVER_PORT=8000          # documentation only; not read by server code
```

Copy `.env.example` to `.env` before running.

---

## Running Locally

```bash
# 1. Start MongoDB
docker compose up -d

# 2. Install dependencies
uv sync        # or: pip install -e ".[dev]"

# 3. Seed sample data
python scripts/seed_data.py

# 4. Run full test suite
pytest tests/ -v

# 5a. MCP server (stdio — for VS Code Claude extension)
python -m bank_ods.mcp

# 5b. REST API
uvicorn bank_ods.rest:app --port 8000

# 5c. GraphQL API
uvicorn bank_ods.graphql:app --port 8001
```

---

## Design Decisions

**Single service layer.** All transport layers delegate to `bank_ods.services.*`. No transport contains query logic. This makes each transport interchangeable and parity-testable.

**Models as schema source of truth.** Pydantic models define fields and types once. The ENTITIES registry propagates this to index creation and SDL generation, preventing drift.

**Append-only snapshots for temporal data.** Positions and balances write new documents per date rather than updating in place. This preserves full history without a change-log pattern and simplifies range queries.

**Error envelope, never raise.** Service functions return `{error, code}` dicts on failure. Transports pass through or wrap. This keeps error handling explicit and avoids exception leakage across layer boundaries.

**ISO 8601 at boundaries.** External APIs always send and receive `"YYYY-MM-DD"` strings. Services parse to `datetime` internally. Serialization back to strings happens in `serialize_doc()` at the return boundary.

**Limit enforcement at services.** All list operations clamp to `[1, 200]` inside the service. Transport layers pass `limit` through without re-validating, trusting the service invariant.

**SDL at runtime.** The GraphQL schema is generated from Pydantic models at process startup, not from a static `.graphql` file. This ensures the schema is always consistent with the Python models.

**No MongoDB auth.** This is a local-only prototype. Docker Compose runs MongoDB without authentication. Do not add auth — it is unnecessary and would complicate local setup for no benefit.

---

## Constraints

- Do not modify `docs/DESIGN.md`, `docs/PLAN.md`, or `docs/PLAN-multilayer.md` — these are reference documents.
- Do not add collections beyond the six defined without discussion.
- Do not add MongoDB authentication.
- All new data access must go through `bank_ods.services.*`.
