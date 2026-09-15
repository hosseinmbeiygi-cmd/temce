# ADR-0001: Evolutionary Migration — Modular Monolith → Modular Platform

- **Status:** Accepted
- **Date:** 2026-09-09
- **Phase reference:** Phase 0 (Ammunition Gathering) of the migration plan

## Context

The platform is an operational FastAPI modular monolith (~68 endpoint modules, 438 routes,
199 service files, 110+ tables in one shared PostgreSQL 16/TimescaleDB instance,
Redis 7 streams for jobs). It is actively developed and under CI (ruff, mypy advisory,
pytest, BacktestRunner dispatcher guard, secrets scan).

Primary measured pain points:

- **Shared DB coupling** — every module reads/writes one database; no table has a
  declared owner. 25 of 69 endpoint modules import `sqlalchemy` directly (raw queries
  in the HTTP layer); 65 service files do the same.
- **BrsApi hard limits** — 4000 requests/day, 5-minute window, 302/block responses.
  No budget governor, no circuit breaker metric.
- **ML artifact lifecycle** — `ml_artifacts/` on disk with no registry, versioning or
  retention.
- **Duplication** in services/backtesting and screener families.
- **Dead-letter/retry complexity** in Redis Streams with no idempotency keys or SLO.

## Decision

We adopt an **evolutionary architecture** path (strangler pattern, database decomposition
in stages) instead of microservice extraction or a rewrite:

1. **Phase 0 — measure (this ADR).** Advisory import-linter contracts, dependency graph,
   ADR process, per-domain observability. No behavior change. Nothing breaks.
2. **Phase 1 — logical ownership.** `DATA_OWNERSHIP.md` assigns every table an owner
   domain. Pure logic (e.g. `iran_costs.py`) moves to `libs/market-core` with no DB
   dependency. Import contracts flip from advisory to hard-fail.
3. **Phase 2 — interface hardening.** Outbox pattern, materialized view for
   latest-per-symbol, Schemathesis contract tests over the existing OpenAPI schema.
4. **Phase 3 — first extractions** of already semi-independent services (Currency,
   BrsApi Integration with budget governor + circuit breaker, ML artifact registry).
5. **Phase 4 — selective DB split** (schema-per-service; physical DB split only for
   Market Data time-series and Auth, only if data justifies it).

### Non-negotiable constraints carried through all phases

- No big-bang rewrite; every step backward-compatible and feature-flagged.
- `services/backtesting/costs/iran_costs.py` stays the single source of cost truth;
  when moved to `libs/market-core`, the CI BacktestRunner guard covers the new path.
- BrsApi budget governor respects 4000/day and the 5-minute window in Redis
  (shared counters), never in process memory.
- CI, tests, migrations, observability are preserved at every phase.

## Phase 1 progress (2026-09-09, post-fix session)

- **`Repositories must not import services layer`: KEPT.** Finglish/catalog
  logic moved to `domain/instruments/symbol_finglish.py` +
  `domain/instruments/symbol_catalog.py`; `services/symbol_catalog.py` is now
  a facade; `DEFAULT_SYMBOLS`/`KNOWN_FUND_SYMBOLS` literals are domain-owned
  (services re-export for API compat). `repositories/instrument_repository.py`
  imports domain only. Catalog output byte-identical to git HEAD (519 symbols,
  `فولاد` matched, 38 existing tests pass).
- **`services must not import logging directly`: KEPT.** All 10 direct
  `import logging` under services/ replaced with `core.logging.get_logger`
  (incl. `chat/chart_generator`, `smart_money/parallel_engine`).
- **Remaining BROKEN (expected, deliberately not fixed this session):**
  `ml ↔ endpoints` independence (needs an ML façade service — Phase 2/3 work,
  touches ~50 endpoint files) and `services` raw sqlalchemy
  (63 ignored imports; 41 of 64 files use raw `text()` queries — these are
  repository-boundary work, Phase 1 continued).
- Baseline report refreshed: `docs/dep_graph_import_contracts_baseline.txt`
  (2 kept, 2 broken).

## Consequences

- Import violations are currently **counted, not blocked** (advisory). Phase 0
  baseline (measured 2026-09-09, `lint-imports --config .importlinter`,
  full report in `docs/dep_graph_import_contracts_baseline.txt`):
  - **63** service modules import `sqlalchemy` directly (ignorable until Phase 1
    drives to zero); 25 of 69 endpoint modules likewise.
  - **10** service modules import stdlib `logging` directly instead of `core.logging`.
  - `repositories.instrument_repository` imports `services.symbol_catalog` —
    inverted layering, one concrete fix.
  - `ml` ↔ `apps.api.endpoints` are tangled through ~50 endpoint files
    (via `services.inference_service`, `services.backtest_service`,
    `services.ml_signal_connector`); extraction must route through a service
    façade first.
  - Highest fan-in internal modules: `core.logging` (360), `core.result` (94),
    `domain.common.base_entity` (90), `schemas.common.responses` (63),
    `core.database` (62) — these are the future `libs/` candidates.
- Every future boundary change requires a new ADR before code lands.
- `DATA_OWNERSHIP.md` is the authority for table ownership disputes; schema changes
  to a domain's tables require that domain's CODEOWNERS approval (Phase 1).

## Artifacts created in Phase 0

- `.importlinter` — advisory contracts (logging funnel, ml purity, repo layering,
  services DB access)
- `docs/DATA_OWNERSHIP.md` — 110 tables → owner domains
- `scripts/dep_graph.py` — stdlib AST dependency graph generator (no new deps)
- `monitoring/dashboards/migration_health.py` — Phase-0 Grafana panels:
  `brsapi_blocked_total`, `job_dead_total`
- `docs/dep_graph.md` — baseline services/ dependency graph report
