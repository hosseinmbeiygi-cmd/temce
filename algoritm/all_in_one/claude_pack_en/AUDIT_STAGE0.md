# AUDIT_STAGE0 — Audit summary of backtest and ML for Claude Code

> Source: `audit/REPORT_FULL.md` and `audit/findings_new.csv` (49 findings). Audit runs: 2026-10-09 and 2026-10-10 on the owner's machine (Windows, Python 3.11.9, local PostgreSQL; SELECT only).
> **Warning:** the audit was performed by a different model. Re-verify every finding before acting on it (open file:line, run a test). Labels: `[RE]` read+executed, `[R]` read only.

## 1. Verdict

**Unreliable.** Reason: the measurement instrument is broken; it has NOT been shown that the signal is worthless. We still **do not know whether ML has an edge**.

Three main reasons:
1. Measurement: sells are sized from cash; MDD equals the price's MDD; three engines give contradictory results; fills at the decision bar's close; Vectorized has no costs and no look-ahead guard.
2. ML: wrong artifact path ⇒ zero predictions ⇒ zero trades; the existing models (359) are unvalidated.
3. Data/controls: `gregorian_date` is a sync date; raw prices; cash dividends not recorded; survivorship; gate 9 is fail-open.

## 2. Solid findings (all [RE] unless noted)

### Measurement (backtest)
| ID | Finding | File (path from audit) | Severity |
|---|---|---|---|
| A-03 | The sell branch of `MlSignalStrategy` sizes quantity from cash; the position is never fully closed (fills: 315,678 → 26,054 → … → 1 share) | `backtesting/strategies/ml_based/ml_signal_strategy.py`, `backtesting/sizing.py`, `backtesting/strategies/base.py` | critical |
| A-04 | MDD 38.73% equals the price's own MDD (38.7309) in all 5 experiments; cause: the strategy is always ~90% in the market (the MDD formula itself is not necessarily wrong) | `backtesting/metrics/drawdown_metrics.py`, `services/backtest_service.py` | critical |
| A-06 | Three engines, one signal: Simulator +28.25%, Vectorized gross −20.94% | `services/backtest_framework.py`, `services/signal_backtest_engine.py` | critical |
| B-01 | The "random baseline" in Simulator is effectively buy-and-hold (0 of 200 seeds negative) | `backtesting/sizing.py`, `ml_signal_strategy.py` | critical |
| B-04/B-05 | Look-ahead is measurable in Vectorized (+264% to +772% gross) and there is no signal-origin guard; the proposed test fails | `services/backtest_framework.py` | critical/high |
| C-01 | `BacktestSimulator` fills at the same bar's close; `BacktestEngine` at the next bar's open | `backtesting/engine/simulator.py`, `backtesting/engine/backtest_engine.py` | critical [R] |
| A-02/A-05/G-04 | First-buy slippage hits the 150 bps cap (ADV fallback = 1,000,000); resolved ADV ~8.4e9 (suspicious); total cost ~constant because gross notional is ~constant and 64% of it is in a single fill | `backtesting/engine/broker.py`, `backtesting/engine/adv.py` | high |
| A-07/C9 | `SignalBacktestEngine`: fixed cost rate `0.003` vs SSOT round trip `0.0147` (4.9x too low) | `services/signal_backtest_engine.py` | high |
| D-04/C-08 | `profit_factor` is `inf` in one engine and floored at 1.0 in another; fake +786% trade; `json.dumps` breaks | `services/signal_backtest_engine.py`, `backtesting/analytics/engine.py` | high |
| C7/C4 | `AttributeError: 'MarketSignal' ... 'to_dict'`; `'BacktestRun' ... 'current_value'` | `apps/api/endpoints/signal_insights.py:120`, `repositories/backtest_repository.py` | critical/medium |
| E-04 | `run_backtest` returns "success" on empty data (flaky) | `services/backtest_service.py` | medium |

