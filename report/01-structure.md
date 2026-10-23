# Step 1: Structure and Statistics

**Project root:** `C:/Users/Iran/Desktop/temce`
**Report generated:** 2026-10-05
**Git last commit:** 2026-09-26 19:39:31 +0330 (8660f79b)
**Git total commits:** 442

---

## 1. Languages, frameworks, versions, build tools, application type

### Application type
- **Backend API service** (FastAPI/uvicorn) — multi-service architecture
- **Desktop/CLI orchestration layer** via `main.py` and workers
- **Frontend** (React/TypeScript) under `frontend/` — limited presence (14 TS/TSX files at depth 2)
- **Some Go code** under `go/` (excluded from analysis)
- **Separate side projects** excluded: `claw-code/`, `mimicode-go/` (in .gitignore)

### Core stack (from `pyproject.toml` + `requirements.txt`)
- Python >=3.11
- FastAPI >=0.109, <0.140 + starlette >=0.40,<1.0
- SQLAlchemy >=2.0, <2.1 (async), alembic >=1.13
- pandas >=2.1, <3.0; numpy >=1.26, <2.4
- redis >=5.0; celery[redis] >=5.3,<6
- asyncpg >=0.29; aiosqlite >=0.20
- pydantic >=2.5; pydantic-settings >=2.1
- ML optional: scikit-learn, xgboost, lightgbm, catboost, torch, shap, imbalanced-learn
- Dev tooling: pytest, pytest-cov, pytest-asyncio, ruff, mypy, pre-commit
- Additional runtime: structlog, scipy, PyYAML, psutil, requests, tenacity, yfinance, pytz, greenlet, python-multipart, sentry-sdk, opentelemetry
- DB: TimescaleDB (PostgreSQL) — `timescaledb.zip` present (local install artifact)
- Cache/queue: Redis
- Object storage: MinIO (minio>=7.2)
- Monitoring: Prometheus (prometheus-client, prometheus.yml), OpenTelemetry, Sentry

### Build / orchestration tools
- **Makefile** present (install, lint, typecheck, test, dev, api, worker, docker-up/build/down, backup, prod-check, clean)
- **Docker** — multiple Dockerfiles (api, admin, frontend, golddesk, scheduler, worker, decision-engine, currency) + docker-compose*.yml (3 files)
- **uvicorn** as ASGI server
- **pre-commit** configured (ruff, mypy, gitleaks, trailing-whitespace, yaml/json/toml validation, detect-private-key)
- **ruff** (linter/formatter), **mypy** (type-checker, currently opt-in)
- **git** — 442 commits

---

## 2. File and line statistics by language and folder (excluding skipped files)

### File counts (project Python files only, excluding excluded dirs)

| Category | Count |
|---|---|
| Python files (`.py`) | ~20,019 |
| Markdown files (`.md`) | 8 at repo root + many in subfolders |
| TypeScript/JS (frontend, depth<=2) | 14 |
| Total non-excluded files (estimate) | ~18,000+ |

> **Note:** The 20,019 Python count includes `code_dump/`, `codal_env/`, `.kilo/`, `_FRONTEND_BACKEND_COPY/`, `.agents/skills/*`, and `report/` trees. The "real" application Python files are fewer. A precise split is in the skipped-files section below.

### Line counts (Python, excluding excluded dirs and vendor/skill trees)

| Scope | Python files | Total lines |
|---|---|---|
| **All project Python** (incl. code_dump, codal_env, _FRONTEND_BACKEND_COPY) | ~20,019 | ~222,690 |
| **`services/`** | 246 | ~79,146 |
| **Rest of project** (excl. services, code_dump, codal_env, _FRONTEND_BACKEND_COPY, .kilo, .agents, report) | — | ~33,165 |

> The services/ tree alone is ~79k lines — by far the largest concentration of logic.

### Large generated/external trees (excluded from deep reads, size only)

