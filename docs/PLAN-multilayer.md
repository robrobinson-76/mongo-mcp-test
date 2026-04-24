# Plan — Unify MCP/REST/GraphQL behind a shared core

## Context

Today the project exposes six MongoDB collections through a single MCP server built on `fastmcp` + sync `pymongo`. Each `tools/*.py` module hand-codes its Mongo queries and dict-shaping. There is no shared definition of what an `Account` or `Transaction` *is* — field names, types, indexes, and serialisation rules are re-implemented in every tool module.

The user wants three things in one pass:

1. A **single canonical definition** for each of the six entities, shared by every layer (fields, types, indexes, serialisation).
2. A **GraphQL layer** using Ariadne.
3. A **REST layer** using FastAPI (async).

All three transport layers must be *thin*: they do nothing but translate protocol-level input into a service call and translate the result back out. The service layer is the only place Mongo is touched.

A built-in test harness must exercise all three layers end-to-end against real seeded Mongo data so the equivalence is continuously verifiable.

Architectural decisions already locked with the user:
- **Driver:** Motor (async) everywhere. fastmcp supports `async def` tools.
- **Schema source:** Pydantic v2 models — one per collection.
- **GraphQL SDL:** Generated from the Pydantic models at startup.
- **Process model:** Separate entry points (`bank_ods.mcp`, `bank_ods.rest`, `bank_ods.graphql`) sharing the same core package.

---

## Target package structure

Rename `src/mcp_server/` → `src/bank_ods/`. Existing `tools/` modules are deleted and replaced by the layered structure below.

```
src/bank_ods/
├── __init__.py
├── config.py                 # env loading (MONGODB_URI, MONGODB_DB, …)
│
├── models/                   # ── SINGLE SOURCE OF TRUTH ──
│   ├── __init__.py
│   ├── base.py               # BankDocument base (camelCase aliases, ISO date encoders,
│   │                         #   ObjectId→str, classvars: COLLECTION, INDEXES)
│   ├── account.py            # Account
│   ├── security.py           # Security
│   ├── transaction.py        # Transaction
│   ├── position.py           # Position
│   ├── settlement.py         # Settlement + StatusHistoryEntry
│   ├── cash_balance.py       # CashBalance
│   └── registry.py           # ENTITIES = [Account, Security, …]; used by index init + SDL gen
│
├── db/
│   ├── __init__.py
│   ├── client.py             # motor.AsyncIOMotorClient singleton; get_db(), get_collection()
│   └── indexes.py            # ensure_indexes(): iterates registry.ENTITIES, creates per-model indexes
│
├── services/                 # ── BUSINESS LOGIC (async) ──
│   ├── __init__.py
│   ├── _common.py            # serialize_doc(), parse_iso_date(), clamp_limit()
│   ├── accounts.py           # get_account, list_accounts
│   ├── transactions.py       # get_transaction, get_transactions, get_transaction_summary
│   ├── positions.py          # get_position, get_positions, get_position_history
│   ├── settlements.py        # get_settlement, get_settlement_status, get_settlements, get_settlement_fails
│   └── balances.py           # get_cash_balance, get_cash_balances, get_projected_balance
│
├── mcp/                      # ── THIN MCP LAYER ──
│   ├── __init__.py
│   ├── server.py             # FastMCP("bank-ods"); lifespan ensures indexes
│   └── tools.py              # @mcp.tool() wrappers; each body is `return await services.X(...)`
│
├── rest/                     # ── THIN REST LAYER ──
│   ├── __init__.py           # exposes `app`
│   ├── app.py                # FastAPI(); lifespan ensures indexes
│   ├── deps.py               # dependencies (date parsing, limit clamping)
│   └── routers/
│       ├── accounts.py       # GET /accounts, /accounts/{id}
│       ├── transactions.py   # GET /transactions, /transactions/{id}, /transactions/summary
│       ├── positions.py
│       ├── settlements.py
│       └── balances.py
│
└── graphql/                  # ── THIN GRAPHQL LAYER ──
    ├── __init__.py           # exposes `app` (Starlette/FastAPI mount of Ariadne GraphQL ASGI app)
    ├── app.py                # builds schema, mounts Ariadne, lifespan ensures indexes
    ├── sdl.py                # generate_sdl(ENTITIES) → SDL string; entity types + Query root
    └── resolvers.py          # query_type resolvers; every resolver delegates to services.*

scripts/
└── seed_data.py              # unchanged behaviour; switched to motor + asyncio.run
                              #   (or kept sync with pymongo — see Phase 2 note)

tests/
├── conftest.py               # event_loop, seeded_db fixture, rest_client, graphql_client
├── test_services.py          # direct async calls — canonical equivalence source
├── test_mcp.py               # invoke MCP tools via in-process fastmcp client
├── test_rest.py              # httpx.AsyncClient against the FastAPI app
├── test_graphql.py           # posts queries to the Ariadne ASGI app
└── test_parity.py            # ── THE HARNESS ──
                              #   same input → assert MCP == REST == GraphQL == service result

pyproject.toml                # add: motor, fastapi, uvicorn, ariadne, httpx, pytest-asyncio
```

