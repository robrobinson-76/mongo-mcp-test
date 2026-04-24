# mongo-mcp-test — Claude Code Project Context

## Purpose

Prototype demonstrating how a Python MCP (Model Context Protocol) server can sit in front of a MongoDB-backed bank ODS, giving an LLM structured, tool-driven access to operational data (transactions, positions, settlements, cash balances).

This is a self-contained local development prototype. It is **not** a production system. The goal is to validate the MCP ↔ MongoDB interaction pattern and explore what useful tooling looks like for an AI agent querying custodian-bank-style operational data.

---

## Target directory

```
C:\dev\clio-git\mongo-mcp-test\
```

All paths below are relative to this root.

---

## Tech stack

| Layer | Technology |
|---|---|
| Database | MongoDB (local, via Docker) |
| MCP server | Python 3.11+, `fastmcp` library |
| Seed data | Python script using `pymongo` + `faker` |
| Package management | `uv` (preferred) or `pip` + `venv` |
| IDE integration | VS Code with Claude extension; MCP wired via `claude_desktop_config.json` |
| Runtime | Local Windows dev machine |

---

## Project layout

```
mongo-mcp-test/
├── CLAUDE.md                    ← this file
├── docs/
│   ├── DESIGN.md               ← schema and architecture decisions
│   ├── PLAN.md                 ← original phased implementation tasks
│   └── PLAN-multilayer.md      ← unified MCP/REST/GraphQL plan
│
├── docker-compose.yml           ← MongoDB container
│
├── src/
│   └── bank_ods/
│       ├── __init__.py
│       ├── config.py            ← env loading
│       ├── models/              ← Pydantic v2 entity models (single source of truth)
│       ├── db/                  ← motor async client + index management
│       ├── services/            ← async business logic (all three layers call these)
│       ├── mcp/                 ← thin MCP layer (fastmcp)
│       ├── rest/                ← thin REST layer (FastAPI)
│       └── graphql/             ← thin GraphQL layer (Ariadne)
│
├── scripts/
│   └── seed_data.py             ← loads sample data into MongoDB
│
├── tests/
│   ├── conftest.py
│   ├── test_services.py
│   ├── test_mcp.py
│   ├── test_rest.py
│   ├── test_graphql.py
│   └── test_parity.py          ← cross-layer equivalence harness
│
├── pyproject.toml               ← dependencies
└── .env.example                 ← MONGODB_URI and other config vars
```

---

## Domain model (summary)

Six collections model a simplified custodian bank ODS. See `DESIGN.md` for full schemas.

| Collection | Purpose |
|---|---|
| `accounts` | Account master — client accounts held at the custodian |
| `securities` | Security master — equities, bonds, funds |
| `transactions` | Trade and cash transaction records |
| `positions` | Current and historical security holdings per account |
| `settlements` | Settlement instructions and lifecycle status |
| `cash_balances` | Cash balance per account per currency |

Collections use camelCase field names and ISO 8601 dates stored as MongoDB `Date` objects.

---

## Architecture conventions

- Three thin transport layers (MCP, REST, GraphQL) all call the same `bank_ods.services.*` functions.
- `bank_ods.services.*` is the only place MongoDB is touched.
- Pydantic v2 models in `bank_ods.models` are the single source of truth for field names, types, indexes, and serialisation.
- MongoDB driver is `motor` (async). All service functions are `async def`.
- Tool/endpoint names follow the pattern `verb_noun` — e.g. `get_transactions`, `get_position`, `get_settlement_status`.

---

## Environment variables

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=bank_ods
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8000
```

Copy `.env.example` to `.env` before running.

---

## Running locally

```bash
# 1. Start MongoDB
docker compose up -d

# 2. Install dependencies
uv sync        # or: pip install -e ".[dev]"

# 3. Seed sample data
python scripts/seed_data.py

# 4a. Start MCP server (stdio — for VS Code Claude extension)
python -m bank_ods.mcp

# 4b. Start REST API
uvicorn bank_ods.rest:app --port 8000

# 4c. Start GraphQL API
uvicorn bank_ods.graphql:app --port 8001

# 5. Run full parity test harness
pytest tests/ -v
```

---

## VS Code / Claude integration

The MCP server is registered in `claude_desktop_config.json` (see `DESIGN.md` → VS Code Integration section for the exact config block). Once registered, Claude Code in VS Code can call the MCP tools directly in any conversation opened against this project.

---

## What Claude Code should NOT do in this project

- Do not modify `docs/DESIGN.md` or `docs/PLAN.md` autonomously — those are reference docs.
- Do not add authentication to MongoDB — this is local-only, no auth required.
- Do not create additional collections beyond the six defined without discussion.
