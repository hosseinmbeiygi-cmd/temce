# QA Remediation Report — Temce

**Date:** 2026-10-04
**Baseline audit:** `C:/Users/Iran/Downloads/FINAL_QA_AUDIT_REPORT.md` — **NO-GO, 48.2/100**, 2 P0 / 20 P1 / 8 P2
**Branch:** `main` · **Runtime:** CPython 3.11.9 (venv), pandas 2.3.3, Node 24.16.0, Docker 29.8.0

---

## 1. Verdict

| | Baseline | Recheck | Δ |
|---|---:|---:|---:|
| **Readiness score** | 48.2 / 100 | **67.8 / 100** | **+19.6** |
| **Verdict** | NO-GO | **NO-GO** | unchanged |

Both audited **P0 blockers are fixed and verified in real containers**. The verdict nevertheless stays **NO-GO**, because §9's rule is *"GO requires score ≥ 80 **AND** zero P0 **AND** zero open P1 on money/signal-producing paths"* — and the 20 P1 money/signal findings (F03–F28) are entirely untouched by this remediation. The score alone is also still 12.2 points short of the ≥ 80 gate.

---

## 2. P0-1 — Runtime dependencies (F01)

**Status: FIXED and verified.**

### Root causes found
1. `requirements.txt` omitted 9 packages that the code imports directly (`core/logging` → `structlog`, features → `scipy`, config → `PyYAML`, …).
2. `apps/api/app.py` imports `File()` / `Form()` on 11 endpoints → FastAPI raises `RuntimeError: form data requires "python-multipart"` **at import time**. `python-multipart` was also undeclared.
3. A **hidden, unreported P0 inside the P0**: all multi-stage images ran `adduser --home /app` but the builder stage wrote packages to `/root/.local` and the runtime stage set `PATH=/home/app/.local/bin`. At runtime CPython resolved `site.getusersitepackages()` to `/app/.local/lib/python3.11/site-packages`, which did not exist. The image built cleanly and then failed with `ModuleNotFoundError: No module named 'structlog'` on first use. Fixed to `COPY --from=builder /root/.local /app/.local` + `ENV HOME=/app`.

### Changes
- `requirements.txt` — added `structlog`, `scipy`, `PyYAML`, `psutil`, `requests`, `tenacity`, `yfinance`, `pytz`, `greenlet`, `python-multipart` (each with an inline comment citing the finding).
- Added **upper bounds** so an unpinned install cannot silently resolve a breaking major: `pandas>=2.1,<3.0`, `numpy>=1.26,<2.4`, `sqlalchemy>=2.0,<2.1`, `fastapi>=0.109,<0.140`, `starlette>=0.40,<1.0`.
- `requirements-overrides.txt` — `sqlalchemy>=2.0` was **replacing**, not merging with, the requirements.txt bound. Corrected to `sqlalchemy>=2.0,<2.1`.
- `requirements.lock` — regenerated (430 pins) via `uv pip compile requirements.txt -o requirements.lock --python-version 3.11 --override requirements-overrides.txt`.
- 8 × `Dockerfile*` — `pip install --no-deps -r requirements.lock`; `ENV HOME=/app`; `COPY --from=builder /root/.local /app/.local`; added the missing `COPY` of `ml`, `app`, `monitoring`, `contracts`, `tabdeal`, `reports`, `scripts` (reachable from `apps.api.app` → `ml.models` → `app.alert_hub` → `reports.builders`).
- `.dockerignore` — exclude generated `reports/*.log`, `reports/*.json`, `reports/screenshots/` while keeping the `reports` **package**.

> **Install-mode note (documented in `requirements.txt`):** the lock **must** be installed with `--no-deps`. `tehran-stocks==2.0.0` declares `SQLAlchemy<2.0.0`, so a plain `pip install -r requirements.lock` fails with `ResolutionImpossible`.