---

## Phase-by-phase plan

### Phase 0a — Documentation reorg

Create `docs/` at the repo root and move the existing planning artefacts into it so planning docs live separately from runtime code:

- `DESIGN.md` → `docs/DESIGN.md`
- `PLAN.md` → `docs/PLAN.md` (original phased plan)
- Copy this plan file in to `docs/PLAN-multilayer.md` (this unified-API plan)

Update any in-repo references (the paths inside `CLAUDE.md` — `DESIGN.md` and `PLAN.md` cross-links, and the "Project layout" block). `CLAUDE.md` itself stays at the repo root. The directive in `CLAUDE.md` that says "Do not modify `DESIGN.md` or `PLAN.md` autonomously" is a content rule — relocating the files is an org change, not an edit; will confirm with the user before moving if they prefer otherwise.

### Phase 0b — Dependencies & rename

- Rename the package directory `src/mcp_server` → `src/bank_ods`. Update `pyproject.toml` `[tool.hatch.build.targets.wheel] packages`.
- Add dependencies: `motor>=3.4`, `fastapi>=0.110`, `uvicorn[standard]>=0.29`, `ariadne>=0.23`, `httpx>=0.27`, `pytest-asyncio>=0.23`.
- Drop no-longer-needed imports of sync `pymongo` inside services (kept only for index creation convenience if needed).

Verify: `uv sync` succeeds; `python -c "import bank_ods"` works.

### Phase 1 — Shared model layer (`bank_ods.models`)

- [bank_ods/models/base.py](src/bank_ods/models/base.py) — `BankDocument(BaseModel)`:
  - `model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel, json_encoders={datetime: ..., ObjectId: str})`.
  - Class vars: `COLLECTION: ClassVar[str]`, `INDEXES: ClassVar[list[IndexSpec]]` where `IndexSpec = tuple[list[tuple[str, int]], dict]` (fields, options like `unique`).
  - `@classmethod from_mongo(cls, doc) -> Self` and `to_mongo(self) -> dict` helpers.
- One file per entity, mirroring the schemas already documented in [DESIGN.md](DESIGN.md) §"MongoDB Collection Schemas". Fields are typed (`str`, `float`, `datetime`, `Optional[...]`, `Literal[...]` for the enum-like fields `accountType`/`status`/`transactionType`/etc.). IDs stay as strings; `_id` is excluded from the model (projected away in services).
- [bank_ods/models/registry.py](src/bank_ods/models/registry.py) — flat list of all six model classes. This is what `ensure_indexes()`, `generate_sdl()`, and tests iterate over.

Verify: `pytest -k test_models_schema` — a trivial unit test asserting each model round-trips through `model_dump(by_alias=True)` and exposes `COLLECTION` + at least one index.

### Phase 2 — DB layer (motor)

- [bank_ods/db/client.py](src/bank_ods/db/client.py) — `get_client()` returns an `AsyncIOMotorClient` singleton; `get_db()`, `get_collection(name)`. Reading `MONGODB_URI` / `MONGODB_DB` from `bank_ods.config`.
- [bank_ods/db/indexes.py](src/bank_ods/db/indexes.py) — `async def ensure_indexes()` iterates `registry.ENTITIES` and calls `create_index(spec.keys, **spec.options)` via motor.
- `scripts/seed_data.py`: keep **sync pymongo** here — it is a one-shot CLI, async buys nothing, and it must match the seed counts in [PLAN.md](PLAN.md) §Phase 3 (20 / 50 / 2 000 / 1 000 / 1 800 / 400). Update only the collection/index creation bits to reference `bank_ods.models.registry` so schema drift is impossible.

Verify: after seeding, `python -c "import asyncio, bank_ods.db.client as c; asyncio.run(c.get_db().list_collection_names())"` lists all six collections.

### Phase 3 — Service layer (`bank_ods.services`) — the canonical core

Every function is `async`, takes primitive / ISO-string inputs, and returns JSON-ready `dict` / `list[dict]`. These are ported 1:1 from the existing `tools/*.py` contents (return shapes, `{"count", "data"}` envelope, error dicts). Key cleanups:

- Date parsing, limit clamping, and `_serialize(doc)` move into `services/_common.py` and are reused everywhere — this replaces the ad-hoc helpers currently duplicated in each `tools/*.py` module.
- Error handling: each service catches `pymongo.errors.PyMongoError` once (at the service boundary) and returns `{"error": str(e), "code": "MONGO_ERROR"}`. Transport layers do NOT re-catch.
- No string interpolation into queries; filters are built as dict literals (as today).

