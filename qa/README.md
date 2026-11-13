# Compact, read-only QA reconstruction

This PR restores a **new, reproducible numerical QA bundle**, not the missing
artifacts of the earlier full-system audit. No previous pass rate, readiness
score, browser screenshot, or API execution is represented as fresh evidence.
The production application and the existing `reports/` Python package are
unchanged. Proposed application edits exist only as a `.diff` report.

## Fresh evidence (local date: 2026-10-03, Asia/Tehran)

Source tested: `f5d195a43eedd9727c053afa078e90958047ef9a`.

| Category | Cases | PASS | FAIL | ERROR |
|---|---:|---:|---:|---:|
| Backtest **accounting/analytics unit contracts** | 75 | 15 | 60 | 0 |
| ML feature causality/schema and shallow-model holdouts | 55 | 30 | 15 | 10 |
| Screener filters, sorting, RSI availability and cache refresh | 50 | 41 | 9 | 0 |
| Options margin/pricing, NAV, coin and FX calculations | 20 | 5 | 15 | 0 |
| **Total** | **200** | **91** | **99** | **10** |

Two independent processes produced the same economic/outcome digest:
`2fe2c1e30b100564f2ae9da95b18a74eb7a7af779d94aba886ee70b163ccad8f`.
Ten separate tests of the QA harness passed. All 12,187 original tracked files
matched their captured SHA-256 values. No IP connection was attempted.

**These are intentionally failing product-contract probes, not green tests or
200 end-to-end jobs.** The 10 `ERROR` cases reproduce the original
`TradeFeatures.compute` `KeyError('real_net_flow_ma{w}')`; they are not silently
counted as passes. Every result includes its case ID, parameter variant,
observations, elapsed time, and cumulative process peak RSS.

## Reproduce

Use Python 3.11 on Linux. Run from the repository root; dependencies and all
runtime state are confined to `qa/runtime/`:

```bash
python3 -m venv qa/runtime/.venv
qa/runtime/.venv/bin/pip install --no-cache-dir -r qa/audit/requirements.lock
PYTHONDONTWRITEBYTECODE=1 qa/runtime/.venv/bin/python -m unittest discover \
  -s qa/audit -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 qa/runtime/.venv/bin/python qa/audit/run.py \
  --output qa/audit/results.json
# The current original source produces exit 1: expected unresolved findings.
PYTHONDONTWRITEBYTECODE=1 qa/runtime/.venv/bin/python qa/audit/run.py \
  --output qa/audit/repeat.json
```

The runner blocks **all IPv4/IPv6 socket connects, including loopback**, before
application imports. It uses frozen synthetic fixtures and explicit RNG seeds;
no database, Redis, browser, API, account, order service or market feed is used.
It captures original tracked-file hashes **before** application imports and
compares them afterward. It allows evidence output only inside `qa/`. QA files
and the three named new report artifacts are excluded from the source baseline;
the repository's pre-existing `reports/` package is included.

Exit `0`: all tested contracts hold. Exit `1`: recorded contract failures or
runtime errors. Exit `2`: a detected infrastructure, network-policy,
immutability or CLI failure. Missing bootstrap dependencies also mean an
infrastructure failure; do not interpret a run without a fresh JSON result as
product evidence. Logs should be redirected into `qa/logs/` if retained.

The wall-clock/peak-RSS fields are diagnostic measurements, not memory-leak or
load-test certifications. `ru_maxrss` is cumulative process peak memory on
Linux, not the allocation of the individual case. Timings exclude interpreter
startup and imports. The repeatability digest excludes timestamps, timings,
RSS and tracebacks but includes assertions, economic observations and outcomes.

## Evidence and review

- `audit/run.py`: the 200-case runner and deterministic fixture generators.
- `audit/test_harness.py`: 10 harness tests, separate from product outcomes.
- `audit/results.json`, `audit/repeat.json`: fresh per-case evidence.
- `audit/verification.json`: repeatability and original-file integrity proof.
- `audit/harness_validation.txt`: harness test output.
- `audit/requirements.lock`: exact installed Python dependency versions.
- `audit/context.json`: source/runtime provenance and reconstruction scope.
- `../reports/QA_AUDIT_2026-10-03.md`: nine-section audit report and findings.
- `../reports/QA_READINESS_2026-10-03.json`: **NO-GO**, with numeric score withheld.
- `../reports/QA_PROPOSED_FIXES_2026-10-03.diff`: review-only partial remediation.

Regenerate proposed patches **without applying them**:

```bash
python3 qa/audit/propose_fixes.py
git apply --check reports/QA_PROPOSED_FIXES_2026-10-03.diff
```

`git apply --check` only verifies patch context. It does **not** validate proposed
behavior. The sketches are incomplete (including deterministic-case Greeks,
cache serialization and margin policies) and were never applied to source.

## Important scope limits

This does not recreate full-app authentication/navigation at either viewport,
HTTP readiness, route/API/WS/SSE discovery, screenshots, chart-library lifecycle
or timeframe switching, the 15-alert lifecycle, all six runner engines,
transactional concurrency/idempotency tests, production ML weights, universe-
wide screener workloads, current exchange/regulatory rules, or the previous
30-risk catalogue. All remain unqualified by this bundle. There is no recovered
historical readiness score. Direct bookkeeping assertions about invalid fills,
capital admission and extreme `1e16` IRR arithmetic are conservative local
contracts: real upstream guards/account limits have not been audited here.

Future work should first correct the feature-builder crash, causal filling,
drawdown and margin/calculator defects in a separately authorized source-change
PR, then rerun the original full-system acceptance plan. No real trading or
release approval follows from this QA-only PR.

## Cleanup

No external services or persistent application state were created. Generated
venvs, runtime manifests, caches and application work directories are ignored
and are not part of the PR. After execution they may be removed with:

```bash
rm -rf qa/runtime
```

Do not remove the repository's existing `reports/` source files. Keep only the
intentional `qa/` bundle and three new `reports/QA_*_2026-10-03.*` deliverables in
Git; never add dependencies, runtime databases or browser binaries.