### Market rules and costs
| ID | Finding | File | Severity |
|---|---|---|---|
| A-01 | **Correction of an earlier claim:** in `BacktestSimulator` commission + clearing fee + sell tax ARE applied (buy 0.00485, sell 0.00985) | `backtesting/engine/broker.py`, `backtesting/costs/iran_costs.py` | info |
| C-02 | `IRAN_LIMIT_HISTORY` is time-aware but dead code; the 2024 value = `0.03` with the comment "example" (placeholder) | `backtesting/data/price_limits.py` | high [R] |
| C-03 | `rule_versioning` (tick/T+2/session) exists but is not wired into the backtest | `backtesting/market/rule_versioning.py` | medium [R] |
| C2 | Fees/settlement/tax/slippage/ADV/tick/T+2/hours are fixed and time-independent | `domain/trading/iran_costs.py` and the above | high |

### Data
| ID | Finding | Severity |
|---|---|---|
| G-01/G-02 | `gregorian_date`/`shamsi_date` in `brsapi_historical_daily` are sync dates; several trade dates share one `gregorian_date`; `_fetch_future_prices` filters on it (consistent with the fake trade, but the direct link is not proven) | critical |
| C-04 | The backtest reads **raw** prices; `vw_daily_history_adjusted` and `daily_adjust_factors` (621,818 rows) are unused | high |
| C-05/G-05 | `corporate_action_events` has only `capital_increase` (586 rows / 145 symbols), all with `dps=0`; `corporate_actions` has zero rows ⇒ cash dividends are not recorded | high |
| G-03 | `brsapi_historical_daily` is not a hypertable; no knowledge_time; upsert overwrites the past; not bitemporal | high |
| C-08 | Survivorship: symbols in the last 90 days = whole history (2407); the `symbols` table has only 511 rows | high |
| — | Khodro had no corporate event in 2024 (last 2020, next 2025-04-22), so the Khodro 2024 experiments are not contaminated from that angle | info |

### ML
| ID | Finding | Severity |
|---|---|---|
| F-01 | 359 models in `ml_artifacts/`; `ArtifactManager` takes the root `data/models` ⇒ `FileNotFoundError` ⇒ `predicted_change_pct=0.0` ⇒ zero trades (`services/backtest_service.py::_inject_ml_predictions`, `ml/artifacts.py`) | critical |
| F-02 | Metadata of **one** sample model (`xgboost_خودرو`): directional accuracy 0.183, R² −0.54; the other 358 were not examined | high |
| F-04 | The canary "tomorrow's return" was silently accepted (IC=0.999); there is no leakage-detection gate | high |
| F-05 | Label shuffle ⇒ IC≈0 (positive) | positive |
| C-06 | ML label uses `close[t]` but execution is at `open[t+1]`; locks/suspensions are not handled in labels (`ml/datasets/labeling.py`) | high |
| C-07 | Plain `GridSearchCV(cv=5)` on a time series; no purge/embargo; `WalkForwardEngine.split` has no embargo; DSR/PBO implemented but unused; n_trials not recorded (`ml/models/sweeper.py`, `services/backtest_framework.py`) | high |
| C-09/C-10 | Two HIDDEN_ERRORS bugs (`float_turnover_pct`, `net_inst_ratio`) are fixed; auto-retrain does not replace the model blindly (`_min_accuracy_gain=0.02`) | positive |
| F-03 | Ridge experiment (5 symbols): cross-sectional RankIC with N=5 is meaningless; **ignore it** | — |

### Controls and tests
| ID | Finding | Severity |
|---|---|---|
| D-03 | Gate 9 in `quant_signal_orchestrator.py:1253-1261` is fail-OPEN, while `AUDIT_REPORT.md` recorded "fail-closed fixed" [R] | critical |
| D-02 | Numbers in `docs/quant-signal-goal-assessment.md` are stale: direction accuracy 36.7%→38.43%; return per signal −4.0%→−3.73%; paper win rate 28.43% and paper return −15.25% were reproduced | medium |
| E-01..E-05 | Of 175 pytest failures, most are environmental (401/429); `test_phase_engine` has 6 real failures; validity tests (random≈0, label shuffle, feature canary, ledger conservation) **do not exist** | high |
| H-01..H-04 | 6 sensitive keys on disk (`.env`, `.env.bak.*`, `.env.production`; not in git); ToS of scraped sources unknown; git-history scan not done | medium |

## 3. Proposed keep / rewrite / suspend table (based on the audit; the owner approves)