| Path | Reason for exclusion |
|---|---|
| `node_modules/` | npm dependency tree (size: large, du timed out) |
| `venv/` | Python virtualenv (size: large, du timed out) |
| `ml_artifacts/` | ML model outputs (in .gitignore) |
| `history_data/` | Fetched historical data (in .gitignore) |
| `crypto_history/` | Crypto history data (in .gitignore) |
| `backtest_data_all/` | Backtest data (exists at root) |
| `codal_env/` | Codal virtualenv — contains heavy vendor libs (polars 13k+ lines, pyarrow tests, etc.) |
| `.kilo/` | Worktree clones (duplicate code trees from git worktree operations) |
| `_FRONTEND_BACKEND_COPY/` | Duplicate backend copy (likely test/migration artifact) |
| `.agents/skills/*` | Downloaded skills — read-only data, not application code |
| `code_dump/` | Code dumps (some tracked, some not; contains copies of core modules) |
| `reports/` | Pre-existing reports directory |
| `storage/`, `data/`, `*.db`, `dump.rdb` | Runtime data |

---

## 3. Largest / most-changed / stale files

### 20 largest application Python files (excluding vendor trees, .kilo, _FRONTEND_BACKEND_COPY, .agents, report)

| Lines | Path |
|---|---|
| 3,344 | `apps/api/endpoints/brsapi.py` |
| 2,137 | `services/stock_assistant_service.py` |
| 2,049 | `services/quant_signal_orchestrator.py` |
| 2,010 | `services/unified_assistant_service.py` |
| 1,990 | `build_symbol_reports.py` |
| 1,832 | `apps/api/endpoints/funds.py` |
| 1,812 | `brsapi/services/sync_service.py` |
| 1,798 | `tests/comprehensive/test_all.py` |
| 1,768 | `brsapi/jobs/registry.py` |
| 1,664 | `code_dump/15_brsapi_endpoints/brsapi.py` |
| 1,640 | `tests/unit/services/test_indicator_calculation.py` |
| 1,539 | `services/multi_market_signal_engine.py` |
| 1,374 | `src/gold_desk/api.py` |
| 1,316 | `code_dump/02_orchestrator/quant_signal_orchestrator.py` |
| 1,310 | `apps/api/endpoints/backtests.py` |
| 1,204 | `apps/api/app.py` |
| 1,181 | `services/screener_service.py` |
| 1,178 | `code_dump/01_signal_engine/multi_market_signal_engine.py` |
| 1,177 | `tests/unit/services/test_quant_signal_orchestrator.py` |
| 1,153 | `services/options_service.py` |

> **Observation:** `code_dump/` contains full copies of modules also present in `services/` and `apps/`. These are duplicates/snapshots — they must not be read as the source of truth.

### 20 most frequently changed files in git history (all branches)

| Changes | File |
|---|---|
| 35 | `crawler_state.json` |
| 34 | `core/config/__init__.py` |
| 30 | `apps/api/endpoints/news.py` |
| 28 | `apps/api/router.py` |
| 25 | `frontend/package.json` |
| 25 | `apps/api/app.py` |
| 25 | `README.md` |
| 24 | `repositories/news_repository.py` |
| 22 | `frontend/src/app/page.tsx` |
| 22 | `.gitignore` |
| 21 | `services/alert_service.py` |
| 21 | `jobs/definitions/__init__.py` |
| 21 | `frontend/src/lib/api.ts` |
| 21 | `frontend/src/app/alerts/page.tsx` |
| 21 | `frontend/package-lock.json` |
| 21 | `core/database.py` |
| 21 | `brsapi/client.py` |
| 21 | `apps/api/middleware.py` |
| 21 | `apps/api/endpoints/codal.py` |
| 21 | `apps/api/endpoints/brsapi.py` |

> **Observation:** `crawler_state.json` (35 changes) is a runtime state file — heavy churn, possibly a smell. `core/config/__init__.py` (34 changes) is the config layer — high churn here may indicate evolving configuration semantics.

### Files unchanged for a long time
(Root-only `.md` files all have few changes — see least-changed list above.)
Specific long-unchanged application files: not computed in this batch (requires per-file commit-date scan; deferred to Step 4 or on-demand).

---

## 4. Skipped files/folders and reasons

