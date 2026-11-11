# Project Analysis Summary — `temce`

- **Run date:** 2026-11-01
- **Mode:** read-only (Rigor Analyze / Rigor Audit)
- **Branch:** `w4-fix-security`
- **HEAD:** `df979ca0 fix(scale): make cron state, job locks and cache multi-worker safe`
- **Working tree:** 236 pending entries at scan time — this report describes the tree as observed, not only `HEAD`.
- **Root:** `C:\Users\Iran\Desktop\temce`

> This is not a deep-learning research repository. The skill's structural questions were
> mapped to this platform as: data ingestion → feature/model → backtest → serve.
> No code was modified, no test/lint/type suite was executed (see `EVAL_CONTRACT.md`).

---

## 1. What the system is

An Iran capital-market data + analytics platform (TSE/IFB/IME, Codal, BrsApi, funds,
gold/FX, options) with a FastAPI backend, a Next.js frontend, a backtesting engine and an
ML signal stack. It is deployed as several containers plus a Windows-native mode.

Tech stack (evidence: `pyproject.toml`, `docker-compose.yml`, `frontend/package.json`):

| Layer | Implementation |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2 / pydantic-settings, SQLAlchemy 2 async |
| DB | PostgreSQL/TimescaleDB (Docker service `timescaledb`), plus a local SQLite `transactions.db` |
| State / cache | Redis (single shared State layer) |
| Queue / jobs | `jobs/` registry + scheduler + queue consumer, APScheduler |
| ML | scikit-learn, XGBoost, LightGBM, CatBoost, torch, SHAP |
| Frontend | Next.js 16 / React 19, TanStack Query, Tailwind 4, Vitest |
| Obs | OpenTelemetry, Prometheus, Sentry, structlog |

---

## 2. Module map (top-level)

| Path | Role | Size signal |
|---|---|---|
| `apps/` | Deployable processes: `api`, `admin`, `currency_service`, `decision_engine`, `funds`, `gateway`, `scheduler`, `worker`, `*_worker`, `cli` | 180 py files |
| `core/` | Config, DB, cache, security, logging, resilience, rate limit, feature flags, time | 174 py files |
| `domain/` | Pure domain models per vertical (instruments, options, funds, codal, signals, portfolios …) | 219 py files |
| `services/` | Business logic per vertical (fund_*, codal_*, smart money, signal chain, kill switch …) | 278 py files |
| `repositories/` | The only DB door per aggregate (`instrument_repository`, `quote_repository`, …) | 22 modules |
| `api/` | Legacy/precompute router surface (`api/routers`, `api/ws_manager`) | small |
| `ingestion/` | Upstream adapters + parsers + quality gates (BrsApi, TSETMC, FX, gold, library sources) | 59 py files |
| `brsapi/` | BrsApi-specific jobs, pipelines, repositories, services, quality | 78 py files |
| `jobs/` | Job definitions, registry, locking, dispatcher, retry, reconciliation | 57 py files |
| `ml/` | Datasets, features, models, evaluation, registry, artifacts | 118 py files |
| `backtesting/` | Engine, execution simulator, portfolio, costs, metrics, composer | 302 py files |
| `providers/`, `integrations/`, `schemas/`, `models/`, `migrations/` | Provider layer, external integrations, API contracts, ORM, Alembic (93 versions) | — |
| `frontend/` | Next.js app router (152 `page.tsx`, 71 route dirs), 81 test files | — |
| `tests/` | 631 `test_*.py` files: unit, integration, e2e, gold_desk, performance, load, legacy | — |

---

## 3. Entrypoints

**Serving**
- `main.py` → `uvicorn "apps.api.app:app"` (`core.config.settings`, workers).
- `apps/api/app.py:1064` `create_app()` — middleware stack, lifespan, router setup.
- `apps/api/router.py` `Router.setup()` — 80 `include_router` calls; 72 carry an explicit
  mount-level dependency (`_require_user` / `_require_admin` / `_public_read`).
- Unmounted-by-decision routers are documented in `apps/api/router.py` (API-05) and guarded
  by `tests/unit/api/test_api05_mount_decisions.py`.
- Other apps: `apps/admin/app.py`, `apps/currency_service/app.py`, `apps/decision_engine`,
  `apps/funds`, `apps/gateway`.

