# Research / Execution Map — `temce` (2026-11-01)

The skill's DL-oriented map (train / infer / eval) is expressed here as
**ingest → feature/model → backtest → serve → schedule**.

## Entrypoints

| Stage | Entry | Evidence |
|---|---|---|
| Serve (API) | `uvicorn apps.api.app:app` via `main.py` | `main.py`; `apps/api/app.py:1064` `create_app()` |
| Serve (admin) | `apps/admin/app.py` (`admin_app`) | `Makefile: admin` |
| Serve (currency) | `apps/currency_service/app.py` | Dockerfile.currency |
| Route assembly | `apps/api/router.py` `Router.setup()` | 80 `include_router`, 72 with mount dependency |
| Ingest (BrsApi) | `brsapi/services/sync_service.py`, `brsapi/jobs/*` | compose service `ingestion` |
| Ingest (market/parser) | `ingestion/main.py`, `ingestion/market_data.py`, `ingestion/parser/*` | 59 modules |
| Schedule | `jobs/scheduler.py`, `jobs/registry.py`, `jobs/locking.py` | compose service `scheduler` |
| Queue | `jobs/queue_publisher.py`, `jobs/queue_consumer.py`, `api/ws_manager.py` | Redis |
| Model training | `jobs/model_training.py`, `jobs/model_retraining.py`, `services/auto_retrain_pipeline.py` | strict-mypy list |
| Evaluation | `ml/evaluation/*`, `services/evaluation_suite.py` | metrics/benchmark modules |
| Backtest | `backtesting/engine/backtest_engine.py`, `backtesting/composer/phase_runner.py` | `tests/unit/backtesting/test_cost_parity.py` |
| Signal chain | `services/quant_signal_orchestrator.py` → `signal_voting_system` → `confidence_scorer` → `signal_decision_engine` | strict CI mypy job |
| Frontend | `frontend/src/app/**/page.tsx` (152 pages) | `frontend/package.json` |

## Configuration

- One settings object: `core/config/__init__.py` (pydantic-settings, aliases `UPPER_SNAKE`).
- Split config helpers: `core/config/api.py` and siblings.
- Env contract: `.env.example` (10.7 KB). Tracked env files: `.env.example`,
  `frontend/.env.sentry.example` only.
- Production validation: `Settings.validate_production()` (`core/config/__init__.py:473`),
  invoked at `apps/api/app.py:899`, `apps/admin/app.py:19`, `apps/currency_service/app.py:26`.
- Compose services: `timescaledb`, `redis`, `backend`, `ingestion`, `worker`, `currency`,
  `frontend`.

## Artifacts and outputs

- Migrations: `migrations/versions` — 93 revisions; head recorded in `_alembic_heads.txt`.
- ML artifacts: `ml_artifacts/`, `models/`, `catboost_info/`.
- Reports: `reports/`, `symbol_reports/`, `new_reports/`, `AUDIT_REPORTS/`.
- Test evidence (untracked/root): `baseline_*.txt`, `after_issue*_*.txt`, `unit_v*.log`,
  `full_unit_issue4.log`.
- Generated code dumps (tracked): `BACKTEST_ALL_CODE.txt`, `GOLD_CODE_FULL.txt`,
  `gold_complete_bundle.txt`.

## Data stores

- PostgreSQL/TimescaleDB (primary), replica URL supported (`settings.database_replica_url`).
- Redis (cache, shared state, locks, WS tickets, rate-limit buckets).
- SQLite `transactions.db` (5.2 GB on disk, untracked; its `-wal` is tracked — see R4).
- MinIO client dependency present in `pyproject.toml`.

## Test surfaces

- `tests/unit/**` (largest), `tests/integration/**`, `tests/e2e/**`, `tests/gold_desk/**`,
  `tests/performance/**`, `tests/load/**`, `tests/legacy/**`, `tests/comprehensive/**`.
- 631 `test_*.py` files; 16 files marked `needs_db`.
- Frontend: 81 `*.test.ts(x)` files under `frontend/src`.
