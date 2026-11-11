# REMEDIATION_PLAN — Staged remediation program (R0 to R7)

> Basis: `AUDIT_STAGE0.md` + `ARCHITECTURE.md` sections 16–17 (Strangler pattern, gates) + `SPEC_BACKTEST.md` + `SPEC_IRAN_MARKET.md`.
> Rule: until the previous step's gate passes and the owner approves, do not start the next step. Every step: "tests first, then fixes"; changes to existing files only as patches.
> The order is deliberately "measurement > data > rules > validation > ML": until measurement is right, training a model is meaningless.

## R0 — Freeze and baseline
**Goal:** record the current "known-bad" state for later comparison.
- `git tag pre-remediation`; confirm the DB backup.
- Rerun the baseline: the ml_signal path (5 symbols, 2024), experiments A to D on Khodro, full `pytest` with failures categorized (environmental / logical / stale). Outputs in `experiments/R0/` with a `run_manifest`.
- Re-verify the 10 critical findings (file:line + a small run). Report every mismatch with the audit.
- **Gate:** `experiments/R0/` reproducible (two runs ⇒ identical output); list of re-verifications; owner approves.

## R1 — Measurement correctness (backtest code)
**Inputs:** A-03, A-04, A-06, A-07, B-01, B-04, B-05, C-01, A-02/G-04, D-04, C7, C4, E-04.
| # | Task | Acceptance test |
|---|---|---|
| R1.1 | Sell sizing from the position size (patch `ml_signal_strategy.py`/`sizing.py`) | After a sell signal the position = 0 (or per an explicit rule); fills do not decay to 1 share |
| R1.2 | Execution rule: an order decided at t fills at the first allowed phase after t; no fill at the decision bar's price | Property test: `fill_time > decision_time`; leakage test with a look-ahead strategy |
| R1.3 | Reference-engine decision (ADR-001) + parity test between the reference and Simulator/Vectorized/SignalBacktestEngine on the simplest strategies | Results equal within a recorded tolerance; otherwise the cause is documented |
| R1.4 | One cost model for all engines (currently fixed SSOT; R3 wires `rule_at`); Vectorized takes a cost parameter; SignalBacktestEngine uses SSOT | Ratio of SignalBacktestEngine's rate to SSOT = 1.0 |
| R1.5 | ADV: pre-warm in direct runs; investigate the ~8.4e9 value (depends on R2) | No fallback warning in logs; Khodro's ADV matches a hand computation from `trade_volume` |
| R1.6 | Vectorized rejects negative signals (`NO_SHORT_ALLOWED`) unless `short_allowed`; signal-origin (truncation) guard | `audit_out/_proposed_tests/test_vectorized_signal_origin.py` passes; NO_SHORT test |
| R1.7 | Consistent, JSON-safe `profit_factor`; `to_dict`; `current_value`; empty data ⇒ explicit failure | `json.dumps` without `allow_nan`; endpoint 200 with `total_signals > 0` (if signals exist) |
| R1.8 | Report MDD relative to buy-and-hold in addition to absolute | MDD of two strategies with different behavior differs |
**R1 gate:** the `SPEC_BACKTEST` section 13 invariants that apply here (1, 3, 4, 5, 6, 7, 11, 12) have tests and are green; owner's hand-computed golden; before/after comparison on R0.

## R2 — Data correctness
**Inputs:** G-01, G-02, G-03, C-04, C-05, C-08, G-04 + `SPEC_DATA_SCHEMAS.md`.
- A real `trade_date` (Jalali→Gregorian conversion tested, round trip for all years including leap years) and `first_seen_at` (non-overwritable). **Migrations are proposed SQL only**; the owner runs them.
- All time filters (`_fetch_future_prices`, `AdvResolver`) use `trade_date`.
- Adjusted loading (`adjusted_price_reader`); portfolio-value continuity test at ex-date; reconcile with the official/second-source series (list the differences).
- Cash dividends: find the data source (Codal/existing tables); if absent, the dividend-adjustment module is `suspended` and results carry the label "no dividend adjustment".
- `symbol_history`/dated universe; count and list delisted symbols; test `last_90d < all_time`.
- DQ: low≤open,close≤high, volume/value, price within the rule's limit (after R3), calendar gaps, duplicates. A DQ report, never hiding failures.
**R2 gate:** DQ report; adjustment-continuity test; date-conversion test; hash reproduction.

