# temce Project Analysis

**Date:** September 24, 2026  
**Revision reviewed:** `bc9fd2070a4003bbe4de8c888cd676563aa01046`  
**Scope:** The active repository's architecture, primary execution paths, dependencies, deployment configuration, baseline security, and locally runnable checks. No repository code was changed. This was not a line-by-line audit of every file or a penetration test. The historical `_FRONTEND_BACKEND_COPY/` tree was excluded when drawing conclusions about active code.

## Executive Summary

This is an Iranian market-data and analytics platform with a Next.js frontend, a FastAPI backend, signal and backtesting engines, data ingestion, PostgreSQL/TimescaleDB, and Redis. The standalone frontend builds and type-checks in this environment, and all 408 frontend tests pass. However, **the API cannot be imported at the reviewed revision because unresolved merge markers remain in its main router**. Installing the declared Python requirements and validating the default Docker Compose configuration also fail. Consequently, the full deployment and live API cannot be considered verified.

## Architecture and Data Flow

1. **Frontend:** `frontend/src/app/` contains the App Router pages, while `frontend/src/lib/api.ts` implements the request client and session handling. `frontend/next.config.ts:17` proxies `/api/v1/*` requests to the backend. `frontend/package.json:13` declares Next.js 16 and React 19.
2. **API and identity:** `main.py:7` and `apps/api/app.py:943` are FastAPI entry points. `apps/api/router.py:257` mounts the routers; `apps/api/dependencies.py:221` implements Bearer authentication and role checks. `apps/api/middleware.py` defines CSRF, rate-limiting, and request-security middleware.
3. **Business logic:** `domain/` holds domain models and contracts; `services/` holds business workflows; `backtesting/runner.py` dispatches backtests; and `ml/` implements machine-learning features. `backtesting/costs/iran_costs.py` provides the canonical trading-cost calculation, which has dedicated passing tests.
4. **Data and operations:** `providers/`, `brsapi/`, and `ingestion/` ingest external data. `repositories/` and `core/database.py` provide PostgreSQL access, while `migrations/versions/` contains Alembic migrations. `jobs/` and `apps/scheduler/` handle scheduling, queues, and workers; Redis supports queues, caching, and locks.
5. **Supporting services:** `apps/admin/`, `apps/currency_service/`, and `apps/decision_engine/` provide separate execution surfaces. Root Dockerfiles, `docker-compose*.yml`, and `.github/workflows/` define deployment and CI. `README.md:123` and `docs/PROJECT_GUIDE.md` are useful general maps; `ARCHITECTURE.md:1` primarily describes the BrsApi forecasting subsystem rather than the entire repository.

## Prioritized Findings

### P0 — The main API router cannot be imported

Unresolved `<<<<<<<`, `=======`, and `>>>>>>>` merge markers remain at `apps/api/router.py:223` through `apps/api/router.py:226`. Since `apps/api/__init__.py:1` imports that router, API import, the authentication audit, and collection of dependent tests stop with a `SyntaxError`. Both `py_compile` and `compileall` reproduced the failure. **Recommended fix:** Resolve the conflict while preserving the `news_tag_map_admin_router` import; rerun compilation, the authentication audit, and backend tests.

### P0 — The declared backend dependencies do not resolve

`requirements.txt:7` specifies `sqlalchemy>=2.0`, whereas the `tehran-stocks>=2.0` dependency at `requirements.txt:33` resolves to version 2.0.0, which requires `SQLAlchemy<2.0` according to the observed pip resolver output. Installing `requirements.txt` failed with `ResolutionImpossible`. CI installation at `.github/workflows/ci.yml:85` and the builds defined at `Dockerfile.api:6` and `Dockerfile:9` rely on this file. Installing from `pyproject.toml` separately supplies only a subset without the incompatible provider; it is not a production-deployment fix. **Recommended fix:** Find a compatible provider version or isolate that provider behind an adapter and separate environment; add a reproducible dependency-resolution check.

### P0 — The default Docker Compose configuration is invalid