**Background**
- `jobs/scheduler.py`, `jobs/registry.py`, `jobs/locking.py`, `jobs/queue_consumer.py`.
- `apps/*_worker` images; compose services `ingestion`, `worker`, `currency`, `backend`,
  `frontend`, `timescaledb`, `redis`.

**Data ingestion**
- `ingestion/main.py`, `ingestion/market_data.py`, `ingestion/brs_api_client.py`,
  `brsapi/jobs/*`, `brsapi/services/sync_service.py`.

**Research / evaluation loop**
- `backtesting/engine/backtest_engine.py`, `backtesting/composer/phase_runner.py`,
  `backtesting/metrics/trade_metrics.py`.
- `ml/evaluation/*`, `ml/models.py` (`register_all_models` imported by the API app).
- `services/evaluation_suite.py`, `services/backtest_framework.py`.

---

## 4. Configuration binding

- Single settings object: `core/config/__init__.py` (pydantic-settings, ~500 lines), split
  helpers under `core/config/` (e.g. `api.py`).
- Env contract documented in `.env.example` (10.7 KB); secrets are not tracked
  (`git ls-tree` shows only `.env.example` and `frontend/.env.sentry.example`).
- Production guard: `Settings.validate_production()` (`core/config/__init__.py:473`) refuses
  `SECRET_KEY` default, `AUTH_DISABLED`, `CORS_ORIGINS=["*"]`, SQLite, insecure cookies; it is
  invoked at startup in `apps/api/app.py:899`, `apps/admin/app.py:19`,
  `apps/currency_service/app.py:26`, and is fail-closed in production.
- Docker/compose defaults and k8s manifests exist; 9 Dockerfiles (api, admin, worker,
  scheduler, frontend, currency, decision-engine, golddesk, root).

---

## 5. What is healthy (verified by reading, not by running)

- **Exception hygiene:** an AST scan of 1,488 backend modules found **0** silent
  `except:`-style handlers with empty bodies and only **4** `except …: pass`.
- **Auth hardening is visible in code:** per-endpoint `Depends(get_current_user)` in
  `gold_analytics`, kill-switch dual-role checks in `system.py`, WebSocket ticket flow
  (`POST /auth/ws-ticket`, 60 s TTL) with the legacy query token explicitly deprecation-logged.
- **Startup safety:** `validate_production()` fails closed; GoldDesk token salt import fails
  fast by design.
- **Concurrency remediation:** recent commits make cron state, job locks and cache
  multi-worker safe (`df979ca0`).
- **Test surface:** 631 test files, 16 files carry `needs_db`, markers configured
  (`pyproject.toml:149`).
- **Boundary contracts exist** (`.importlinter`) even though they are advisory today.

---

## 6. Conservative insertion points (if code changes are later authorised)

| Change type | Preferred zone | Read first |
|---|---|---|
| New read endpoint | `apps/api/endpoints/*.py` + mount in `apps/api/router.py` | the matching service + repository, and `tests/unit/api/` |
| New business rule | `services/<vertical>_service.py` | `domain/<vertical>/`, `repositories/<vertical>_repository.py` |
| New persistence | `repositories/*` + `migrations/versions/` | `migrations/` head, `tests/unit/repositories/` |
| New scheduled work | `jobs/definitions*`, `jobs/registry.py` | `jobs/locking.py`, `jobs/retry_policy.py` |
| New upstream source | `ingestion/<source>/` adapter + quality gate | `ingestion/http_client.py`, `brsapi/quality.py` |
| New model/feature | `ml/features`, `ml/datasets` | `ml/registry`, `ml/evaluation/*` |
| Strategy/cost change | `backtesting/` | `tests/unit/backtesting/test_cost_parity.py` |

Do **not** treat `_FRONTEND_BACKEND_COPY/`, `_audit_base/`, `_base_wt*/`, `_base_wt_clean/`,
`.freebuff/worktrees/`, `venv/`, or the undeclared nested repos `InkGist/` and
`dsh-our-free-model/` as sources of truth — they are copies/worktrees/nested repositories
(see R6/R12).

---

## 7. Related documents in this run

- `RISKS.md` — heuristic findings with evidence paths (none are confirmed bugs).
- `RESEARCH_MAP.md` — entrypoint and artifact map.
- `CHANGE_MAP.md` — allowed vs protected zones.
- `EVAL_CONTRACT.md` — how correctness is (and is not) verified here.
- `status.json` — machine-readable checks and findings.
- `evidence/evidence-2026-11-01.md` — raw commands and key output.