## R3 — Time-dependent rules table and epochs
**Inputs:** C2, C-02, C-03 + `rules/RULES_COLLECTION_GUIDE.md` + `ARCHITECTURE` sections 21–23.
- Implement `rules` and `rule_at(key, scope, date)` (tests: overlap ⇒ error; boundary dates; bitemporal).
- Wire `price_limits`/`rule_versioning` to the table; remove the placeholder 0.03; replace constants in `broker.py`/`iran_costs.py` with `rule_at` (patch).
- **The owner supplies rule values from official announcements**; Claude Code only builds the structure and tests (`TODO(source)` for rows without a source).
- Data-reconciliation test: the real max/min daily change must be consistent with the limit registered for that day.
- `regime_epoch` in data and features; `policy_events`; `market_status` (including unusual closures and halts) and the scenario test "N-month closure with an open position".
**R3 gate:** no rule numbers in code (automated grep); stage 1 tests of the `PHASES_AND_PROMPTS` matrix; every result that depends on a source-less rule is "unreliable".

## R4 — Validation harness and standard report
**Inputs:** E-05, B-01..B-07 + `BASELINES.md` + `SPEC_IRAN_MARKET` sections 2, 3, 7, 14.
- The 7 tests proposed by the audit (random≈0/negative, look-ahead rejected, label shuffle, feature canary, universe with delisted, cost parity, ledger conservation) in `tests/validity/`.
- Baselines per `BASELINES.md` (matched-exposure random 200 seeds, detrended, aligned look-ahead, shift).
- **Standard report** (one template): three measures; benchmarks; beta; `N_eff`; `fillable_rate` (UNCALIBRATED until R7); `n_epochs`; `n_trials`; DSR/PBO; leave-one-epoch-out; `run_manifest`.
**R4 gate:** every positive and negative control shows the expected behavior; the standard report is produced on a sample run.

## R5 — ML (only after R1 to R4)
**Inputs:** F-01, F-02, F-04, C-06, C-07 + `SPEC_ML.md`.
- Fix the artifact path (`ArtifactManager`); the 359 models are `UNVERIFIED`; audit their metadata as a table, without relying on it.
- Labels from executable prices (`open[t+1]`→`open[t+1+h]` with costs), handling of locks/suspensions (`untradable`/T4).
- Walk-forward with purge and embargo ≥ horizon; record `n_trials`; DSR/PBO in the report; single-look hold-out.
- Leakage guard in the feature pipeline (the canary must be detected); `knowledge_time` for real/legal, fundamental, Codal, NAV features.
- One simple baseline (Ridge/LightGBM) over several years and symbols; compare with BL-1..BL-3 after costs; acceptance only via `acceptance.yaml`.
**R5 gate:** `SPEC_ML` section 10 (shift, canary, shuffle, audits); an honest result (even if weak); hold-out recorded.

## R6 — Tests, controls and cleanup
- 175 failures: a table of file/count/group/cause; auth fixture (401); stale tests (`test_phase_engine`); flaky ones.
- Gate 9 fail-closed (D-03) + test.
- Docs: update README counts; date-stamp `docs/quant-signal-goal-assessment.md`; align `AUDIT_REPORT.md` with real behavior.
- Git-history secret scan; ToS document for scraped sources; archive root scripts and report folders (with approval).

## R7 — Queue, locks and exit model (stage 4 of `PHASES_AND_PROMPTS`)
**Prerequisite:** depth/queue data or `own_order_log`. Without it: entry on a locked side without queue data ⇒ `unfillable`; results `UNCALIBRATED`; the calibration module is `suspended`.
- `queue_v1`, `days_to_exit`, joint-lock stress, `market_lock_share_daily`, `margin_call_unmeetable` (only if derivatives are active).
- **Gate:** property tests (`filled ≤ qty`, no fill before `t_submit`), calibration with `own_order_log`.

## Modules `suspended` until further notice
ensemble/voting, calibrator, regime, the 10-gate engine, agent-based, genetic algorithm, auto-retrain with direct replacement, any deep model, derivatives/bonds/funds/commodities (until data marked `none/unknown` in the `SPEC_DATA_SOURCES` coverage matrix reaches `partial/full`).
