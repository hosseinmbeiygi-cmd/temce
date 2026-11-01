# Change Map — `temce` (2026-11-01)

Read-only analysis output. Nothing here authorises an edit; it records where an edit would be
low-risk or high-risk if one is later requested.

## Allowed / normal change zones

- `apps/api/endpoints/<feature>.py` — new or changed HTTP handlers.
- `apps/api/router.py` — mount a router (respect the API-05 unmounted list and its guard test).
- `services/<vertical>_service.py` — business rules for one vertical.
- `domain/<vertical>/` — pure models and value objects.
- `repositories/<aggregate>_repository.py` — data access for one aggregate.
- `jobs/definitions*`, `jobs/registry.py` — scheduled/queued work.
- `ingestion/<source>/` — new upstream adapter plus its quality gate.
- `ml/features`, `ml/datasets`, `ml/evaluation` — features, labels, metrics.
- `frontend/src/app/<route>/` and `frontend/src/components/` — UI.
- `docs/`, `analysis_outputs/` — documentation and analysis artifacts.

## Protected zones (verify before touching)

| Zone | Why |
|---|---|
| `migrations/versions/` | 93-revision chain; a bad revision breaks deploy. Read `_alembic_heads.txt` and the DB-02 baseline note first. |
| `core/config/__init__.py` (`validate_production`) | Fail-closed startup guard; weakening it opens production misconfiguration. |
| `core/security/*`, `apps/api/dependencies.py`, `apps/api/middleware.py` | AuthN/AuthZ, token revocation, CSRF, security headers. |
| `apps/api/router.py` mount dependencies | Changing 72 mount-level role guards silently widens access. |
| `tests/unit/api/test_api05_mount_decisions.py` | Guard test that encodes the “unmounted routers” decision. |
| `tests/unit/backtesting/test_cost_parity.py` | Financial correctness contract for costs/rates. |
| `frontend/src/__tests__/*Gold*` | GoldDesk safety/UX contracts. |
| `pyproject.toml` `[tool.mypy]` overrides | Removing `ignore_errors` will surface a large error backlog at once. |

## Data-interface zones (shape changes ripple widely)

- `schemas/**` — request/response contracts consumed by the Next.js client.
- `models/**` (SQLAlchemy) — must move together with `migrations/`.
- `domain/common/enum_types.py`, `core/enums/instruments.py` — shared enums.
- `repositories/base_repository.py` — inherited by every repository.
- `core/shared_state.py` — Redis state documents shared by every API worker.

## Single-variable high-risk zones

Changing one of these alone can shift results or exposure without a visible code diff:

1. `core/config/__init__.py` (defaults, aliases, validators).
2. `.env.example` (documented contract) and compose/k8s env wiring.
3. `services/` → `sqlalchemy` import seam (currently unenforced, see R2).
4. Any `mypy` override or CI `|| true` (see R1/R2).
5. `backtesting/costs`, `backtesting/execution_simulator.py` — silently changes historical P&L.
6. `apps/api/router.py` mount dependency list.
7. `pyproject.toml` pytest addopts (`-m "not needs_db"`).

## Do not treat as source of truth

`_FRONTEND_BACKEND_COPY/`, `_audit_base/`, `_base_wt/`, `_base_wt_clean/`,
`.freebuff/worktrees/`, `venv/`, `.venv/`, `code_dump/`, `_FRONTEND_BACKEND_COPY/backend/`.
