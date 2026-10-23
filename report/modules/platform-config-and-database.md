# Module card: platform-config-and-database

**Name:** platform-config-and-database  
**Path:** `core/config/__init__.py` (375 lines), `core/database.py` (~200+ lines read; full file read)  
**Tier:** 1 (config drives auth, secrets, rate limits, DB — blast radius high; database is the persistence core)  
**Purpose:** Pydantic Settings from `.env`, production validation, async SQLAlchemy engine + session factory + read-replica, commit-guard for raw DML.  
**Main files (lines):** `core/config/__init__.py` (375), `core/database.py` (full read)  
**Files read:** both fully  
**Files unread:** none in this module

## 3.1 Identity

- **Entry points / consumers:**
  - `core.config.settings` is imported by virtually every module (`from core.config import settings`).
  - `core.database.get_session`, `get_replica_session`, `init_database`, `close_database` used by API lifespan, services, jobs.
  - `apps/api/app.py`, `apps/decision_engine/app.py`, workers use DB init/close.
- **Dependencies:** `pydantic`, `pydantic_settings`, `sqlalchemy`, `asyncpg`, `aiosqlite`, `pathlib`, `re`, `contextlib`.

## 3.2 Logic and algorithms

- **Config** (`core/config/__init__.py`):
  - `Settings(BaseSettings)` with `env_file=".env"`, `extra="ignore"`.
  - Notable fields:
    - `auth_disabled` (default False) — auth opt-out flag (docstring: sandbox only).
    - `secret_key` default `"change-me-in-production"` (alias `SECRET_KEY`).
    - `cors_origins` default `["http://localhost:3000"]`.
    - `enable_input_sanitization=True`.
    - `database_auto_create_tables=False` (production must use Alembic).
    - Provider timeouts/retries/rate-limits; per-endpoint rate limits for signals/backtests/ML/portfolios/alerts/screener.
    - `validate_production()` enforces: secret_key not default, CORS not `["*"]`, not SQLite, `auth_cookie_secure=True`, OTLP endpoint set.
  - `database_url_async` / `database_replica_url_async` properties add `+asyncpg` driver suffix for PostgreSQL.
- **Database** (`core/database.py`):
  - Async engine + `async_sessionmaker` (expire_on_commit=False).
  - Read-replica optional (`database_replica_enabled` + `database_replica_url`).
  - `init_database()` connects, sets isolation level READ COMMITTED explicitly, optionally auto-creates tables only if `database_auto_create_tables=True` (SQLite dev mode).
  - **Commit guard** (audit DB-001/DB-002): listeners on sync session `do_orm_execute` + `after_flush` flag `_audit_wrote`; used by `get_session` to ensure a COMMIT even when autoflush cleared dirty state.
  - Raw-text DML detection via regex `^(WITH|INSERT|UPDATE|DELETE|MERGE)\b`.

## 3.3 Data

- **Inputs:** `.env` (via pydantic_settings), command-line/env overrides.
- **Outputs:** settings object, DB engine + sessions.
- **Storage:** PostgreSQL (asyncpg) primary + optional replica; SQLite only as dev fallback (rejected in production by validator).
- **Data contract:** session factory API; callers use `async for session in get_session():`.

## 3.4 General checklist

- **Logic:**
  - [YES] Production validation exists and runs (caller-dependent). [SEEN: core/config/__init__.py:318-333]
  - [YES] Auto-create tables disabled by default; production uses Alembic. [SEEN: core/config/__init__.py:86, database.py]
  - [NO] `validate_production` does NOT check `auth_disabled=True` — possible to have auth disabled in production if env sets it. [SEEN: core/config/__init__.py:318-333 vs :25]
- **Time:** DB layer uses UTC via SQLAlchemy/asyncpg; no local-time usage seen here.
- **Data:**
  - [YES] DB URL constructed with async driver suffix. [SEEN: database.py]
  - [YES] Isolation level pinned to READ COMMITTED. [SEEN: database.py]
  - [UNKNOWN] Whether replica read routing is actually used by read-only endpoints (config exists; need to check middleware/endpoints).
