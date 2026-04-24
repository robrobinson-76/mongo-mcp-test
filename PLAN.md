# Implementation Plan — mongo-mcp-test

This is the execution plan for Claude Code. Work through each phase in order. Each phase has a clear goal, the files to create or modify, and verification steps. Do not skip ahead — later phases depend on earlier ones being complete and verified.

---

## Before you start

Confirm these are in place on the local machine before Phase 1:

- [ ] Docker Desktop running
- [ ] Python 3.11+ installed
- [ ] `uv` installed (`pip install uv`) — or confirm using plain `pip + venv`
- [ ] VS Code with the Claude extension installed
- [ ] `C:\dev\clio-git\` directory exists (create it if not)

---

## Phase 1 — Project scaffold

**Goal:** Bare-bones project structure in place. Python environment initialised. Docker MongoDB running.

### Tasks

1. Create the project directory and initialise it as a git repo:
   ```
   mkdir C:\dev\clio-git\mongo-mcp-test
   cd C:\dev\clio-git\mongo-mcp-test
   git init
   ```

2. Create `pyproject.toml` with the following content:
   ```toml
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

   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"
   ```

3. Create `docker-compose.yml`:
   ```yaml
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

4. Create `.env.example`:
   ```
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DB=bank_ods
   MCP_SERVER_HOST=localhost
   MCP_SERVER_PORT=8000
   ```
   Copy `.env.example` to `.env`.

5. Create `.gitignore`:
   ```
   .env
   __pycache__/
   *.pyc
   .venv/
   .uv/
   dist/
   *.egg-info/
   .pytest_cache/
   ```

6. Create the package directory structure (empty `__init__.py` files are fine for now):
   ```
   src/
     mcp_server/
       __init__.py
       server.py        (stub)
       db.py            (stub)
       tools/
         __init__.py
         transactions.py  (stub)
         positions.py     (stub)
         settlements.py   (stub)
         balances.py      (stub)
         accounts.py      (stub)
   scripts/
     seed_data.py       (stub)
   tests/
     __init__.py
     test_tools.py      (stub)
   ```

7. Install dependencies:
   ```
   uv sync
   # or: python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"
   ```

8. Start MongoDB:
   ```
   docker compose up -d
   ```

### Verification

```bash
# MongoDB is reachable
python -c "import pymongo; c = pymongo.MongoClient('mongodb://localhost:27017'); print(c.server_info()['version'])"
# Expected: prints the MongoDB version string (e.g. "7.0.x")
```

---

## Phase 2 — MongoDB layer

**Goal:** `db.py` provides a working MongoDB client and collection accessors. All six collections exist with correct indexes.

### Tasks

1. Implement `src/mcp_server/db.py`:
   - Load `MONGODB_URI` and `MONGODB_DB` from environment (use `python-dotenv`).
   - Create a module-level `MongoClient` singleton.
   - Expose a `get_db()` function returning the database handle.
   - Expose `get_collection(name: str)` returning a collection handle.
   - On first call, ensure indexes are created (call `_ensure_indexes()`).

2. Implement `_ensure_indexes()` in `db.py`. Create indexes per the schemas in `DESIGN.md`:

   | Collection | Indexes |
   |---|---|
   | `accounts` | `accountId` unique; `clientId`; `status` |
   | `securities` | `securityId` unique; `isin` unique; `ticker`; `assetClass` |
   | `transactions` | `transactionId` unique; `(accountId, tradeDate)`; `status`; `settlementDate`; `securityId` |
   | `positions` | `(accountId, securityId, asOfDate)` unique; `asOfDate`; `accountId` |
   | `settlements` | `settlementId` unique; `transactionId`; `(accountId, settlementDate)`; `status` |
   | `cash_balances` | `(accountId, currency, asOfDate)` unique; `asOfDate` |

### Verification

```python
# Run this from a Python REPL inside the venv:
from src.mcp_server.db import get_db
db = get_db()
print(db.list_collection_names())
# After seeding (Phase 3) all six names should appear.
# Indexes visible via:
for col in ["accounts","securities","transactions","positions","settlements","cash_balances"]:
    print(col, list(db[col].index_information().keys()))
```

---

## Phase 3 — Seed data