`docker-compose.yml:35` defines a `backend` service, while the automatically loaded override at `docker-compose.override.yml:6` adds a distinct `api` service **without an image or build context**; `docker-compose.override.yml:47` also adds a distinct `postgres` service. `docker compose config --quiet` failed with “service api has neither an image nor a build context.” Even after aligning service names, the base configuration at `docker-compose.yml:107` references a nonexistent `frontend/Dockerfile`. Its backend build at `docker-compose.yml:38` selects the root `Dockerfile`, whose command at `Dockerfile:14` runs `ingestion.main` rather than the ASGI API. The root `Dockerfile.api` and `Dockerfile.frontend` exist but are not selected by the base Compose file. **Recommended fix:** Align base, override, and production service names, build contexts, Dockerfiles, and proxy targets. Validate Compose before attempting builds and health checks.

### P1 — Development services can be exposed on all host interfaces

`docker-compose.yml:12` and `docker-compose.yml:28` contain fixed development-only default passwords, while `docker-compose.yml:13` and `docker-compose.yml:29` publish PostgreSQL and Redis ports on the host by default. **If deployed on a network-accessible host**, this creates an unauthorized-access risk. This review found no evidence that those defaults are used in production or that access has occurred. **Recommended fix:** Bind development ports to `127.0.0.1` and require explicit secrets on shared hosts or in production; assess the separate production configuration as well.

### P1 — Quality gates and frontend configuration are inconsistent

`Makefile:12` and `.github/workflows/ci.yml:96` suppress mypy failures with `|| true`; `Makefile:9` runs lint with `--fix`, potentially changing source files. The main CI workflow type-checks the frontend but does not run its full Vitest suite (`.github/workflows/ci.yml:137`), although 408 tests passed locally. Also, `docker-compose.yml:118` sets `NEXT_PUBLIC_API_URL` to the internal `http://backend:8000`: that address would not work in a browser **if embedded into the bundle at build time**, and setting it only at runtime does not update an already-built public Next.js variable. Prefer a consistent relative `/api/v1` browser URL and a server-side `API_URL` (`frontend/src/lib/api.ts:1`, `frontend/next.config.ts:19`).

### P2 — Commands and documentation lag behind the repository

`Makefile:31` runs `python -m jobs.worker`, but that module is absent; the existing worker entry point is `apps/worker/__main__.py:1`. Counts in `README.md:16`—88 pages, 39 migrations, and 250 test files—do not match this checkout's tracked-file counts of 146 `page.tsx` files, 67 migration files, and at least 369 `test_*.py` files under `tests/`. The `_FRONTEND_BACKEND_COPY/` tree contains 2,265 tracked files; its relationship to active code should be made explicit. These issues are not the primary startup blockers, but they increase maintenance overhead.

## Validation Results

| Check | Result |
|---|---|
| `npm test -- --run` in `frontend/` | **Passed:** 408 tests across 32 files |
| `npx tsc --noEmit` in `frontend/` | **Passed** |
| `FRONTEND_BUILD_HEAP_MB=4096 npm run build` in `frontend/` | **Passed:** middleware and Sentry deprecation warnings |
| Backtesting `test_cost_parity` and `test_engine_runner` modules | **Passed:** 30 tests using Python 3.11.16 and a limited `pyproject.toml` installation |
| `python -m compileall` across the main Python packages | **Failed:** the API router was the only reported syntax failure |
| `python scripts/check_router_auth.py` and `pytest tests/unit` | **Blocked at router import:** the full backend suite and runtime authentication remain unverified |
| `docker compose config --quiet` | **Failed:** incomplete `api` service |
| `pip install -r requirements.txt` | **Failed:** unsatisfiable SQLAlchemy/provider dependency constraints |

PostgreSQL/Redis end-to-end tests, live-service smoke tests, and an actual Docker build were not run; the dependency, Compose, and syntax blockers must be addressed first. A successful standalone frontend build does **not** establish connectivity to the API.

## Recommended Order of Work

1. Resolve the router merge conflict; make compilation, the authentication audit, and test collection pass.
2. Fix the declared dependency conflict; recheck CI installation and backend Docker builds.
3. Align base, override, and production Compose files with the intended services and Dockerfiles; verify health checks.
4. Harden development port exposure and frontend URL configuration; make mypy and Vitest meaningful CI gates.
5. Refresh the Makefile, README counts, and documentation of the historical copy.
