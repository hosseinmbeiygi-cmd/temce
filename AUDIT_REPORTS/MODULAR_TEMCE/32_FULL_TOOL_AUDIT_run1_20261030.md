# FULL TOOL AUDIT — run1 — 2026-10-30

Scope: execute the maximal feasible subset of available tools against the working tree,
stage-by-stage, and report with raw evidence. Status vocabulary: `PASS` / `PARTIAL` /
`BLOCKED` / `FAIL` only. New finding IDs use the `AUD-` prefix so existing `DB-`, `API-`,
`SEC-` numbering is not disturbed.

## 1. Snapshot

- Branch: `integration/golddesk-fixes`
- HEAD: `095cc98f` — 2026-10-30 01:11:25 +0330
- Commits: 245
- Working tree: **dirty** — 355 porcelain entries (113 unstaged-modified, 112 untracked,
  87 staged-added, 15 added-modified, 17 staged-modified, 11 both).
- Recently touched files (≤120 min) are treated as a concurrent editor's work and marked
  BLOCKED for fixes: `apps/api/endpoints/stocks_v2.py`, `services/market_service.py`,
  `tests/unit/api/test_stocks_v2_freshness_envelope.py`,
  `frontend/src/app/indicators/page.tsx`, several `AUDIT_REPORTS/` files.

Inventory (vendor/worktree dirs excluded):

| Item | Count |
|---|---|
| Python files | 4,921 |
| Test files (`tests/**`) | 736 |
| `.ts`/`.tsx` files | 487 |
| Next.js `page.tsx` | 152 |
| FastAPI route decorators | 694 across 97 files |
| Alembic revisions | 89 (single head `0119_service_private_tables`) |
| ORM model files | 52 |

## 2. Tool coverage

Executed:

- Built-ins: Bash, Read, Write, Grep, Glob, Task*, MCP meta tools.
- Gates: `ruff`, `mypy` (`--explicit-package-bases`), `tsc --noEmit`, `eslint`, `vitest`,
  `pytest` (collect + targeted).
- Runtime: `alembic upgrade head` against audit DB; `psql` read-only via Docker;
  `curl`; Chrome DevTools MCP (`list_pages`, `navigate_page`, `list_console_messages`,
  `list_network_requests`, `lighthouse_audit`).
- Data: pandas profiling of local CSVs (DuckDB not installed in `venv`).
- Static graph: AST import-cycle scan over 12 top-level packages.

Not executed (reason):

- Cloud MCPs `qoder-cloud-agents` (80), `graphos-tools` (48), `qoder_sites` (33),
  `sentry-cli`, Postman cloud — no credentials/session.
- `mobile-use` — no device/emulator.
- Finance skills (`stock-market-pro`, `trading-analysis`, `equity-research`, …) — feed is
  US/KR/global, not TSE/BrsApi; would fabricate a domain mismatch.
- Product/design/PM skills — no PRD, design source, or user data to audit.
- `hik-isc-plugin`, `dingtalk`, `cangjie-skills`, `moonbit-skills`, `superun-creation`,
  `meoo` — different domain.
- ML training/fit run — source review only (no dataset/GPU run requested).
- Skill tool was not invoked directly; `code-review` and `security-audit` methodologies
  were applied manually (gates + targeted diff/secret scan).

## 3. Stage results

| Stage | Status | Evidence |
|---|---|---|
| S0 snapshot/inventory | PASS | git snapshot + counts above |
| S1 static gates | PARTIAL | ruff 0, tsc 0, eslint 0 errors/169 warnings; mypy **629 errors**; secret scan 0 |
| S2 backend/API | PARTIAL | OpenAPI builds with env: 671 paths / 706 ops; 1 duplicate operationId; 0 security schemes |
| S3 database | **FAIL** | `upgrade head` exit 1 at 0005 (`relation "quotes" does not exist`); drift test 3 passed |
| S4 tests | PARTIAL | collect 8,158 (2 env errors); API subset 377 pass/7 env-blocked/6 skip; vitest 586 pass |
| S5 frontend runtime | PARTIAL | shell HTTP 200; all `/api/v1/*` calls HTTP 500 (backend offline); Lighthouse 90/96/91/60 |
| S6 data quality | PARTIAL | crypto snapshots stale to 2026-08-26; `all_data_180d.csv` 393 nulls; no duplicates |
| S7 ML leakage review | PASS | chronological split + purge gap + walk-forward gap + train-only scaling; no `shuffle=True` |
| S8 architecture | PARTIAL | 146 modules, **31 two-level import cycles** (85 at top-level granularity) |
| S9 report | PASS | this file + raw log |

## 4. Findings

### AUD-DB-01 — P0 — clean-DB upgrade fails (existing DB-02) — FAIL