**Goal:** `scripts/seed_data.py` runs without error and populates MongoDB with realistic-looking custodian bank data across all six collections.

### Tasks

Implement `scripts/seed_data.py` as a single standalone script. It must:

1. Drop and recreate all six collections on each run (idempotent).

2. Generate and insert in this order (to satisfy references):
   - **20 accounts** — use `faker` for client names; vary `accountType` across CUSTODY/PROPRIETARY/OMNIBUS; set `status` mostly ACTIVE with 2-3 SUSPENDED.
   - **50 securities** — 30 equities (real-ish tickers: AAPL, MSFT, RY.TO, TD.TO, etc.), 15 government bonds, 5 funds. Include both USD and CAD denominated.
   - **2 000 transactions** — reference real `accountId` and `securityId` values. Date-range: last 90 days. Mix of BUY/SELL (70%), DIVIDEND (10%), FX (10%), DEPOSIT/WITHDRAWAL (10%). Status distribution: 80% SETTLED, 10% PENDING, 5% FAILED, 5% CANCELLED.
   - **1 800 settlements** — one per settled/pending/failed transaction. Include realistic `statusHistory` arrays. DVP delivery type for security trades, FOP for transfers.
   - **1 000 positions** — EOD snapshots. For each account, generate daily positions for the 10 most active securities over the last 45 days.
   - **400 cash balances** — EOD snapshots. For each account, generate CAD and USD balances for the last 10 days.

3. Print progress as it inserts: `Inserted N accounts`, `Inserted N securities`, etc.

4. Print a final summary: collection name → document count.

### Verification

```bash
python scripts/seed_data.py
# Expected output ends with:
# accounts: 20
# securities: 50
# transactions: 2000
# positions: 1000
# settlements: 1800
# cash_balances: 400
```

Also spot-check in MongoDB:
```python
from src.mcp_server.db import get_db
db = get_db()
txn = db.transactions.find_one({"status": "SETTLED"})
print(txn["transactionId"], txn["tradeDate"], txn["netAmount"])
```

---

## Phase 4 — MCP server

**Goal:** A working MCP server that Claude Code can connect to via stdio, exposing all tools defined in `DESIGN.md`.

### Tasks

1. Implement `src/mcp_server/server.py`:
   ```python
   from fastmcp import FastMCP

   mcp = FastMCP("bank-ods")

   # Import tool modules so they register their tools on `mcp`
   from mcp_server.tools import accounts, transactions, positions, settlements, balances

   if __name__ == "__main__":
       mcp.run()  # stdio transport
   ```

2. Implement `src/mcp_server/tools/accounts.py` — register `get_account` and `list_accounts` on the `mcp` instance from `server.py`. Query `accounts` collection. Return serialised dicts (no ObjectId, dates as ISO strings).

3. Implement `src/mcp_server/tools/transactions.py` — register `get_transaction`, `get_transactions`, `get_transaction_summary`. For `get_transactions`, accept optional `status` and `transaction_type` filters and an ISO date range (`from_date`, `to_date`). For `get_transaction_summary`, return counts and total `netAmount` grouped by `transactionType` and `status`.

4. Implement `src/mcp_server/tools/positions.py` — register `get_position`, `get_positions`, `get_position_history`.

5. Implement `src/mcp_server/tools/settlements.py` — register `get_settlement`, `get_settlement_status`, `get_settlements`, `get_settlement_fails`.

6. Implement `src/mcp_server/tools/balances.py` — register `get_cash_balance`, `get_cash_balances`, `get_projected_balance`.

7. Serialisation helper — add a `_serialize(doc)` function in `db.py` (or a shared `utils.py`) that converts a MongoDB document dict: ObjectId → str, datetime → ISO 8601 string. Apply it to all tool return values.

8. Error handling — wrap all tool functions in try/except for `pymongo.errors.PyMongoError` and return `{"error": str(e), "code": "MONGO_ERROR"}`.

### Tool implementation pattern (reference)