Verify: `tests/test_services.py` exercises the happy path, not-found path, and error envelope for every service function against seeded data.

### Phase 4 — Thin MCP layer (`bank_ods.mcp`)

- [bank_ods/mcp/server.py](src/bank_ods/mcp/server.py) — `mcp = FastMCP("bank-ods")`; lifespan hook calls `await ensure_indexes()` on startup.
- [bank_ods/mcp/tools.py](src/bank_ods/mcp/tools.py) — one `@mcp.tool()` per existing tool, body is literally `return await services.transactions.get_transaction(transaction_id)` etc. Docstrings from the current tool files carry over (they are the LLM-visible description).
- Entry point: `python -m bank_ods.mcp` (also update the `claude_desktop_config.json` args snippet in [DESIGN.md](DESIGN.md) — but that doc is read-only per CLAUDE.md, so instead document the new command in the final commit/PR message).

Verify: `fastmcp list src/bank_ods/mcp/server.py` shows all 15 tools. `tests/test_mcp.py` invokes tools in-process via the fastmcp test client.

### Phase 5 — Thin REST layer (`bank_ods.rest`)

- [bank_ods/rest/app.py](src/bank_ods/rest/app.py) — FastAPI app with lifespan hook for `ensure_indexes()`. Response models are the Pydantic entities from `bank_ods.models` (wrapped in `ListResponse[T]` for list endpoints so `{count, data}` is the schema).
- Routers follow a predictable mapping — one endpoint per service function:

  | Service function | Endpoint |
  |---|---|
  | `get_account(id)` | `GET /accounts/{account_id}` |
  | `list_accounts(...)` | `GET /accounts` (query params: `client_id`, `status`, `limit`) |
  | `get_transaction(id)` | `GET /transactions/{transaction_id}` |
  | `get_transactions(...)` | `GET /transactions` (query params) |
  | `get_transaction_summary(...)` | `GET /transactions/summary` |
  | `get_position(...)` | `GET /positions/{account_id}/{security_id}?as_of_date=` |
  | `get_positions(...)` | `GET /positions/{account_id}?as_of_date=` |
  | `get_position_history(...)` | `GET /positions/{account_id}/{security_id}/history` |
  | `get_settlement(id)` | `GET /settlements/{settlement_id}` |
  | `get_settlement_status(...)` | `GET /settlements/by-transaction/{transaction_id}` |
  | `get_settlements(...)` | `GET /settlements?account_id=&settlement_date=&status=` |
  | `get_settlement_fails(...)` | `GET /settlements/fails?from_date=&to_date=&account_id=` |
  | `get_cash_balance(...)` | `GET /balances/{account_id}/{currency}?as_of_date=` |
  | `get_cash_balances(...)` | `GET /balances/{account_id}?as_of_date=` |
  | `get_projected_balance(...)` | `GET /balances/{account_id}/{currency}/projected?as_of_date=` |

- Router bodies are one line: `return await services.X.fn(...)`. All validation comes from FastAPI's Pydantic-driven query/path param coercion.

Verify: run `uvicorn bank_ods.rest:app --reload`; visit `/docs` — every endpoint and model shows up. `tests/test_rest.py` hits each endpoint with `httpx.AsyncClient(transport=ASGITransport(app=app))`.

### Phase 6 — Thin GraphQL layer (`bank_ods.graphql`)

- [bank_ods/graphql/sdl.py](src/bank_ods/graphql/sdl.py) — `generate_sdl()`:
  - For each model in `registry.ENTITIES`, walk `model.model_fields` and emit `type Account { ... }`. Map Python types → GraphQL scalars (`str`→`String`, `float`→`Float`, `int`→`Int`, `bool`→`Boolean`, `datetime`→custom `DateTime` scalar, `Optional[T]`→nullable, `list[T]`→`[T!]`).
  - Emit nested types for embedded docs (`StatusHistoryEntry` inside `Settlement`).
  - Emit the `Query` root type with one field per service function. Inputs mirror the REST table above (ISO dates are `String`).
  - Emit a `ListResponse`-like wrapper per entity: `type TransactionList { count: Int!, data: [Transaction!]! }`.
- [bank_ods/graphql/resolvers.py](src/bank_ods/graphql/resolvers.py) — `QueryType()` with a resolver per query field, each body `return await services.X.fn(...)`. Because service outputs are already plain JSON-safe dicts with camelCase keys matching the SDL, no reshaping is needed.
- [bank_ods/graphql/app.py](src/bank_ods/graphql/app.py) — `make_executable_schema(generate_sdl(), query_type, datetime_scalar)`; mount via `ariadne.asgi.GraphQL(schema)` wrapped in a tiny Starlette app (or FastAPI with a single `/graphql` route) so we can attach an `ensure_indexes()` lifespan.