| Module | Decision | Reason |
|---|---|---|
| `backtesting/engine/backtest_engine.py` (`BacktestEngine`) | **Keep** (proposed reference) | Next-open execution + look-ahead test; **full code not read**; run a parity test first |
| `backtesting/engine/simulator.py`, `broker.py` | **Rewrite** execution/ADV parts | Fills at close; ADV fallback; keep the `cost_model` core |
| `backtesting/costs/iran_costs.py`, `domain/trading/iran_costs.py` | **Keep + wire to `rule_at`** | Formula is right; rates are time-independent |
| `services/backtest_framework.py` (`VectorizedBacktest`, CPCV, `StatisticalValidator`) | **Rewrite** Vectorized; keep CPCV/DSR | No costs/guard; DSR unused |
| `services/signal_backtest_engine.py` | **Rewrite** | Fixed rate, sync column, `profit_factor` |
| `backtesting/strategies/ml_based/ml_signal_strategy.py` | **Rewrite** the sell branch | A-03 |
| `backtesting/sizing.py`, `strategies/base.py` | **Keep + fix** (sell from the position) | — |
| `backtesting/metrics/drawdown_metrics.py` | **Keep** + add a relative report | Formula probably right |
| `backtesting/data/price_limits.py`, `market/rule_versioning.py` | **Keep structure, rewrite data, wire in, migrate to the `rules` table** | Dead code/placeholder |
| `services/backtest_service.py` | **Rewrite** data loading, ML injection, empty-data error | C-04, F-01, E-04 |
| `ml/artifacts.py` + `ml_artifacts/` (359 models) | **Fix path; models `UNVERIFIED`/archived** | F-01, F-02 |
| `ml/datasets/labeling.py` | **Rewrite** | C-06 |
| `ml/models/sweeper.py` | **Rewrite** (purged/CPCV + record n_trials) | C-07 |
| `services/feature_engine.py` | **Keep + knowledge_time + leakage guard + tests** | F-04, C5 |
| `services/auto_retrain_pipeline.py` | **Keep + shadow/paper stage** | The 0.02 guard is good |
| `services/quant_signal_orchestrator.py` (gate 9) | **Fix** fail-closed | D-03 |
| ensemble, calibrator, regime, 10 gates, agent-based, genetic (`cascade_engine`) | **Suspend** until a baseline passes | Unvalidated; part C8 incomplete |
| `brsapi_historical_daily` and related tables | **Add** `trade_date`, `first_seen_at`; do not drop columns | G-01, G-03 |
| `fix_critical_errors.py`, `fix_test_syntax.py`, `gen_all.py`, `mkpages.py`, `funds-all-code.txt`, four report folders | **Archive/delete** after owner approval (and import confirmation) | I-01..I-03; usage by import not confirmed |

## 4. Not examined (must be done in the steps)

- `knowledge_time` of real/legal, fundamental, Codal, NAV features; daily cross-sectional normalization and winsorization; what regime/ensemble/calibrator are fitted on.
- Named list of delisted symbols; a rerun of the whole suite; git secret scan; 15 open PRs and 1 issue; a real run of `SignalBacktestEngine` with SSOT costs.
- **Iranian-market items the audit did not cover** (`SPEC_IRAN_MARKET.md`): `fillable_rate` and the queue/lock model; whether Vectorized rejects negative (short) signals; `lock_up_today/lock_streak` and censored returns; cash dividends; Jalali calendar/unusual closures and horizon counting; `regime_epoch`/`policy_events`; `N_eff`; three measures; systemic exit risk (joint-lock); free float/market maker/IPO; time zone/DST; Persian text normalization of symbols.

## 5. Open questions for the owner

1. Approve the table above (especially the reference engine, ADR-001).
2. Is `gregorian_date` intentionally the sync time or an ingest bug? (ADR-002)
3. Was a model ever trained deliberately and stored only in `ml_artifacts/`? What was the purpose of those 359 models?
4. Are the official rule sources (announcements) available to you? From what period?
5. What about `acceptance.yaml` and the reference rates (FX, risk-free, inflation)?
6. Does `own_order_log` (your own real orders) exist? (needed for the queue/exit step)
7. Root-level modules (`fix_*.py` …) and report folders: delete or archive?