Verified live on `tse_quant` (audit container, port 15432): the database has 1 table
(`dual_date_columns`) and no `alembic_version`; `alembic upgrade head` exits **1** at
`0005_add_performance_indexes` with `UndefinedTableError: relation "quotes" does not
exist`; the transaction rolls back and the DB is unchanged. Root cause and the
awaiting-approval baseline design are unchanged from
`30_DB02_ROOT_CAUSE_run1_20261030.md` / `31_DB02_BASELINE_MIGRATION_run1_20261030.md`.

### AUD-API-01 — P2 — duplicate OpenAPI operationId

FastAPI warns: `Duplicate Operation ID market_watch_api_v1_market_watch_get` for
`apps/api/endpoints/market_watch.py`. Generated clients/codegen will collide.

### AUD-API-02 — P2 — no security scheme in the OpenAPI contract

All 706 operations report `security: []`; auth is enforced through custom headers and
`Depends` (104 auth-dependency usages), but the published contract does not declare it.
Consumers and agent tooling cannot discover the auth requirement. (Confirmed by
`app.openapi()` introspection, not by execution.)

### AUD-TEST-01 — P2 — tests hard-wired to native `localhost:5432/market`

`tests/test_screener_flow.py` and `tests/test_sync_2.py` abort collection; 7 gold
endpoint/auth tests fail with HTTP 500 caused by
`RuntimeError: Cannot connect to PostgreSQL … localhost:5432/market`. The audit stack
listens on 15432/16379; the suite does not use it. Environmental, not a code defect,
but it blocks repeatable CI evidence.

### AUD-DATA-01 — P2 — local market samples are stale

`crypto_data/*_180d.csv` end at **2026-08-26** (today: 2026-10-30, ≈65 days gap);
`crypto_data/all_data_180d.csv` has 393 nulls in 184 rows. No duplicate rows detected.
Any dashboard fed from these files shows stale data.

### AUD-ARCH-01 — P2 — package-level import cycles

31 cycles among 146 modules. Examples:
`backtesting.market ↔ backtesting.engine ↔ backtesting.strategies`,
`apps.api ↔ brsapi.services`,
`apps.api → apps.scheduler → jobs → jobs.definitions → brsapi.services → apps.api`.
Top-level-only granularity reports 85 cycles, so the coupling is structural, not a
single-file artifact.

### AUD-FE-01 — P3 — 169 ESLint warnings, 0 errors

Examples: unused `_droppedByContract` (`frontend/src/lib/goldApi.ts:692`), unused
`Shield` import (`frontend/src/lib/nav-config.tsx:9`), unused `isPublic`
(`frontend/src/middleware.ts:131`). 23 are auto-fixable.

### AUD-SEC-01 — P3 — app import requires an explicit token salt (good gate, operational cost)

`apps/api/app.py` imports `src/gold_desk/api_token.py`, which raises unless
`GOLD_API_TOKEN_SALT` is set. OpenAPI generation is therefore impossible without env
(verified: exit 1, then exit 0 with an inline value). Keep the gate; document it for
tooling/CI.

BLOCKED items:

- Redis live checks: `NOAUTH Authentication required` on `tse_redis:16379`.
- Data-driven frontend validation: backend `:8000` is down, so every API call is 500.
- Live DB data-quality comparisons: the audit DB is empty (only `dual_date_columns`).
- Any cloud/credentialed tool: qca, GraphOS, Sites, Sentry, Postman cloud.

## 5. Raw evidence

`AUDIT_REPORTS/MODULAR_TEMCE/evidence/full_tool_audit_20261030_run1.log`
(commands, exit codes, raw output; credentials redacted).

## 6. Verdict

- Stages: 10 executed; **PASS 3** (S0, S7, S9), **PARTIAL 6** (S1, S2, S4, S5, S6, S8),
  **FAIL 1** (S3).
- Findings: P0 ×1, P2 ×5, P3 ×2; BLOCKED categories ×4.
- No file was modified by this run; no fix was applied. DB-02 remains the only release
  blocker in the audited surface.

## 7. Recommended next steps

1. Approve the DB-02 baseline design (one new migration + one `down_revision` line) and
   re-run `alembic upgrade head` on `tse_quant`; acceptance = exit 0 and `alembic current`
   = `0119`.
2. Point the test suite at the audit stack (15432/16379) via env, not `.env`, and re-run
   the 7 blocked tests.
3. Fix the duplicate `market_watch` operationId and declare the auth scheme in OpenAPI.
4. Re-run S5 with the backend up; then Lighthouse a11y/agentic scores are meaningful.
5. Treat the 31 cycles as a separate refactor slice; do not mix with DB-02.