### Verification
- Clean venv (`uv venv` + `uv pip install --no-deps -r requirements.lock`): 33/33 declared deps import; `core.logging`, `core.config`, `ml.features.technical_features` import; `apps.api.app` imports → **574 paths / 600 operations**.
- **Lock reproducibility check:** recompiling `requirements.txt` with the same command resolves the **identical 428-package set** (only 11 packages have newer patch releases upstream, which is what a lock is supposed to freeze). The lock is a valid, reproducible pin set — the F02 failure mode is gone.
- **8 / 8 images build** (`qa/build_all_images.sh`, `reports/docker_build_matrix.txt`).
- **8 / 8 containers start with zero `ModuleNotFoundError`** (`qa/boot_all_images.sh`, `reports/docker_boot_matrix.txt`):
  - `api`, `scheduler`, `decision-engine` → `UP`
  - `admin`, `currency` → exit 3, `RuntimeError: Cannot connect to PostgreSQL` (expected; no DB in the boot sandbox) — imports themselves succeed
  - `worker`, `golddesk` → exit 0 one-shot entrypoints
  - API container on port 8099 served `GET /api/v1/health → 200 OK`

---

## 3. P0-2 — pandas `fillna(method=)` removal (F02)

**Status: FIXED and verified.**

- `ml/features/technical_features.py:47` — `.fillna(method='ffill').fillna(0)` → `.ffill().fillna(0)`
- `scripts/run_ml_dual.py:264` — same defect, same fix (found by search, not in the audit)

### Verification
- **Byte-identical output on pandas 2.3.3**: `a.equals(b) is True`.
- **No `TypeError` on pandas 3.0.3** (system Python, where `fillna(method=)` was removed): ran `TechnicalFeatures().compute()` with `FutureWarning` promoted to an error and NaNs injected into high/low → `compute OK, rows: 120`, `atr` NaNs `0`.
- All **15 `ml.features.*` modules** import cleanly under pandas 3.
- ML tests: `tests/unit/ml` → **47 passed**; plus `tests/unit/services/test_feature_engine.py` → **148 passed**.
- Repo-wide import census: **117 / 117 `ml.*` submodules import** (was 93.2 % in the audit).

---

## 4. New defect found and fixed by the live crawl

`/gold/antigravity` threw **minified React error #418** (hydration text mismatch).

**Root cause:** `frontend/src/app/gold/antigravity/page.tsx:161` called `new Date().toISOString()` in the render body of a `"use client"` component (inside `outputJson`). The server render and the client hydration therefore produced different text.

**Fix:** the timestamp is now display-only state populated in a mount effect (`generatedAt`, `useState("")` + `useEffect`), so the first client render matches the server exactly.

**Re-crawl: the #418 error is gone** — `runtime_errors: 0` (was 1).

> Latent residual risk (not fixed, out of scope): the same `new Date()`-in-render pattern exists in ~8 other client components, e.g. `frontend/src/app/markets/gold-fx/page.tsx:89`, `frontend/src/components/DebugPanel/index.tsx:220`, and `useState(new Date().toISOString()…)` initialisers under `app/backtest/*`. Those routes happened not to trip the error in this crawl, but they are the same bug class.

---

## 5. Frontend verification (Task 3)

| Check | Command | Result |
|---|---|---|
| Unit tests | `npx vitest run --maxWorkers=2` | **33 files, 411 tests, all passed** (exit 0) |
| Lint | `node node_modules/eslint/bin/eslint.js src` | **0 errors, 186 warnings** (exit 0) |
| Production build | `node node_modules/next/dist/bin/next build` | **exit 0**, "Compiled successfully", 143 static pages |

Pre-existing issues found but **not** fixed (out of scope, documented):
- `npm run build` is broken on Windows — `scripts/build-with-heap.js` spawns the extensionless POSIX shim `node_modules/.bin/next`. Use the direct `node node_modules/...` invocation above.
- `npm run build` also needs `rm -rf .next` first; a stale `.next/dev/types` causes `Cannot find name 'AppRoutes'`.
- `npx next lint --dir src` — `--dir` is not a valid option in this Next version; `next lint` is gone. Use eslint directly.
- `vitest run` at default worker parallelism **OOMs** (~100 MB heap, `Committing semi space failed`). `--maxWorkers=2` is stable. Unrelated to any code change.

---

## 6. Live Playwright crawl (148 routes)

`qa/ui_crawl.mjs` + `qa/run_ui_crawl.sh` + `qa/ui_crawl_classify.py` → `reports/ui_crawl_results.json`, `reports/ui_crawl_summary.json`, `reports/screenshots/` (148 PNG, 9.7 MB).

| Metric | Value |
|---|---|
| Routes crawled | 148 |
| Verdict **OK** | **147 (99.32 %)** |
| `NOT_FOUND_CONTENT` | 1 — `/codal/[id]`, `h1=404` (synthetic sample id `1`; HTTP 401 from the API) |
| Blank views | **0** |
| Runtime / page errors | **0** |
| Genuine console errors | **0** |
| Backend-unavailable console noise (excluded) | 519 — Next proxy 500s, backend not running during the crawl |

