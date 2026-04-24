# Architecture — Bank ODS Prototype

## Purpose

A local prototype demonstrating how a Python MCP server can expose a MongoDB-backed custodian bank ODS to an LLM via structured, tool-driven access. The same data layer also serves a REST API and a GraphQL API, all sharing a single async service core.

This is not a production system. The goal is to validate the MCP ↔ MongoDB interaction pattern and explore what useful tooling looks like for an AI agent querying operational bank data.

The codebase has been hardened for Kubernetes deployment at 40-50K GraphQL requests/day with EOD burst peaks (~10 req/sec). See the [K8s Deployment](#kubernetes-deployment) section.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       Transport Layer                            │
│                                                                  │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│   │  MCP Server  │   │  REST API    │   │  GraphQL API     │   │
│   │  (fastmcp)   │   │  (FastAPI)   │   │  (Ariadne)       │   │
│   │  stdio/sse   │   │  port 8000   │   │  port 8001       │   │
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
                    │   (Docker/K8s)  │
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
│   ├── ARCHITECTURE.md             ← this file
│   ├── AGENTS.md                   ← MCP tool reference for AI agents
│   ├── PLAN.md                     ← original phased implementation plan (reference)
│   ├── PLAN-multilayer.md          ← unified MCP/REST/GraphQL plan (reference)
│   └── PLAN-k8s-scalability.md    ← K8s scalability implementation plan
│
├── Dockerfile.rest                 ← multi-stage build; uvicorn on :8000
├── Dockerfile.graphql              ← multi-stage build; uvicorn on :8001
├── Dockerfile.mcp                  ← multi-stage build; stdio or sse via MCP_TRANSPORT
├── .dockerignore
├── docker-compose.yml              ← MongoDB + REST + GraphQL services
│
├── k8s/
│   ├── configmap.yaml              ← shared env config + MongoDB URI secret
│   ├── rest-deployment.yaml        ← 2 replicas, /health probes
│   ├── rest-service.yaml           ← ClusterIP
│   ├── graphql-deployment.yaml     ← 2 replicas baseline, /health probes
│   ├── graphql-service.yaml        ← ClusterIP
│   ├── graphql-hpa.yaml            ← HPA: 2→8 replicas at 60% CPU
│   ├── mcp-deployment.yaml         ← 1 replica (stdio default; sse for chatbot)
│   └── mcp-service.yaml            ← ClusterIP (used with sse transport only)
│
├── src/
│   └── bank_ods/
│       ├── __init__.py
│       ├── config.py               ← MONGODB_URI, MONGODB_DB, DEBUG, LOG_LEVEL, MONGO_TIMEOUT_MS
│       ├── logging_config.py       ← JSON formatter, configure_logging(), RequestLoggingMiddleware
│       │
│       ├── models/                 ← Pydantic v2 entity models (single source of truth)
│       │   ├── base.py             ← BankDocument, IndexSpec, serialize_doc
│       │   ├── account.py
│       │   ├── security.py
│       │   ├── transaction.py
│       │   ├── position.py
│       │   ├── settlement.py
│       │   ├── cash_balance.py
│       │   └── registry.py         ← ENTITIES list — drives index creation + SDL generation
│       │
│       ├── db/
│       │   ├── client.py           ← Motor singleton with connection timeouts
│       │   └── indexes.py          ← ensure_indexes() — idempotent, called on startup
│       │
│       ├── services/               ← 15 async business logic functions (only MongoDB access here)
│       │   ├── _common.py          ← parse_date(), clamp_limit(), clamp_skip(), serialize_doc()
│       │   ├── accounts.py         ← get_account, list_accounts
│       │   ├── transactions.py     ← get_transaction, get_transactions, get_transaction_summary
│       │   ├── positions.py        ← get_position, get_positions, get_position_history
│       │   ├── settlements.py      ← get_settlement, get_settlement_status, get_settlements, get_settlement_fails
│       │   └── balances.py         ← get_cash_balance, get_cash_balances, get_projected_balance
│       │
│       ├── mcp/
│       │   ├── server.py           ← FastMCP("bank-ods"), lifespan → ensure_indexes()
│       │   ├── tools.py            ← 15 @mcp.tool() wrappers; each delegates to services
│       │   └── __main__.py         ← reads MCP_TRANSPORT env var; mcp.run(transport=...)
│       │
│       ├── rest/
│       │   ├── app.py              ← FastAPI app, /health, RequestLoggingMiddleware, lifespan
│       │   ├── errors.py           ← check() — maps service error envelopes to HTTP 404/500
│       │   └── routers/
│       │       ├── accounts.py
│       │       ├── transactions.py
│       │       ├── positions.py
│       │       ├── settlements.py
│       │       └── balances.py
│       │
│       └── graphql/
│           ├── app.py              ← Ariadne + FastAPI; /health; debug from env; logging middleware
│           ├── sdl.py              ← Dynamic SDL generation from ENTITIES registry
│           └── resolvers.py        ← 15 QueryType field resolvers → services
│
├── scripts/
│   └── seed_data.py                ← Loads ~5,200 realistic documents using faker (seed=42)
│
├── tests/
│   ├── conftest.py                 ← Session-scoped fixtures: db, first_account, rest_client, gql_client
│   ├── test_services.py            ← Direct service function tests (happy path, NOT_FOUND, filters, pagination)
│   ├── test_rest.py                ← REST endpoint tests (status codes, response shapes, health, skip)
│   ├── test_graphql.py             ← GraphQL query validation (health, skip)
│   └── test_parity.py              ← Cross-layer equivalence: REST == GraphQL == service (including skip)
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

```json
{
  "accountId":       "ACC-000123",
  "accountName":     "Maple Pension Fund - Equity",
  "accountType":     "CUSTODY",
  "clientId":        "CLT-000042",
  "clientName":      "Maple Pension Fund",
  "baseCurrency":    "CAD",
  "status":          "ACTIVE",
  "openDate":        "2018-03-01T00:00:00",
  "closeDate":       null,
  "custodianBranch": "Toronto",
  "createdAt":       "...",
  "updatedAt":       "..."
}
```

`accountType`: CUSTODY | PROPRIETARY | OMNIBUS  
`status`: ACTIVE | SUSPENDED | CLOSED  
Indexes: `accountId` (unique), `clientId`, `status`

#### `securities` — Security master

```json
{
  "securityId":  "SEC-000001",
  "isin":        "US0378331005",
  "cusip":       "037833100",
  "ticker":      "AAPL",
  "description": "Apple Inc Common Stock",
  "assetClass":  "EQUITY",
  "subType":     "COMMON_STOCK",
  "currency":    "USD",
  "exchange":    "NASDAQ",
  "issuer":      "Apple Inc",
  "country":     "US",
  "maturityDate": null,
  "couponRate":   null,
  "status":      "ACTIVE",
  "createdAt":   "...",
  "updatedAt":   "..."
}
```

`assetClass`: EQUITY | GOVT_BOND | CORP_BOND | FUND | CASH  
`status`: ACTIVE | MATURED | DELISTED  
Indexes: `securityId` (unique), `isin` (unique, sparse), `ticker`, `assetClass`

#### `transactions` — Trade and cash movements (highest volume)

```json
{
  "transactionId":   "TXN-20240115-001234",
  "transactionType": "BUY",
  "tradeDate":       "2024-01-15T00:00:00",
  "settlementDate":  "2024-01-17T00:00:00",
  "accountId":       "ACC-000123",
  "securityId":      "SEC-000001",
  "quantity":        100.0,
  "price":           185.50,
  "currency":        "USD",
  "grossAmount":     18550.00,
  "fees":            25.00,
  "netAmount":       18575.00,
  "fxRate":          1.3450,
  "counterpartyId":  "CPTY-GOLDM",
  "status":          "SETTLED",
  "settlementRef":   "STL-20240117-000789",
  "sourceSystem":    "ORDER_MGMT",
  "internalRef":     "ORD-2024-056789",
  "createdAt":       "...",
  "updatedAt":       "..."
}
```

`transactionType`: BUY | SELL | DEPOSIT | WITHDRAWAL | TRANSFER_IN | TRANSFER_OUT | DIVIDEND | FX  
`status`: PENDING | MATCHED | SETTLED | FAILED | CANCELLED  
Indexes: `transactionId` (unique), `(accountId, tradeDate)` desc, `status`, `settlementDate`, `securityId`

#### `positions` — EOD security holdings (append-only snapshots)

```json
{
  "positionId":    "POS-ACC000123-SEC000001-20240115",
  "accountId":     "ACC-000123",
  "securityId":    "SEC-000001",
  "asOfDate":      "2024-01-15T00:00:00",
  "quantity":      500.0,
  "currency":      "USD",
  "costBasis":     89750.00,
  "marketPrice":   185.50,
  "marketValue":   92750.00,
  "unrealizedPnL": 3000.00,
  "positionType":  "LONG",
  "snapshotType":  "EOD",
  "createdAt":     "...",
  "updatedAt":     "..."
}
```

`positionType`: LONG | SHORT  
`snapshotType`: EOD | INTRADAY | SETTLEMENT  
Indexes: `(accountId, securityId, asOfDate)` compound unique, `asOfDate`, `accountId`

#### `settlements` — Settlement instruction lifecycle

```json
{
  "settlementId":       "STL-20240117-000789",
  "transactionId":      "TXN-20240115-001234",
  "accountId":          "ACC-000123",
  "securityId":         "SEC-000001",
  "settlementDate":     "2024-01-17T00:00:00",
  "deliveryType":       "DVP",
  "quantity":           100.0,
  "currency":           "USD",
  "settlementAmount":   18575.00,
  "counterpartyId":     "CPTY-GOLDM",
  "counterpartyAccount":"GB29NWBK60161331926819",
  "custodianAccount":   "CA99RBCC0000000123456",
  "status":             "SETTLED",
  "statusHistory": [
    { "status": "PENDING",    "timestamp": "2024-01-15T14:00:00Z" },
    { "status": "INSTRUCTED", "timestamp": "2024-01-15T16:00:00Z" },
    { "status": "MATCHED",    "timestamp": "2024-01-16T09:00:00Z" },
    { "status": "SETTLED",    "timestamp": "2024-01-17T10:23:00Z" }
  ],
  "failReason": null,
  "csdRef":     "DTCC-2024-XYZ",
  "swiftRef":   "MT54X-REF",
  "createdAt":  "...",
  "updatedAt":  "..."
}
```

`deliveryType`: DVP | FOP | RVP | RFP  
`status`: PENDING | INSTRUCTED | MATCHED | SETTLED | FAILED | CANCELLED | RECYCLED  
Indexes: `settlementId` (unique), `transactionId`, `(accountId, settlementDate)`, `status`

#### `cash_balances` — Daily cash positions (append-only snapshots)

```json
{
  "balanceId":       "BAL-ACC000123-USD-20240115",
  "accountId":       "ACC-000123",
  "currency":        "USD",
  "asOfDate":        "2024-01-15T00:00:00",
  "openingBalance":  1250000.00,
  "credits":           18575.00,
  "debits":                0.00,
  "closingBalance":  1268575.00,
  "pendingCredits":      0.00,
  "pendingDebits":   18575.00,
  "projectedBalance": 1250000.00,
  "snapshotType":    "EOD",
  "createdAt":       "...",
  "updatedAt":       "..."
}
```

`snapshotType`: EOD | INTRADAY  
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

Functions never raise exceptions to callers. Transport layers translate these envelopes to appropriate protocol-level errors (HTTP 404/500 for REST; GraphQL resolver null-propagation).

### Accounts

```python
get_account(account_id: str) → dict
list_accounts(client_id=None, status=None, limit=20, skip=0) → dict
```

### Transactions

```python
get_transaction(transaction_id: str) → dict
get_transactions(account_id, from_date, to_date, status=None, transaction_type=None, limit=50, skip=0) → dict
get_transaction_summary(account_id, from_date, to_date) → dict
# summary returns: {count, data: [{transactionType, status, count, totalNetAmount}]}
```

### Positions

```python
get_position(account_id, security_id, as_of_date) → dict
get_positions(account_id, as_of_date, skip=0) → dict
get_position_history(account_id, security_id, from_date, to_date, skip=0) → dict
# history is sorted ascending by asOfDate
```

### Settlements

```python
get_settlement(settlement_id) → dict
get_settlement_status(transaction_id) → dict   # lookup by transaction, not settlement ID
get_settlements(account_id, settlement_date, status=None, skip=0) → dict
get_settlement_fails(from_date, to_date, account_id=None, skip=0) → dict
```

### Balances

```python
get_cash_balance(account_id, currency, as_of_date) → dict
get_cash_balances(account_id, as_of_date, skip=0) → dict
get_projected_balance(account_id, currency, as_of_date) → dict
# projected returns subset: {accountId, currency, asOfDate, closingBalance, pendingCredits, pendingDebits, projectedBalance}
```

### Limit and Pagination

All list operations accept `skip: int = 0` (clamped to ≥0) and `limit` (clamped to `[1, 200]` via `clamp_limit()`). Default limits: accounts 20, transactions 50, others 200. Page size for positions/settlements/fails is fixed at 200 per page; for balances it is 50 per page.

---

## Transport Layers

### MCP — `bank_ods.mcp`

- Server ID: `bank-ods`
- Transport: controlled by `MCP_TRANSPORT` env var (`stdio` default; `sse` for chatbot/K8s)
- Entry point: `python -m bank_ods.mcp`
- Tools: 15 `@mcp.tool()` functions in `tools.py`, each a single-line delegate to services
- Startup: `ensure_indexes()` via lifespan context manager
- Tool docstrings are LLM-visible tool descriptions
- **MCP transport evolution:** Desktop Claude uses `stdio` (1:1 process). Future chatbot deployment uses `sse` — just set `MCP_TRANSPORT=sse` and expose port 8002.

### REST — `bank_ods.rest`

- Framework: FastAPI
- Entry point: `uvicorn bank_ods.rest:app --port 8000`
- Docs: `http://localhost:8000/docs` (Swagger UI)
- Health: `GET /health` → `{"status": "ok"}` (K8s liveness/readiness probe)
- Error responses: HTTP 404 (NOT_FOUND), 500 (MONGO_ERROR) — not 200 with error body
- Request logging: JSON-structured per-request log via `RequestLoggingMiddleware`
- 5 routers: accounts, transactions, positions, settlements, balances

**Endpoint summary:**

| Prefix | Endpoints |
|---|---|
| `/accounts` | GET `/{id}`, GET `?client_id&status&limit&skip` |
| `/transactions` | GET `/{id}`, GET `?account_id&from_date&to_date&status&transaction_type&limit&skip`, GET `/summary?...` |
| `/positions` | GET `/{account_id}?as_of_date&skip`, GET `/{account_id}/{security_id}?as_of_date`, GET `/{account_id}/{security_id}/history?from_date&to_date&skip` |
| `/settlements` | GET `/{id}`, GET `/by-transaction/{txn_id}`, GET `?account_id&settlement_date&status&skip`, GET `/fails?from_date&to_date&account_id&skip` |
| `/balances` | GET `/{account_id}?as_of_date&skip`, GET `/{account_id}/{currency}?as_of_date`, GET `/{account_id}/{currency}/projected?as_of_date` |
| `/health` | GET — ops probe |

### GraphQL — `bank_ods.graphql`

- Framework: Ariadne (ASGI)
- Entry point: `uvicorn bank_ods.graphql:app --port 8001`
- Endpoint: `POST http://localhost:8001/graphql`
- Health: `GET /health` → `{"status": "ok"}`
- Debug: controlled by `DEBUG` env var (default `false` — never leaks stack traces in production)
- Request logging: JSON-structured via `RequestLoggingMiddleware`
- SDL generated at runtime from the ENTITIES registry by `sdl.py`
- 15 query fields with `skip: Int` on all list operations
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

## Logging

Structured JSON logging is configured at app startup via `configure_logging(LOG_LEVEL)` in `logging_config.py`. All output goes to stdout (K8s log aggregation captures stdout).

Each HTTP request produces a log line:
```json
{"level": "INFO", "logger": "bank_ods.http", "msg": "{\"method\": \"GET\", \"path\": \"/accounts\", \"status\": 200, \"duration_ms\": 12.3}"}
```

`LOG_LEVEL` env var controls verbosity (default `INFO`).

---

## Kubernetes Deployment

### Load profile

| Interface | Volume | Peak |
|---|---|---|
| GraphQL | 40-50K req/day | 2-3K req in 5 min (~10 req/sec EOD) |
| REST | ~10K req/day | Lower peaks |
| MCP | Dev team usage | Variable throughout day |

A single async Python pod handles ~10 req/sec comfortably. K8s adds redundancy and EOD burst capacity via HPA.

### Manifests (`k8s/`)

| Manifest | Description |
|---|---|
| `configmap.yaml` | `MONGODB_DB`, `LOG_LEVEL`, `DEBUG`, `MONGO_TIMEOUT_MS` + MongoDB URI secret |
| `rest-deployment.yaml` | 2 replicas; 256Mi/250m limits; `/health` liveness + readiness |
| `rest-service.yaml` | ClusterIP (add Ingress for external exposure) |
| `graphql-deployment.yaml` | 2 replicas baseline; same resource limits |
| `graphql-service.yaml` | ClusterIP |
| `graphql-hpa.yaml` | HPA: min 2, max 8 replicas; scale at 60% CPU |
| `mcp-deployment.yaml` | 1 replica; `MCP_TRANSPORT=stdio` by default |
| `mcp-service.yaml` | ClusterIP; active only when `MCP_TRANSPORT=sse` |

### K8s deployment model

- One uvicorn worker per pod (K8s handles horizontal scaling via replicas — do not use `--workers N`)
- GraphQL HPA scales from 2→8 replicas at EOD peaks; REST stays at 2 fixed replicas
- Motor client is a per-pod singleton — each pod manages its own connection pool
- MongoDB URI is in a K8s Secret, not a ConfigMap

### Dockerfiles

Three separate multi-stage Dockerfiles (`Dockerfile.rest`, `Dockerfile.graphql`, `Dockerfile.mcp`) use `python:3.12-slim` with `uv` for reproducible, fast builds from `uv.lock`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB` | `bank_ods` | Database name |
| `MONGO_TIMEOUT_MS` | `10000` | Server selection, connect, socket timeout (ms) |
| `DEBUG` | `false` | GraphQL debug mode; `true` exposes stack traces |
| `LOG_LEVEL` | `INFO` | Python logging level (DEBUG/INFO/WARNING/ERROR) |
| `MCP_TRANSPORT` | `stdio` | MCP transport: `stdio` (desktop) or `sse` (chatbot/K8s) |

Copy `.env.example` to `.env` before running locally.

---

## Testing Strategy

Tests require a running MongoDB with seeded data (`python scripts/seed_data.py`).

| File | What it tests |
|---|---|
| `test_services.py` | Service functions directly — happy paths, NOT_FOUND, filters, aggregation, skip pagination |
| `test_rest.py` | REST endpoint HTTP status codes, response shapes, `/health`, 404s, skip pagination |
| `test_graphql.py` | GraphQL query structure, `/health`, skip pagination |
| `test_parity.py` | **Cross-layer equivalence** — REST == GraphQL == service for every operation including skip |

49 tests total. All must pass before merge.

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
- `first_account`, `first_balance`, `first_settled_txn` — fetched from seeded DB; known-good test anchors
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

## Running Locally

```bash
# 1. Start MongoDB
docker compose up -d mongodb

# 2. Install dependencies
uv sync

# 3. Seed sample data
python scripts/seed_data.py

# 4. Run full test suite
pytest tests/ -v

# 5a. MCP server (stdio — for Claude Desktop / VS Code)
python -m bank_ods.mcp

# 5b. REST API
uvicorn bank_ods.rest:app --port 8000

# 5c. GraphQL API
uvicorn bank_ods.graphql:app --port 8001

# Or run everything via Docker Compose (REST + GraphQL + MongoDB)
docker compose up
```

### VS Code / Claude Desktop MCP Registration

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bank-ods": {
      "command": "uv",
      "args": ["run", "python", "-m", "bank_ods.mcp"],
      "cwd": "C:/dev/clio-git/mongo-mcp-test",
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "bank_ods"
      }
    }
  }
}
```

Restart VS Code after editing. The server name `bank-ods` corresponds to `FastMCP("bank-ods")` in `server.py`. Tools appear in Claude Code as `mcp__bank-ods__<tool_name>`.

---

## Design Decisions

**Single service layer.** All transport layers delegate to `bank_ods.services.*`. No transport contains query logic. This makes each transport interchangeable and parity-testable.

**Models as schema source of truth.** Pydantic models define fields and types once. The ENTITIES registry propagates this to index creation and SDL generation, preventing drift.

**Append-only snapshots for temporal data.** Positions and balances write new documents per date rather than updating in place. This preserves full history without a change-log pattern and simplifies range queries.

**Error envelope, never raise.** Service functions return `{error, code}` dicts on failure. REST maps these to HTTP status codes via `check()` in `rest/errors.py`. GraphQL resolvers pass through the service result (null-propagation on non-null field violations). This keeps error handling explicit at each transport boundary.

**ISO 8601 at boundaries.** External APIs always send and receive `"YYYY-MM-DD"` strings. Services parse to `datetime` internally. Serialization back to strings happens in `serialize_doc()` at the return boundary.

**Limit and skip at services.** All list operations accept `limit` (clamped to `[1, 200]`) and `skip` (clamped to `≥0`) inside the service. Transport layers pass both through without re-validating, trusting the service invariant.

**SDL at runtime.** The GraphQL schema is generated from Pydantic models at process startup, not from a static `.graphql` file. This ensures the schema is always consistent with the Python models.

**One uvicorn worker per K8s pod.** Motor manages its own async connection pool per process. Multiple pods (via replicas + HPA) provide horizontal scale, not multiple workers per pod. This simplifies resource accounting and crash isolation.

**Motor timeout configuration.** `serverSelectionTimeoutMS`, `connectTimeoutMS`, and `socketTimeoutMS` are all set from `MONGO_TIMEOUT_MS` (default 10s). Under EOD burst conditions, a slow MongoDB query holds a uvicorn worker; timeouts bound the blast radius.

**Why fastmcp over the raw MCP SDK?** fastmcp removes boilerplate: JSON schema generation from type hints, transport setup, lifespan management. The raw SDK is fine but adds noise for a prototype.

**Flat documents, not deeply nested.** Simpler queries, simpler tool responses. In a real ODS the document model would reflect entity relationships more aggressively; here we prioritize queryability from an LLM tool perspective.

**No MongoDB auth.** This is a local-only prototype. Docker Compose runs MongoDB without authentication. Do not add auth — it is unnecessary and would complicate local setup for no benefit.

---

## Constraints

- Do not add collections beyond the six defined without discussion.
- Do not add MongoDB authentication.
- All new data access must go through `bank_ods.services.*`.
- Do not add mutation tools to the MCP server — this is a read-only ODS view.
