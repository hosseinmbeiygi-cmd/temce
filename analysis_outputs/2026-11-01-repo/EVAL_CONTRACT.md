# Evaluation Contract — `temce` (2026-11-01)

## Purpose

Define what “verified” means for this repository so that any later change can be judged
against a stable baseline, and record exactly what this read-only analysis did *not* run.

## Canonical commands (declared in the repo)

| Purpose | Command | Source |
|---|---|---|
| Unit tests | `pytest tests/unit -v --tb=short --timeout=60` | `Makefile: test` |
| Full suite | `pytest tests/ -v --tb=short --timeout=120` | `Makefile: test-all` |
| DB-backed tests | `pytest -m needs_db` | `pyproject.toml:130,154` |
| Lint | `ruff check .` | `Makefile: lint`, `.github/workflows/ci.yml:99` |
| Type check | `mypy apps core domain services --ignore-missing-imports` | `.github/workflows/ci.yml:105` |
| Type check (strict island) | `mypy <10 signal-chain files>` | `.github/workflows/ci-pr.yml:77` |
| Boundary check | `lint-imports --config .importlinter` | `.github/workflows/ci.yml:102` |
| Frontend tests | `npm test` (`vitest run`) in `frontend/` | `frontend/package.json` |
| Production config | `python -c "from core.config import settings; settings.validate_production()"` | `Makefile: prod-check` |
| Migrations | `alembic upgrade head` | `Makefile: migrate` |

## Gate status as configured (confirmed by reading)

| Gate | Status | Reason |
|---|---|---|
| Ruff | PASS | Hard-fails CI (`ruff check . --output-format=github`). |
| Mypy (broad) | FAIL | `|| true` in CI and `ignore_errors = true` for most modules. |
| Mypy (strict island) | PASS | Ten signal-chain files run strict in `ci-pr`. |
| Import-linter | FAIL | `|| echo "::warning::…"` and a wildcard ignore neutralising the sqlalchemy contract. |
| Unit tests | PARTIAL | Default `addopts` excludes `needs_db`; CI runs `tests/unit` and `tests/gold_desk`. |
| Production guard | PASS | `validate_production()` is fail-closed and called at boot in API/Admin/Currency. |
| Secret scan | PASS | `.github/workflows/secrets-scan.yml` exists; `.env` is untracked. |

## Executed in this run

- Static filesystem/git inventory (`ls`, `git ls-tree`, `git log`, `git status`).
- AST scans over 1,488 backend modules: silent handlers, empty functions, syntax check.
- Targeted reads/greps for entrypoints, routers, config, CI, tests, frontend.

## Not executed (BLOCKED by this skill’s read-only, low-execution policy)

- `pytest` (any scope), `ruff`, `mypy`, `lint-imports`, `npm test`, `docker compose`.
- Alembic against a live database; any BrsApi/network call.
- Browser-level frontend verification.

Consequence: **no claim in this report depends on a passing or failing test run.** All
findings are configuration/code-reading facts or explicitly labelled heuristics.

## Environment caveats recorded in the repo

- `pyproject.toml:140` — `timeout_method = "thread"`: on Windows a native stall kills the
  whole pytest process; long runs are recommended on Linux.
- `pyproject.toml:146-148` — session-scoped event loop required; per-module loops break
  asyncpg connections.
- `.env` is untracked; local runs depend on operator-provided DSN/Redis. Do not print or
  copy secret values into reports.
