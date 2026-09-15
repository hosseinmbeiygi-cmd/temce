# Changelog

All notable changes to `temce` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — Quality & Hardening

### Added
- `tests/unit/options/test_greeks.py` — dataclass shape protection.
- `tests/unit/options/test_var_calculator.py` — historical + parametric VaR/CVaR.
- `tests/unit/options/test_monte_carlo.py` — European MC + put-call parity.
- `tests/unit/options/test_margin_engine.py` — strategy detection branches.
- `tests/unit/services/test_signal_decision.py` — Decision/GateResult logic.
- `frontend/src/lib/seeded-random.test.ts` + `dates.test.ts` — pure utils.
- `.pre-commit-config.yaml` — gitleaks + ruff + mypy hooks.
- `.github/dependabot.yml` — weekly dep updates (pip, npm, docker, actions).
- `.github/workflows/secrets-scan.yml` — gitleaks in CI.
- `docs/INDEX.md` — documentation map.
- `docs/secrets-management.md` — secrets policy + Sealed Secrets guide.
- `[tool.coverage]` in `pyproject.toml` — coverage gate for financial modules.

### Changed
- `pyproject.toml` — mypy strict on critical signal/options modules; relaxed
  baseline elsewhere with per-PR gate (1700 errors).
- `pyproject.toml` — ruff ignore-list reduced; per-file-ignores documented.
- `frontend/tsconfig.json` — `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` + `noImplicitOverride` enabled.
- `frontend/eslint.config.mjs` — `no-explicit-any: error`.
- `.github/workflows/ci.yml` — concurrency cancel, mypy baseline gate,
  `--cov-fail-under=60`, removed `mypy ... || true`.
- `.github/workflows/ci-pr.yml` — removed `continue-on-error: true` from
  frontend lint job.
- `Dockerfile` (ingestion) — multi-stage, non-root, HEALTHCHECK.
- `Dockerfile.worker`, `Dockerfile.scheduler` — added HEALTHCHECK.
- `docker-compose.decision-engine.yml` — secrets sourced from env vars.
- `docker-compose.yml` — removed deprecated `version: '3.8'`.
- `apps/api/endpoints/brsapi.py` — `time` import, module-level `_json_sink` hoist.
- `apps/api/app.py` — return-type annotations on cron/cache endpoints.
- `apps/api/router.py` — `ApiResponse[dict[str, object]]`.
- `apps/api/error_handlers.py` — `FastAPI` type on `register_error_handlers`.
- `brsapi/services/query_service.py` — removed dead code (real bug).
- `domain/options/cointegration.py` — renamed to `_mackinnon_pvalue_2var`.
- `domain/options/tree_pricing.py` — SIM108 ternary.
- `domain/decision_engine_v5/trading.py` — removed unused imports.

### Removed
- 19 `scripts/_*.py` tmp/debug files.
- `scripts/_db.py` (helper inlined into `tests/unit/test_dual_dates.py`).
- `project_summary.txt` (2.5MB legacy dump) — untracked.
- `version: '3.8'` from `docker-compose.yml` (deprecated).

### Security
- Plaintext passwords removed from `docker-compose.decision-engine.yml`
  and `k8s/decision-engine-secret.yaml` — now env-interpolated.
- gitleaks pre-commit + CI blocks any future secret commits.
- K8s secret template now uses `stringData` with `REPLACE_ME_*` placeholders.

### Notes
- `TestHestonGate` (in `test_tier2_prediction.py`) is skipped — references
  the deleted `heston_calibration_sufficient` function. Rewrite against
  `calibrate_heston` API is a follow-up.
- mypy strict on the full codebase (~1700 errors) is out of scope; tracked
  in CI as a baseline gate. Strict mode is enforced on critical modules.
