# TEMCE Platform Architecture

**Iran Market Data & Analytics Platform**
FastAPI · Next.js 16 · TimescaleDB/PostgreSQL · Redis · Docker

---

## Overview

TEMCE is a modular, multi-service platform for collecting, storing, analysing, and back-testing
Iranian capital market data (TSE, IFB, IME, gold, forex, crypto, bonds, derivatives).

---

## Runtime Services (Docker Compose)

| Container | Image / Dockerfile | Port | Role |
|---|---|---|---|
| `tse_timescaledb` | `timescale/timescaledb:latest-pg15` | 5432 | Primary datastore (PostgreSQL + TimescaleDB) |
| `tse_redis` | `redis:7.0-alpine` | 6379 | Cache, job queue, distributed locks |
| `tse_api` | `Dockerfile.api` | 8000 | Main FastAPI application |
| `tse_ingestion` | `Dockerfile` | — | Background data-collection engine |
| `tse_worker` | `Dockerfile.worker` | — | APScheduler + Redis job consumer |
| `tse_currency` | `Dockerfile.currency` | 8002 | Live FX / gold rate micro-service |
| `tse_frontend` | `Dockerfile.frontend` | 3000 | Next.js 16 frontend |

---

## Backend Code Layout (`apps/api`)

```
apps/
  api/          FastAPI app — app.py, routers, middleware, endpoints/
  worker/       APScheduler worker process (__main__.py)
  strategy_worker/  Reserved for future strategy-execution worker
  admin/        Admin dashboard (Jinja2)
core/
  database.py   async SQLAlchemy engine + get_session() generator
  config.py     Pydantic Settings (env-based)
  redis_client.py
  trading_constants.py  TRADING_DAYS_PER_YEAR_* constants
services/       Business logic layer (~103 files)
repositories/   Async SQLAlchemy query layer
domain/         Domain models, value objects, calculation engines
  options/      Black-Scholes, Greeks, probability
  common/       Shared value objects
  instruments/  Instrument definitions
  ...
ml/
  registry.py         Typed production ModelRegistry (ModelArtifactMeta)
  model_registry.py   DemoModelRegistry — in-memory demo data only
  global_registry.py  Singleton seeded with demo data for the ML dashboard
  models/             sklearn / XGBoost / LSTM model wrappers
backtesting/    Multi-asset back-test engine (~275 files)
  metrics/      Sharpe, Sortino, drawdown, benchmark
  strategies/   Factor-based, ML-driven, rule-based
  scenarios/    Bull/bear/sideways market simulation
  visualization/
ingestion/      Data-collection engine (BrsApi.ir client)
brsapi/         ORM models for BrsApi raw data tables
src/
  forecasting/  Drift+vol random-walk price projection
  features/     Feature engineering helpers
jobs/           Scheduled job definitions (19 jobs)
```

---

## API Layer

- **~438 routes** across 60 endpoint files under `apps/api/endpoints/`
- Versioned prefix: `/api/v1/`
- JWT authentication (Bearer token) via `core/security.py`
- CORS configured in `apps/api/app.py`
- `/metrics` endpoint: Prometheus-compatible, auth-protected
- OpenAPI docs at `/docs` (SwaggerUI) and `/redoc`

---

## Database

- **TimescaleDB** (PostgreSQL 16 extension) for time-series price data
- **Alembic** migrations: `alembic/versions/` — head is `0039`, ~122 tables
- Async driver: `asyncpg` via `sqlalchemy[asyncio]`
- Session factory: `core/database.py::get_session()` — async generator;
  commit fires only when the generator resumes after `yield` (callers must
  not `return` early inside `async for session in get_session()`)
- TimescaleDB hypertables used for OHLCV and tick data

---

## Job Scheduler

- **APScheduler** `AsyncIOScheduler` runs inside `tse_worker`
- 19 scheduled jobs under `jobs/` (cron + interval triggers)
- Job pattern: `BaseJob` → `execute(context: JobContext) → JobResult`
- Distributed locking via Redis (prevents duplicate runs in multi-replica)
- Dead-letter queue for failed jobs: see `docs/job-queue.md`

---

## ML Pipeline

- **Production registry** (`ml/registry.py::ModelRegistry`): typed, version-aware,
  supports stage promotion; exported from `ml/__init__.py`
- **Demo registry** (`ml/model_registry.py::DemoModelRegistry`): in-memory,
  uuid-keyed; used only by `ml/global_registry.py` to seed the ML dashboard
- **Model loader**: lazy + LRU cache; see `docs/ml-model-loader.md`
- Supported frameworks: XGBoost, scikit-learn, LSTM (PyTorch/Keras wrappers)

---

## Front-end

- **Next.js 16** (`App Router`) under `frontend/src/app/`
- ~153 pages (`page.tsx`) covering markets, analytics, back-test, ML, admin
- Communicates with the API at `NEXT_PUBLIC_API_URL` (env-injected at build)
- Live FX rates from `tse_currency` via `CURRENCY_API_URL`
- TypeScript strict; Tailwind CSS

---

## Trading-Day Constants (`core/trading_constants.py`)

| Constant | Value | Used for |
|---|---|---|
| `TRADING_DAYS_PER_YEAR_TSE` | 250 | Tehran Stock Exchange default |
| `TRADING_DAYS_PER_YEAR_GLOBAL` | 252 | NYSE / XAU / crypto / USD |
| `TRADING_DAYS_PER_YEAR_IME` | 240 | Iran Mercantile Exchange |
| `CALENDAR_DAYS_PER_YEAR` | 365 | Calendar-day annualisation |

---

## Key External Dependencies

| Dependency | Purpose |
|---|---|
| `fastapi` + `uvicorn` | HTTP server |
| `sqlalchemy[asyncio]` + `asyncpg` | Async ORM |
| `alembic` | DB migrations |
| `redis-py` | Cache + job queue |
| `apscheduler` | Scheduled jobs |
| `pydantic-settings` | Config from env |
| `python-jose` + `passlib` | JWT auth |
| `numpy` / `pandas` | Numerical computing |
| `xgboost` / `scikit-learn` | ML models |
| `sentry-sdk` | Error tracking (optional) |

---

## Deployment

```
docker compose up           # development
docker compose -f docker-compose.yml \
               -f docker-compose.production.yml up   # production
```

Secrets are **never** committed. All passwords/tokens are required env vars
(`:?` syntax in `docker-compose.yml`). See `docs/env-vars.md` for the full list.