Real UI latency (paint metrics; the crawl's wall-clock figure is inflated by a deliberate 2500 ms settle sleep and is **not** a valid measurement):

| Metric | n | p50 | p90 | max |
|---|---:|---:|---:|---:|
| First Contentful Paint | 62 | 780 ms | 980 ms | 1448 ms |
| DOMContentLoaded | 148 | 108 ms | 300 ms | 417 ms |
| loadEventEnd | 148 | 388 ms | 531 ms | 834 ms |

Measured against a local production build (`next start`) on the same machine — not a deployed/CDN environment. The backend was **not** running, so live data-dependent UI behaviour remains unverified.

---

## 7. Backend test suite

All `tests/` executed in bounded chunks (`qa/run_unit_tests.sh`, `qa/run_toplevel_tests.sh`, `--timeout=20 --timeout-method=thread`); raw per-batch results in `reports/pytest_chunks.txt`.

| | Audit baseline | Recheck |
|---|---:|---:|
| Passed | 4 963 | **4 975** |
| Failed | 145 | **81** |
| Errors | 6 | **4** |
| Skipped | — | 55 |
| Executed | 5 114 | 5 060 |
| **Pass rate** | 97.05 % | **98.32 %** |

**10 tests never execute** (not counted in either figure): `tests/unit/test_brsapi_usage_recorder.py` hangs — `pytest-timeout` fires and dumps stacks, but the process never exits. Each file passes in isolation when run without its neighbours, so this is cross-test state pollution plus a non-terminating path, and it is **pre-existing**.

Spot-check of the failures confirms they are unrelated to this remediation, e.g. `tests/unit/scripts/test_build_feature_store.py::test_build_all_commits_and_logs` → `AttributeError: <module 'scripts.build_feature_store'> does not have the attribute 'async_session_factory'` (a test that patches a symbol the module no longer defines).

---

## 8. `qa/` scripts re-executed

| Script | Result |
|---|---|
| `qa/check_chain.py` | Alembic chain intact, **len = 75**, head `0105` |
| `qa/routes.py` | **148 routes, 148 unique** |
| `qa/sec_audit.py` | static scan (hardcoded secrets, f-string SQL, auth bypass, float money, lookahead, bare except) — findings pre-existing |
| `qa/verify_sma.py` | `SMA_PATCH_VERIFIED` |
| `qa/verify_numeric.py` | live DB: `signals 4`, `paper_trades 3028`, `paper_equity_history 11`, `alert_history 6516`; exact-decimal sanity OK |
| `qa/quotes_dup_check.py` | live DB: `quotes` = **3 409 314 rows, 0 duplicate groups**, unique constraint `uq_quotes_symbol_date_timeframe` present |
| `qa/concurrency_proof.py 30` | live DB: **30 parallel workers → exactly 1 alert fired, 1 history row** (`RACE_OK_SINGLE`) |

Not run: `qa/crawl.py` and `qa/probe.py` (superseded by `qa/ui_crawl.mjs`, which drives all 148 routes against a production build rather than `next dev` on :3000), and `qa/check_upgrade_log.py` (re-reads a static log captured earlier).

---

## 9. C3 — model inference: the audit's premise was wrong, the outcome is still 0

The audit scored **C3 = 0** with the justification *"NOT TESTED (no model artifacts in repo)"*. **That premise is false**: `ml_artifacts/` contains **359** artifact directories across 9 families (`bayesian_ridge`, `catboost`, `extra_trees`, `hist_gradient_boosting`, `huber_regressor`, `lightgbm`, `random_forest`, `stacking_ensemble`, `xgboost`), each with `latest_path.txt`, `metadata.json` and versioned `v1-<hash>` directories.

`qa/c3_inference_check.py` actually loads every artifact and runs real inference → `reports/c3_inference_results.json`:

**0 / 359 artifacts are loadable.** Two independent defects stack up:

1. **The production loader cannot even read the files.** Every `model_pipeline.pkl` is **zlib-compressed** (magic `78 9c`), but `ml/model_loader.py:_load_from_disk` does a bare `pickle.load`. Result: `UnpicklingError: invalid load key, 'x'` on byte 0. A secondary blocker sits behind it: `metadata.json` records a `checksum`, not the `artifact_hash` that the loader's integrity gate (audit ML-007) requires, so the loader would raise *"refusing to unpickle unverified content"* even after the decompression is fixed.
2. **The decompressed pickle stream is itself malformed.** After `zlib.decompress` the payload starts with a valid protocol-4 pickle header (`80 04 95 …`) but is corrupt partway through:
   - 342 artifacts fail `UnpicklingError: STACK_GLOBAL requires str` — at offset ~1318 the stream pushes the module string `'dtype'` where `numpy` belongs, so `numpy.dtype` resolves with module and name swapped.
   - 17 `stacking_ensemble` artifacts fail `invalid load key, '\xNN'` — the stream is truncated mid-opcode.

`pickletools.dis` confirms the corruption is in the stored bytes, not in the environment: the opcode stream is well-formed up to the first bad memo reference and 11 KB of the 13 KB decompressed payload is never reached.

**C3 therefore stays 0.0 — but it is now a measured, root-caused 0 instead of an assumed one.** The ML models cannot be served today; retraining is required, and the artifact writer (compress + `artifact_hash` in metadata) and `ModelLoader` must agree before anything trained is usable.

---

## 10. Rescored §8 table

Formulas copied verbatim from §8. Anything not re-measured is **carried over** and labelled as such.

| id | Sub-component | Max | Baseline | Recheck | Basis |
|---|---|---:|---:|---:|---|
| A1 | Static nav + live-route contract | 15 | 12.20 | **12.20** | carried over — the audit's `phase*_*.py` scripts are not in this tree |
| A2 | Live rendering / blank / console | 15 | 0.00 | **14.90** | **measured** — 147/148 render OK; 0 blank, 0 runtime errors, 0 real console errors |
| B1 | Money representation | 8 | 0.94 | **0.94** | carried over — P1 money work untouched |
| B2 | Calculation correctness | 12 | 8.54 | **8.54** | carried over |
| B3 | Iranian-market rules | 5 | 0.83 | **0.83** | carried over |
| C1 | Backtest engine + metrics | 15 | 10.94 | **10.94** | carried over |
| C2 | ML calibration + importability | 6 | 5.68 | **5.88** | importability **measured** 117/117 = 1.000; calibration carried over |
| C3 | Inference on trained models | 4 | 0.00 | **0.00** | **measured** — 0/359 artifacts loadable (was "not tested") |
| D1 | Idempotency / race / error semantics | 8 | 3.20 | **1.60** | 1 of 5 critical invariants executed live and passed; the other 4 unexecuted score 0 by design |
| D2 | Build & dependency integrity | 6 | 0.00 | **6.00** | **measured** — 430-pin lock + 8/8 images build + 8/8 containers start with no `ModuleNotFoundError` |
| D3 | Code resilience | 6 | 5.88 | **5.92** | unit pass rate **measured** 98.32 % (was 97.05 %); `import_ok` carried over |
| | **Total** | 100 | **48.20** | **67.76** | **+19.56** |

Category totals: UI & Navigation **27.10/30** · Financial Precision **10.31/25** · Backtest & ML **16.83/25** · Concurrency & Resilience **13.52/20**.

> **D1 is scored down, not up.** The audit credited 3.2 on partial evidence; this run executed exactly one of the five critical concurrency invariants and it passed. F03 (no idempotency / row lock / cash check in paper trading) and F28 (global alerts) were not remediated, so the concurrency posture is not better than audited — it is merely *now partly proven*.

Machine-readable output: `reports/readiness_score_recheck.json`. Regenerate with `venv/Scripts/python.exe qa/rescore_readiness.py`.

---

## 11. New findings raised by this remediation

| # | Severity | Finding | Evidence |
|---|---|---|---|
| N1 | **P0 (fixed)** | Docker images never contained their own dependencies: builder wrote `/root/.local`, runtime user resolved `/app/.local`. Build succeeded, container died on first import. | 8 × `docker run`, `reports/docker_boot_matrix.txt` |
| N2 | **P0 (fixed)** | `python-multipart` undeclared → `apps/api/app.py` raised at import, killing all 11 upload endpoints. | clean-venv import test |
| N3 | **P1** | `ml/model_loader.py` reads artifacts with a bare `pickle.load` but every artifact is zlib-compressed; and `metadata.json` has `checksum` while the integrity gate requires `artifact_hash`. **No trained model can be loaded in production, by any path.** | `reports/c3_inference_results.json` |
| N4 | **P1** | All 359 on-disk model artifacts are structurally corrupt pickles (342 `STACK_GLOBAL requires str`, 17 truncated). Retraining required. | `qa/c3_inference_check.py` |
| N5 | **P2** | Base `Dockerfile` startup dies with `asyncpg … invalid DSN: scheme is expected to be either "postgresql" or "postgres", got 'postgresql+asyncpg'` — raw asyncpg is handed a SQLAlchemy DSN. | container boot log |
| N6 | **P2** | `Dockerfile.golddesk` runs `apps.scheduler.app` as its entrypoint — likely the wrong module. | container boot log |
| N7 | **P2** | `scripts/build-with-heap.js` (`npm run build`) cannot spawn `node_modules/.bin/next` on Windows; and stale `.next/dev/types` breaks a rebuild. | build attempts |
| N8 | **P2** | `vitest run` at default parallelism OOMs at ~100 MB heap. | `npx vitest run` |
| N9 | **P2** | `tests/unit/test_brsapi_usage_recorder.py` (10 tests) hangs permanently; `pytest-timeout` fires but the process never exits. | `reports/pytest_chunks.txt` |
| N10 | **P2** | `new Date()` called during render in ~8 further client components — same bug class as the fixed `/gold/antigravity` #418. | `frontend/src/app/markets/gold-fx/page.tsx:89` et al. |

---

## 12. What is still open

The **20 P1 money/signal findings** from the audit are untouched and are what keeps the verdict at NO-GO:

- **Money as float** — F26 (1 276 float money fields vs 15 Decimal), F04 (BUY with no cash check → cash to −100 992 275), F05 (oversell / commission on requested quantity), F23 (close price silently falls back to entry price).
- **Wrong metrics** — F07 (an OPEN long booked as a loss of the whole notional), F08 (Calmar/Recovery always 0; Sortino uses std-of-losses with a 1.0 fallback), F09 (zero-NAV / NaN propagation; `mass_scanner` `ZeroDivisionError`), F11 (max-drawdown % divided by the final peak), F16 (options margin), F10, F25.
- **No idempotency / no ownership** — F03, F28, F22 (errors returned as HTTP 200 `{success:false}` in 140 places).
- **Signal correctness** — F20 (`fix_probability(NaN)` → 0.999), F24 (two coin-bubble implementations disagree 100× on thresholds), F15 (fabricated RSI warm-up; ATR is not True Range), F19 (screener sorts N/A as 0.0).
- **Execution realism** — F06 (MA-cross exits recompute size from current cash), F27 (fills at the signal bar's close plus slippage; no next-bar, no price-limit/queue).
- **Frontend contract** — F12 (64 frontend API calls with no live route), F14 (four unimportable packages), F13 (`.gitignore data/` hides source packages).

To reach the §9 gate the remaining work is not a re-score exercise: it is F03–F28 plus the §8 exit criteria 2–5 (shared metrics library, engine invariants, idempotency + `user_id` migration + openapi contract test, a clean crawl **with the backend up** and working ML inference).

---

## 13. Artifacts

| Path | Contents |
|---|---|
| `reports/readiness_score_recheck.json` | §8 rescore, per-component inputs |
| `reports/ui_crawl_results.json` / `ui_crawl_summary.json` | 148-route crawl, per-route metrics + verdict |
| `reports/screenshots/` | 148 PNG screenshots (9.7 MB) |
| `reports/pytest_chunks.txt` | per-batch pytest counts |
| `reports/c3_inference_results.json` | 359-artifact inference attempt, per-record outcome |
| `reports/docker_build_matrix.txt` | 8/8 image build results |
| `reports/docker_boot_matrix.txt` | 8/8 container start results |
| `requirements.lock` | 430 pinned dependencies (install with `--no-deps`) |
| `qa/build_all_images.sh`, `qa/boot_all_images.sh` | D2 build + start harness |
| `qa/ui_crawl.mjs`, `qa/run_ui_crawl.sh`, `qa/ui_crawl_classify.py`, `qa/routes.txt` | crawl harness |
| `qa/c3_inference_check.py` | model-artifact inference check |
| `qa/rescore_readiness.py` | §8 rescore |
| `qa/run_unit_tests.sh`, `qa/run_toplevel_tests.sh` | chunked pytest runners |