### Excluded by .gitignore (and confirmed absent/not-read)
- `__pycache__/`, `*.pyc`, `*.egg-info/` — compiled/ metadata
- `venv/`, `.venv/`, `env/` — virtualenvs
- `node_modules/` — npm deps
- `*.log`, `logs/` — log files
- `data/`, `*.db`, `*.sqlite` — runtime data
- `pgdata/`, `timescaledata/`, `miniodata/`, `promdata/`, `grafanadata/` — Docker volume data
- `.coverage`, `htmlcov/`, `.pytest_cache/` — test artifacts
- `.mypy_cache/`, `.ruff_cache/` — tool caches
- `ml_artifacts/`, `train_all_models_results.json`, `catboost_info/` — ML outputs
- `history_data/`, `crypto_history/`, `code_dump/` (partially), `test_results/` — data/dumps
- `*.pid`, `*.rdb`, `*.whl`, `*.pkl`, `*.pth` — runtime/ binary artifacts
- `*.bin`, `checkpoint.json` — sensitive/ cleanup
- `go/`, `go.cmd`, `go.ps1`, `start`, `stop` — separate Go toolchain / shell scripts
- `claw-code/`, `mimicode-go/` — separate projects
- `*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.ico`, `*.pdf`, `*.woff`, `*.woff2`, `*.ttf`, `*.eot`, `*.otf` — media/assets
- `tree.txt`, `frontend-all-code.txt`, `funds-all-code.txt`, `*_all-code.txt`, `*_all_codes.txt` — generated text dumps
- `json/brsapi/*_state.json` — runtime state churn
- `.kilo/` — git worktree clones (duplicates)
- `_FRONTEND_BACKEND_COPY/` — duplicate backend copy
- `.agents/skills/*` — downloaded skills (data, not application code)
- `report/` — this audit's own output (created now)

### Explicit exclusions in this audit
- `codal_env/` — vendor Python environment (polars, pyarrow, etc.); size noted, not read
- `.kilo/` — git worktree duplicates; not read
- `_FRONTEND_BACKEND_COPY/` — duplicate; not read
- `code_dump/` — snapshots/duplicates of modules; not treated as source of truth (may be spot-checked against live modules for consistency)

---

## 5. Configuration files, environments, dependency management

### Dependency management
- `pyproject.toml` — project metadata, dependency ranges, ruff/mypy config
- `requirements.txt` — runtime deps with comments (F01/F02 dependency-policy annotations)
- `requirements-dev.txt` — dev deps
- `requirements-overrides.txt` — overrides
- `requirements.lock` — fully-pinned transitive closure (used by Docker/CI)
- Policy note (from requirements.txt): ranges in `pyproject.toml` are declarations only; production installs use `requirements.lock`. Regenerate via `uv pip compile ...`.

### Configuration files
- `config/` — config loaders (PyYAML used per requirements.txt)
- `.env` — present (6,836 bytes) — **DO NOT READ CONTENTS**; sensitive
- `.env.bak.1790980646` — backup (6,869 bytes) — **DO NOT READ**
- `.env.example` — example template (6,869 bytes) — can read for structure
- `.env.production` — production env (1,114 bytes) — **DO NOT READ**
- `alembic.ini` — DB migration config
- `.dockerignore` — Docker ignore rules
- `docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.production.yml` — orchestration
- `prometheus.yml` — Prometheus scrape config
- `.pre-commit-config.yaml` — pre-commit hooks (gitleaks, ruff, mypy, pre-commit hooks)
- `.flake8` — flake8 config (168 bytes)
- `.importlinter` — import linter config
- `.hadolint.yaml` — Dockerfile linter config

### Environment / deployment
- Multiple Dockerfiles for different services
- `deploy/`, `k8s/` — deployment configs (present, not read in this batch)
- `.github/workflows/ci.yml`, `ci-pr.yml`, `decision-engine.yml`, `fund-service.yml`, `release.yml`, `secrets-scan.yml` — CI/CD
- `.github/dependabot.yml` — dependency updates

---

## 6. State of tests, linter, type-checker, CI/CD, logging, monitoring