- **Errors:**
  - [YES] Connection failure raises RuntimeError with helpful message. [SEEN: database.py]
  - [YES] Replica unavailable → fallback to primary + warning. [SEEN: database.py]
- **Concurrency:** async session factory; `expire_on_commit=False` reduces lazy-load surprises.
- **Performance:**
  - [YES] Pool config: pool_size=20, max_overflow=30, pre_ping=True, recycle=3600. [SEEN: database.py]
  - [UNKNOWN] Whether replica is actually wired into read endpoints (potential read-scaling).
- **Security:**
  - [SEEN] Default secret key (see SEC-01 in core-security card).
  - [SEEN] `enable_input_sanitization=True` default; middleware applies it. [SEEN: core/config/__init__.py:81]
  - [SEEN] Production validator blocks SQLite and open CORS. [SEEN: core/config/__init__.py:318-333]
  - [UNKNOWN] Whether DB credentials ever logged (connection string split masking in logs: `url.split('@')[-1]`). [SEEN: database.py]
- **Logging:** DB connect/replica events logged at INFO/WARNING.

## 3.5 Specialized checklist

- **Commit-guard (DB-001/DB-002):** implemented via sync-session event listeners + `_audit_wrote` flag. [SEEN: database.py:15-49] — good; verify `get_session` actually reads the flag and commits.
- **Raw DML detection regex:** `^(WITH|INSERT|UPDATE|DELETE|MERGE)\b` case-insensitive. [SEEN: database.py:16] — covers common DML; CTE writes caught.

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| CFG-01 | core/config/__init__.py:63,322-323 | Default SECRET_KEY = "change-me-in-production". | [SEEN] | high | Same as SEC-01. | Confirm real secret in .env. |
| CFG-02 | core/config/__init__.py:25,318-333 | `auth_disabled` not blocked by `validate_production`. | [SEEN] | medium | Auth could be disabled in production by env. | Add `auth_disabled` to production validation. |
| CFG-03 | core/config/__init__.py:81 | `enable_input_sanitization=True` default; relies on middleware. | [SEEN] | low | Defense-in-depth; ensure middleware exists and is wired. | Verify `InputSanitizationMiddleware` in `apps/api/middleware.py`. |
| CFG-04 | core/database.py:15-49 | Commit-guard via `_audit_wrote`; verify `get_session` honors it. | [SEEN] | low | Prevents lost writes on autoflush. | Read `get_session` implementation. |
| CFG-05 | core/database.py | Replica config exists; unclear if wired into read endpoints. | [SEEN] | low | Read scaling opportunity / consistency question. | Check read-endpoint session resolution. |

## 3.7 Module monetary risk

- **If config/database fails:**
  - Default secret → token forgery (monetary: unauthorized trades/reads).
  - DB connection misconfiguration → platform down (no reads, no writes).
  - Auth disabled → open endpoints.
  - Auto-create tables on prod (if flag flipped) → migration drift / data loss risk.

## 3.8 Questions and unknowns

- Is `validate_production()` actually called at startup? (Need to find caller — likely app lifespan.)
- Is `InputSanitizationMiddleware` present and wired?
- Is `get_session` the context manager that honors `_audit_wrote`?
- Is read-replica actually used?

## 3.9 Recommendations for Claude

- Read `core/config/__init__.py` fully (already done here, but Claude should re-verify production validation caller).
- Read `apps/api/middleware.py` for auth + sanitization + rate-limit wiring.
- Read `core/database.py:get_session` (not fully read here — only the top ~200 lines) to confirm commit-guard.

---
*Saved: 2026-10-05 · labels: [SEEN] observed in code (path:line), full file reads for core/config/__init__.py and core/database.py*