Verify: `uvicorn bank_ods.graphql:app --port 8001`; POST `{ accounts: list_accounts(limit: 3) { count data { accountId clientName } } }` returns data. `tests/test_graphql.py` does the same via `httpx.AsyncClient`.

### Phase 7 — Parity test harness (`tests/test_parity.py`)

This is the guardrail that enforces "all three layers serve the same functionality."

- A table of test cases: `(service_fn, args, mcp_tool_name, rest_request, graphql_query)`.
- For each case:
  1. Call the service directly → `expected`.
  2. Call via MCP tool client → `mcp_result`.
  3. Hit the REST endpoint → `rest_result`.
  4. Execute the GraphQL query → `gql_result`.
  5. Assert all four results are equal (after normalising GraphQL's naturally-nested shape: each resolver returns the same envelope as the service).
- Cases cover: one happy-path per service function, one not-found path, one list with filters, and one error path (bad date format).

This test file is the "built-in test harness" the brief asks for. It runs continuously via `pytest tests/test_parity.py -v` against the real seeded Mongo (no mocks — see `CLAUDE.md` testing stance and [PLAN.md:335-342](PLAN.md#L335)).

Also add a convenience script `scripts/run_harness.sh` (or `.ps1` for Windows) that: checks Mongo is up → reseeds → starts REST on :8000 and GraphQL on :8001 in background → runs the parity suite → tears down.

### Phase 8 — Cleanup

- Delete `src/mcp_server/` (replaced).
- Update `.mcp.json` / VS Code config command path from `mcp_server.server` → `bank_ods.mcp`.
- Add a short `README.md` stub (only if the user asks — per CLAUDE.md, don't create docs unsolicited; instead surface the run commands in the final PR description).

---

## Critical files to create / modify

**Create:**
- `src/bank_ods/models/{base,account,security,transaction,position,settlement,cash_balance,registry}.py`
- `src/bank_ods/db/{client,indexes}.py`
- `src/bank_ods/services/{_common,accounts,transactions,positions,settlements,balances}.py`
- `src/bank_ods/mcp/{server,tools}.py`
- `src/bank_ods/rest/app.py` + `routers/*.py` + `deps.py`
- `src/bank_ods/graphql/{app,sdl,resolvers}.py`
- `tests/{conftest,test_services,test_mcp,test_rest,test_graphql,test_parity}.py`
- `scripts/run_harness.{sh,ps1}`

**Modify:**
- [pyproject.toml](pyproject.toml) — add motor/fastapi/uvicorn/ariadne/httpx/pytest-asyncio; update wheel packages.
- [scripts/seed_data.py](scripts/seed_data.py) — drive collection/index creation off `bank_ods.models.registry`.
- `.mcp.json` — point at `bank_ods.mcp`.

**Delete:**
- `src/mcp_server/` (everything under it, including `tools/*.py`, `db.py`, `server.py`).

---

## Reusable pieces from existing code

- The query bodies in the existing `tools/*.py` (per the explore summary: `get_account`, `get_transactions`, etc.) transplant almost verbatim into the corresponding `services/*.py` — only `pymongo` calls become `motor` awaits.
- The `serialize()` helper and error-handling pattern in `src/mcp_server/db.py` are lifted into `services/_common.py`.
- Seed counts and referential rules in [PLAN.md:186-197](PLAN.md#L186) are still the contract for `scripts/seed_data.py`.
- Index definitions in [DESIGN.md:77,107,141,169,207,235](DESIGN.md) become the `INDEXES` classvars on the Pydantic models.

---

## Verification (end-to-end)

```bash
# 1. DB up + seed
docker compose up -d
python scripts/seed_data.py

# 2. Unit + integration tests (uses live seeded DB)
pytest tests/ -v
#    test_models_schema — models are wired correctly
#    test_services      — canonical behaviour
#    test_mcp           — MCP tools match service
#    test_rest          — REST endpoints match service
#    test_graphql       — GraphQL resolvers match service
#    test_parity        — MCP == REST == GraphQL == service for a matrix of cases

# 3. Interactive smoke (each entry point)
python -m bank_ods.mcp                      # MCP over stdio (for VS Code Claude ext)
uvicorn bank_ods.rest:app --port 8000       # REST — visit http://localhost:8000/docs
uvicorn bank_ods.graphql:app --port 8001    # GraphQL — POST to /graphql

# 4. One-shot parity harness
scripts/run_harness.ps1
#    should print "PARITY OK — 15/15 service fns, 3 transports, N cases per fn"
```

Success criteria:
- `pytest tests/ -v` is green.
- All three entry points start without errors.
- `test_parity` proves MCP, REST, GraphQL all return the same result for the same inputs.
- Claude Code in VS Code can still call `list_accounts`, `get_transactions`, etc. via the MCP server (now under `bank_ods.mcp`).