```python
# tools/transactions.py
from datetime import datetime
from mcp_server.server import mcp
from mcp_server.db import get_collection, serialize

@mcp.tool()
def get_transaction(transaction_id: str) -> dict:
    """Fetch a single transaction by its transaction ID."""
    col = get_collection("transactions")
    doc = col.find_one({"transactionId": transaction_id}, {"_id": 0})
    if doc is None:
        return {"error": "Not found", "code": "NOT_FOUND"}
    return serialize(doc)

@mcp.tool()
def get_transactions(
    account_id: str,
    from_date: str,
    to_date: str,
    status: str = None,
    transaction_type: str = None,
    limit: int = 50,
) -> dict:
    """Query transactions for an account within a date range."""
    col = get_collection("transactions")
    query = {
        "accountId": account_id,
        "tradeDate": {
            "$gte": datetime.fromisoformat(from_date),
            "$lte": datetime.fromisoformat(to_date),
        },
    }
    if status:
        query["status"] = status
    if transaction_type:
        query["transactionType"] = transaction_type
    docs = list(col.find(query, {"_id": 0}).sort("tradeDate", -1).limit(min(limit, 200)))
    return {"count": len(docs), "data": [serialize(d) for d in docs]}
```

### Verification

```bash
# Test that the server starts without import errors
python -m mcp_server.server &
# then Ctrl+C — we just want to confirm it launches cleanly

# List tools via fastmcp CLI (if available):
fastmcp list src/mcp_server/server.py
```

---

## Phase 5 — VS Code integration and smoke test

**Goal:** The MCP server is registered in `claude_desktop_config.json`. Claude Code in VS Code can call tools and get real data back.

### Tasks

1. Create or edit `%APPDATA%\Claude\claude_desktop_config.json`. Add the `bank-ods` entry (see `DESIGN.md` → VS Code Integration section for the exact JSON). Use the `uv` form if `uv` is installed, otherwise use plain `python`.

2. Restart VS Code.

3. Open the Claude extension. Verify `bank-ods` appears in the connected MCP servers list.

4. In a Claude Code conversation in VS Code, run the following smoke test sequence:

   **Smoke test prompt to give Claude Code:**
   ```
   Using the bank-ods MCP tools, do the following and report results:
   1. Call list_accounts() and return the first 3 account IDs.
   2. Take the first account ID and call get_cash_balances() for today's date.
   3. Call get_transactions() for that same account for the last 30 days, status = SETTLED, limit = 5.
   4. Take the first transaction's settlementRef and call get_settlement_status() on it.
   5. Summarise what you found: account name, USD cash balance, number of settled transactions, settlement status.
   ```

5. If any tool returns an error, debug by running the server manually and checking the MongoDB query.

6. Write a basic `tests/test_tools.py` with pytest that imports each tool function directly and calls it against the live MongoDB (populated from Phase 3):
   - `test_get_account_found` — known accountId returns expected fields
   - `test_get_account_not_found` — unknown ID returns `{"error": ..., "code": "NOT_FOUND"}`
   - `test_get_transactions_returns_list` — returns `{"count": N, "data": [...]}`
   - `test_get_settlement_fails_returns_list` — date range covering seeded data returns at least one result
   - `test_get_cash_balance_returns_balance` — known account/currency/date returns `closingBalance`

   Run with: `pytest tests/ -v`

### Verification

All five pytest tests pass. Claude Code returns coherent, data-backed answers in the smoke test prompt — no `{"error": ...}` responses, balances and transaction counts are non-zero.

---

## Completion criteria

- [ ] `docker compose up -d` starts MongoDB cleanly
- [ ] `python scripts/seed_data.py` completes with correct document counts
- [ ] `python -m mcp_server.server` starts without errors
- [ ] All 5 pytest tests pass
- [ ] VS Code Claude extension shows `bank-ods` as a connected MCP server
- [ ] Smoke test prompt returns coherent answers using real seed data

---

## Common issues and fixes

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: mcp_server` | Run with `python -m mcp_server.server` from project root, or install with `pip install -e .` |
| `ConnectionRefusedError` to MongoDB | MongoDB container not running — `docker compose up -d` |
| `fastmcp` not found | Dependency not installed — `uv sync` or `pip install fastmcp` |
| Tools not appearing in Claude | `claude_desktop_config.json` path wrong, or VS Code not restarted |
| Date parse errors in tools | Ensure dates passed as `"YYYY-MM-DD"` strings, not datetime objects |
| ObjectId serialization error in tool return | Apply `serialize()` helper to all docs before returning |
