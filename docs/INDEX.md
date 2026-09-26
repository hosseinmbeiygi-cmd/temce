# Documentation Index — `temce`

## Quick start
- [Project README](../README.md) — what this is, how to run it.
- [Architecture overview](#architecture) — how the pieces fit.

## Architecture
- [Secrets management](./secrets-management.md) — how secrets flow in dev / CI / prod.
- [Decision Engine API](./decision-engine-api.md) — service contract.
- [Job queue](./job-queue.md) — distributed job registry, locking, retries.
- [ML model loader](./ml-model-loader.md) — model hot-reload, versioning.
- [Env vars](./env-vars.md) — every supported variable, with defaults.
- [BrsApi data sources](./brsapi-data-sources.md) — upstream mapping.

## Phase docs (design history)
- [Phase 0](./phase0/) — RawStore, RACI, glossary, schema.
- [Phase 1](./phase1/) — BrokerAdapter, RiskEngine, IV selection, fees/margins.
- [Phase 2](./phase2/) — Normalizer, data quality, backtest cost, CI tests, paper trading.
- [Phase 3](./phase3/) — Allowlist caps, limited live, environments, BCP, security audit.

## Analysis & design notes (2026-09)
- [Project analysis (EN)](./project-analysis-en.md) · [فارسی](./project-analysis-fa.md) — repo-wide review at revision `bc9fd20`.
- [Signal pipeline deep diagnosis (EN)](./signal-pipeline-deep-diagnosis-en.md) — why reliable signal discovery is hard; code-level risks.
- [Options platform architecture (FA)](./options-platform-architecture-fa.md) · [PDF](./options-platform-architecture-fa.pdf) — full design for the TSE options trading platform.
  - Part 7 — strategy engine: [اصلی](./options-platform-part7-strategy-engine-fa.md) · [تکمیلی](./options-platform-part7-strategy-engine-final-fa.md)
  - Parts 8–9 — backtest & prediction engines: [تکمیل بخش ۸ و ۹](./options-platform-part8-9-backtest-ml-fa.md)
- [Enterprise-plus prompt example (FA)](./enterprise-plus-prompt-example-fa.md) — maximal prompt template for fund-analysis features.

## Operations
- [.github/workflows](../.github/workflows/) — CI definitions (lint / type / test / build).
- [Dependabot](../.github/dependabot.yml) — weekly dep updates.

## Quality baseline
- Lint: `ruff check .` (configured in `pyproject.toml`)
- Format: `ruff format --check .`
- Type: `mypy` — strict on critical modules, baseline-gated elsewhere (see CI).
- Tests: `pytest --cov-fail-under=60` for critical financial modules.
- Secrets: `gitleaks` (pre-commit + CI).
- Frontend: `tsc --noEmit` + `eslint . --max-warnings=0`.