### Tests
- **Present:** `tests/` directory with many subdirectories:
  - `tests/unit/` (e.g., `test_indicator_calculation.py`, `test_quant_signal_orchestrator.py`)
  - `tests/comprehensive/test_all.py` (1,798 lines — very large)
  - `tests/integration/`, `tests/e2e/`, `tests/load/`, `tests/performance/`, `tests/fixtures/`
  - `tests/gold_desk/`, `tests/iran_market_data/`, `tests/legacy/`
  - Many standalone test scripts at root: `test_options.py`, `test_screener_api.py`, `test_signal_api.py`, `test_backtest.py`, `test_codes.py`, `test_db.py`, etc.
- **Test runner:** pytest (in Makefile: `pytest tests/unit -v --tb=short --timeout=60`)
- **Test coverage tooling:** pytest-cov in dev deps; `.coverage`, `htmlcov/` in gitignore
- **Risk:** Many test files at root and in `tests/` — need to verify which are actually run in CI vs ad-hoc. `test_all.py` at 1,798 lines is suspiciously large for a single test file.

### Linter
- **ruff** — configured in `pyproject.toml` (target py311, line-length 120, select E/F/I/N/W/UP/B/SIM/ARG/C4, with per-file ignores)
- **flake8** — `.flake8` present (may be redundant with ruff)
- **pre-commit** runs ruff + ruff-format with `--fix`

### Type-checker
- **mypy** — in dev deps and pre-commit, but **opt-in** (commented out in pre-commit config: `# args: [--strict]`, `# files: ^(apps|brsapi|services|domain)/.*\.py$`)
- Makefile typecheck: `mypy apps core domain services --ignore-missing-imports || true` (note: `|| true` means it never fails the build)

### CI/CD
- **GitHub Actions** present: `ci.yml`, `ci-pr.yml`, `decision-engine.yml`, `fund-service.yml`, `release.yml`, `secrets-scan.yml`
- **gitleaks** in pre-commit and CI (secrets detection)
- **Dependabot** configured

### Logging
- **structlog** >=24.1 — structured logging (in dependencies)
- `core/logging/__init__.py` mentioned as entry point for structlog init
- Sentry SDK configured (`sentry-sdk[fastapi]>=2.0`)

### Monitoring
- **Prometheus** — `prometheus-client`, `prometheus.yml`, metrics export
- **OpenTelemetry** — API + SDK + OTLP exporter
- **Sentry** — error tracking
- `monitoring/` directory present (not read in this batch)
- `observability_sentry.py` in core/

### Quality-tool observations
- mypy is opt-in and swallow-fail (`|| true`) — type safety is not enforced in CI
- Large test file `tests/comprehensive/test_all.py` (1,798 lines) — may be a grab-bag; verify it is meaningful
- `code_dump/` contains duplicate copies of modules — risk of confusion about which is canonical

---

## 7. Locations of all skills folders

### Project-level skills
- **`.agents/skills/`** — 50 skill directories present
  - Includes: `ai-research-explore`, `analyze-project`, `anti-detect-browser`, `canvas-design`, `clerk-testing`, `code-review`, `convex-quickstart`, `create-technical-spike`, `drizzle`, `equity-research`, `explore-code`, `finishing-a-development-branch`, `firebase-basics`, `flutter-add-widget-test`, `frontend-design`, `gws-gmail-forward`, `high-end-visual-design`, `hyperframes-registry`, ... (and more)
  - Each skill has `SKILL.md` + optional `scripts/`, `references/`, `agents/` subdirs
  - **Status:** listed, not read (Step 6 covers them)

### User-level skills
- `~/.claude/skills/` — not checked yet (optional; prompt says list locations found in Step 1 plus any pointed to)
- `.claude/` at project root contains only `settings.local.json` — no skills here

### Summary
- Project skills: `.agents/skills/` (50 dirs)
- User skills: `~/.claude/skills/` (not yet enumerated)
- No other skill locations identified in this batch

---

## Output files produced in this step

- `report/01-structure.md` (this file)
- `report/PROGRESS.md` (updated separately)

## Next step

Step 2: Module classification and reading plan → `report/02-modules-plan.md`
