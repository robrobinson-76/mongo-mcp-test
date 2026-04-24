# K8s Scalability Implementation Plan

## Context

Target load: 40-50K GraphQL req/day, ~10K REST req/day, MCP for dev team.  
Peak: 2-3K GraphQL requests in a 5-minute EOD window (~10 req/sec).  
Deployment target: Kubernetes.  
Latency requirement: sub-second p99.

The async Python stack (FastAPI + motor + Ariadne) handles this load comfortably.
Work is about K8s readiness, operational correctness, and MCP evolution path.

---

## Phase 1 — Config & DB layer

**Files:** `src/bank_ods/config.py`, `src/bank_ods/db/client.py`

- Add `DEBUG`, `LOG_LEVEL`, `MONGO_TIMEOUT_MS` to config (from env with safe defaults)
- Add Motor connection timeouts: `serverSelectionTimeoutMS`, `connectTimeoutMS`, `socketTimeoutMS`
- Motor singleton pattern is correct for K8s (one client per pod, connection pool per client)

---

## Phase 2 — Structured JSON logging

**Files:** `src/bank_ods/logging_config.py` (new)

- Custom `_JsonFormatter` using stdlib `logging` (no new dependency)
- `configure_logging(level)` called at app startup
- `RequestLoggingMiddleware` (Starlette `BaseHTTPMiddleware`) logs method, path, status, duration_ms per request
- Used by both REST and GraphQL FastAPI apps

---

## Phase 3 — REST correctness

**Files:** `src/bank_ods/rest/errors.py` (new), `src/bank_ods/rest/app.py`, all routers

### 3a. Error responses
- Create `check(result)` helper in `rest/errors.py`
- Maps `code == "NOT_FOUND"` → HTTP 404, everything else → HTTP 500
- Raises `HTTPException` so FastAPI serializes correct status codes
- Each router wraps its service call: `return check(await svc.get_account(account_id))`

### 3b. Health endpoint
- Add `GET /health` returning `{"status": "ok"}` to `rest/app.py`
- Used as K8s liveness and readiness probe

### 3c. Logging middleware
- Add `RequestLoggingMiddleware` to REST app

---

## Phase 4 — GraphQL correctness

**Files:** `src/bank_ods/graphql/app.py`

- `debug` flag controlled by `settings.DEBUG` env var (default `False`)
- Add `GET /health` FastAPI route before GraphQL mount
- Add `RequestLoggingMiddleware`

---

## Phase 5 — Service layer pagination

**Files:** `src/bank_ods/services/_common.py`, all service files

- Add `clamp_skip(skip)` helper (clamps to 0+)
- Add `skip: int = 0` parameter to all list-returning service functions:
  - `list_accounts`, `get_transactions`, `get_positions`, `get_position_history`,
    `get_settlements`, `get_settlement_fails`, `get_cash_balances`
- REST routers: expose `skip: int = 0` as query param on list endpoints
- GraphQL SDL: add `skip: Int` arg to list query fields
- GraphQL resolvers: pass `skip` through to service functions

---

## Phase 6 — MCP transport env var

**Files:** `src/bank_ods/mcp/__main__.py`, `src/bank_ods/mcp/server.py`

- Add `MCP_TRANSPORT` env var: `stdio` (default, current behavior) or `sse`
- `mcp.run(transport=transport)` — fastmcp supports both transports
- Dockerfile for MCP defaults `MCP_TRANSPORT=stdio`; chatbot deployment sets `sse`
- No behavior change today; enables future chatbot deployment without code change

---

## Phase 7 — Dockerfiles

**Files:** `Dockerfile.rest`, `Dockerfile.graphql`, `Dockerfile.mcp`, `.dockerignore`

- Base: `python:3.12-slim`
- Use `uv` for fast, reproducible installs from `uv.lock`
- Layer order: install deps first (cache), copy source second
- One worker per container (K8s handles horizontal scaling via replicas)
- Separate CMD per service

```
Dockerfile.rest   → uvicorn bank_ods.rest:app --host 0.0.0.0 --port 8000
Dockerfile.graphql → uvicorn bank_ods.graphql:app --host 0.0.0.0 --port 8001
Dockerfile.mcp    → python -m bank_ods.mcp  (stdio default; MCP_TRANSPORT=sse for chatbot)
```

---

## Phase 8 — Docker Compose update

**Files:** `docker-compose.yml`

- Add `rest` service (port 8000, depends on mongodb)
- Add `graphql` service (port 8001, depends on mongodb)
- MCP stays as CLI invocation, not a compose service (stdio transport)
- Shared `MONGODB_URI` env var pointing to compose mongodb service

---

## Phase 9 — Kubernetes manifests

**Directory:** `k8s/`

| File | Contents |
|---|---|
| `configmap.yaml` | `MONGODB_URI`, `LOG_LEVEL`, `DEBUG=false` |
| `rest-deployment.yaml` | 2 replicas, resource limits (256Mi/250m), liveness + readiness on `/health` |
| `rest-service.yaml` | ClusterIP (internal) or LoadBalancer depending on exposure |
| `graphql-deployment.yaml` | 2 replicas baseline, same resources, `/health` probes |
| `graphql-service.yaml` | ClusterIP or LoadBalancer |
| `graphql-hpa.yaml` | HPA: min 2, max 8 replicas, scale at 60% CPU |
| `mcp-deployment.yaml` | 1 replica (stdio), or swap to SSE for chatbot |
| `mcp-service.yaml` | ClusterIP (internal dev access only) |

---

## Implementation order

```
Phase 1  → config + db client          (foundation for timeouts)
Phase 2  → logging_config.py           (needed by phases 3-4)
Phase 3  → REST correctness            (errors, health, logging)
Phase 4  → GraphQL correctness         (debug, health, logging)
Phase 5  → pagination                  (service → REST → GraphQL)
Phase 6  → MCP transport env var
Phase 7  → Dockerfiles + .dockerignore
Phase 8  → docker-compose.yml
Phase 9  → k8s/ manifests
```

---

## What is NOT changing

| Item | Why |
|---|---|
| Framework choices (FastAPI, Ariadne, fastmcp) | Correct for this load profile |
| motor singleton pattern | Right for K8s (one client per pod) |
| Motor pool defaults | Default 100 is fine at 10 req/sec |
| Redis / caching | Not needed at this volume |
| GraphQL DataLoader | No N+1 — resolvers are flat |
| Service layer isolation | Already clean; no change needed |
| MongoDB indexes | Already correct for access patterns |
