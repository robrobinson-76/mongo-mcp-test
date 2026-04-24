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
├── CLAUDE.md               ← this file
├── DESIGN.md               ← schema and architecture decisions
├── PLAN.md                 ← phased implementation tasks
│
├── docker-compose.yml      ← MongoDB container
│
├── src/
│   └── mcp_server/
│       ├── __init__.py
│       ├── server.py       ← MCP server entry point (fastmcp)
│       ├── db.py           ← MongoDB connection and collection helpers
│       └── tools/
│           ├── __init__.py
│           ├── transactions.py
│           ├── positions.py
│           ├── settlements.py
│           ├── balances.py
│           └── accounts.py
│
├── scripts/
│   └── seed_data.py        ← loads sample data into MongoDB
│
├── tests/
│   └── test_tools.py       ← basic tool smoke tests
│
├── pyproject.toml          ← dependencies (fastmcp, pymongo, faker, pytest)
└── .env.example            ← MONGODB_URI and other config vars
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

## MCP server conventions

- Built with `fastmcp`. The server exposes **tools** only (no resources or prompts in this prototype).
- Tool functions are pure — they accept filters, query MongoDB, and return dicts or lists. No side-effects.
- Each tool module (`tools/transactions.py`, etc.) registers its tools on the shared `FastMCP` instance imported from `server.py`.
- MongoDB connection is a module-level singleton in `db.py`. Tests can override `MONGODB_URI` via environment variable.
- Tool names follow the pattern `verb_noun` — e.g. `get_transactions`, `get_position`, `get_settlement_status`.

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
uv sync        # or: pip install -e .

# 3. Seed sample data
python scripts/seed_data.py

# 4. Start MCP server
python -m mcp_server.server
# or: fastmcp run src/mcp_server/server.py
```

---

## VS Code / Claude integration

The MCP server is registered in `claude_desktop_config.json` (see `DESIGN.md` → VS Code Integration section for the exact config block). Once registered, Claude Code in VS Code can call the MCP tools directly in any conversation opened against this project.

---

## What Claude Code should NOT do in this project

- Do not modify `DESIGN.md` or `PLAN.md` autonomously — those are reference docs.
- Do not introduce async MongoDB drivers (stick with `pymongo` sync for simplicity in this prototype).
- Do not add authentication to MongoDB — this is local-only, no auth required.
- Do not create additional collections beyond the six defined without discussion.
