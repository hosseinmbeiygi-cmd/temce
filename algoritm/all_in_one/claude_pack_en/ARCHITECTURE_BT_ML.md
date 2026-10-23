# ARCHITECTURE_BT_ML — Complete architecture of the backtest and ML layer (Iranian market)

> Depends on: `ARCHITECTURE.md`, `SPEC_BACKTEST.md`, `SPEC_ML.md`, `SPEC_IRAN_MARKET.md`, `SPEC_VALUATION.md`, `CLAUDE.md`.
> On conflict: `CLAUDE.md` > `SPEC_*` > `ARCHITECTURE.md` > this document. No legal/regulatory number or acceptance threshold appears here (everything comes from `rule_at()` and `acceptance.yaml`).
> Every "why" refers to an audit finding (`AUDIT_STAGE0.md`) or a SPEC section.

---

## 0. Design principles (non-negotiable)

1. **One reference path, one cost model.** Only one engine produces a "reportable number"; the fast path is screening only and has costs and guards. *(Why: three engines with contradictory results, A-06)*
2. **Time before everything.** Every data read has `knowledge_time ≤ decision_time`; every execution is after `decision_time`. *(B-04, C-01)*
3. **Rules are data.** No market number in code; only `rule_at(key, scope, date)`. A rule without a source is confidence D and lowers the result's trust. *(C-02, C2)*
4. **Long-only by default.** A sell order without a position is rejected; a "bearish signal" = exit/reduce weight. *(`SPEC_IRAN_MARKET` 1)*
5. **Executability is a first-class concept.** `fillable_rate`, `unfillable`, `days_to_exit` are in every result's output. *(locks/queues)*
6. **Measurement is verified independently of the strategy.** Every engine/report is validated with a positive control (aligned look-ahead) and a negative control (matched-exposure random) before any strategy result is trusted. *(B-01)*
7. **ML only consumes correct data and engine.** A model is trained after R1–R4; acceptance only via `acceptance.yaml`. *(F-01, F-02)*
8. **Every result has a "trust grade"** computed mechanically from gates (section 10); a result without a grade is not reported.
9. **Three measures and benchmarks** for every result: nominal, real, USD. *(inflation/FX)*
10. **Independent samples are few.** `N_eff`, `n_epochs`, leave-one-epoch-out are mandatory. *(`SPEC_IRAN_MARKET` 14)*
11. **Reproducibility.** A `run_manifest` for every run; two identical runs ⇒ bit-identical output.
12. **Suspend instead of guess.** Data `none/unknown` ⇒ the module is `suspended`; substitute data/rules are never invented.

---

## 1. Overview

```
 ┌───────────── Sources ───────────┐
 │ prices, real/legal, corp actions,│
 │ Codal, NAV, FX/coin/ounce, depth │
 └──────────────┬──────────────────┘
                ▼
      Ingestion → raw → clean → adjusted → curated            (data layer, section 3)
                │                │
                │        PIT Store (bitemporal, knowledge_time)
                ▼                ▼
   ┌──────────────────┐   ┌──────────────────┐   ┌───────────────────┐
   │ Rules / Calendar │   │  Feature Store   │   │  Event Store      │
   │ rule_at, epochs  │   │  PIT, versioned  │   │  (Codal/news)     │
   └────────┬─────────┘   └────────┬─────────┘   └─────────┬─────────┘
            │                      ▼                       │
            │            Label Factory (executable) ◄──────┘
            │                      ▼
            │              Dataset Builder (PIT universe, purge/embargo)
            │                      ▼
            │              Model Zoo + Training Orchestrator + Trial Registry
            │                      ▼
            │              Evaluation (IC/AUC/deciles) + Leakage Guards
            │                      ▼
            │                  Signals  (scores, probabilities, meta-label)
            ▼                      ▼
   ┌────────────────────────────────────────────────────────────────┐
   │  Portfolio & Risk (allocation, constraints, stops, joint-lock stress) │
   └───────────────────────────────┬────────────────────────────────┘
                                   ▼  Orders
   ┌────────────────────────────────────────────────────────────────┐
   │  Reference engine (event-driven kernel)                         │
   │  Clock/Phases → OrderManager → ExecutionModel → Ledger          │
   │  CorporateActionProcessor · CostModel · ExitRisk · MTM          │
   └───────────────────────────────┬────────────────────────────────┘
                                   ▼
   Metrics → Validation (DSR/PBO/bootstrap/stress) → Report → Registry
                                   ▼
   Trust Grade  →  shadow → paper → live_small → live  (lifecycle)
```

**Fast path:** sits only between Signals and Metrics, with the same CostModel and guards; its output is never a final report (section 5.8).

---

## 2. Time and event core

### 2.1 Clock and phases
- The simulation clock for each `(market, segment)` takes its phases from `rule_at('session_phases')`: `pre_open → opening_auction → continuous → post_close → settlement_run → eod_mark`.
- Event: `(ts, priority, seq, type, payload)`; ordering by `(ts, priority, seq)`, fixed and deterministic.
- `market_status(date, segment) ∈ {open, closed_holiday, closed_unscheduled, halted_symbol}`; an unscheduled closure is a first-class status.

### 2.2 Three times
| Name | Definition |
|---|---|
| `decision_time` | the moment all required data with `knowledge_time ≤ decision_time` is available |
| `earliest_exec_time` | the first allowed execution phase **after** `decision_time + delay`; forbidden within the decision bar/day |
| `settle_time` | `add_business_days(trade_date, rule_at('settlement_days'))` with that market's calendar; in an unusual closure, the first business day after reopening |

### 2.3 Time guard
A `TimeGuard` in the data-access layer: every `get(dataset, asof)` returns no record with `knowledge_time > asof`; an attempt to read the future is a `LookAheadError` (not a warning). This guard is mandatory for **all paths**, including the fast path and feature/label building.

---

## 3. Data layer for backtest and ML

### 3.1 PIT Store
- One interface: `store.read(dataset, instrument_ids, start, end, asof)`; output carries flags `knowledge_time_assumed`, `stale`, `dq_flag`.
- Layers: `raw → clean → adjusted → curated`; the backtest sees only `curated`.
- **Trade date (`trade_date`) is separate from the ingest date.** No time filter uses an ingest column. *(G-01, G-02)*
- **Adjustment:** factor from `corporate_actions` (including cash dividends); the default consumer reads the **adjusted** series; the raw series is only for nominal valuation/execution and only on explicit request. *(C-04, C-05)*
- **PIT universe:** `universe_log(date, instrument_id, in_universe, reason)` including delisted/renamed symbols; the liquidity filter uses data up to T. *(C-08)*

### 3.2 DQ gate
Every dataset has a DQ Score; the backtest warns/stops on data below the threshold. Checks: low≤open,close≤high, price within the `rule_at` limit of that day, calendar gaps, a holiday with trades, ex-date drop vs the dividend amount, difference against a second source.

### 3.3 Coverage matrix and suspension
The `SPEC_DATA_SOURCES` matrix is the source of truth: any module depending on a `none/unknown` dataset automatically gets `status: suspended` with a reason in the `run_manifest`.

---

## 4. Rules, epochs and trust

- `rules(rule_key, scope, value, effective_from, effective_to, source_ref, confidence, knowledge_time)`; the only access: `rule_at(key, scope, date)`; overlapping intervals ⇒ error.
- **Scope resolution:** `symbol > segment > market > global`; exceptions (base market, funds, market-maker symbols) are explicit rows.
- **`regime_epoch`:** every major rule change (price limit, base volume, hours, order cap, long closure) is a new epoch; the epoch id is attached to data/features/labels/reports.
- `policy_events` as structured events with a publication time.
- **Effect on trust:** `run_manifest.rules_confidence_min` = the lowest confidence level among the rules used. Any confidence-D rule ⇒ the "rules" gate in section 10 fails.
- **Reconciliation test:** the real daily change of each symbol must be consistent with that day's registered limit; inconsistency means a table error or an unknown exception.

---

## 5. Reference backtest engine

### 5.1 Components
| Component | Job | Input ⇒ Output |
|---|---|---|
| `Clock` | phases and event order | calendar + `rule_at` ⇒ events |
| `MarketState` | allowed prices, lock/halt/queue state (as far as data allows) | PIT Store ⇒ state at the moment |
| `OrderManager` | order lifecycle and validation | Order ⇒ ACCEPTED/REJECTED(reason) |
| `ExecutionModel` | fills (section 5.3) | Order + MarketState ⇒ Fills |
| `CostModel` | commission/tax/slippage/impact | Fill ⇒ itemized cost |
| `Ledger` | double entry, blocking, settlement, conservation | JournalEntries |
| `CorporateActionProcessor` | `ex_date` events before open | event table ⇒ change in position/cash/reference price |
| `ExitRisk` | `days_to_exit`, `exit_blocked_today`, sustained-sell-queue scenario | position + ADV ⇒ exit risk |
| `Valuator` | daily MTM with `valuation_price`, `stale` for halts | position + price ⇒ equity |
| `Recorder` | output tables and `run_manifest` | everything ⇒ Parquet |

### 5.2 Order lifecycle and rejections
`NEW → ACCEPTED → WORKING → PARTIALLY_FILLED → FILLED | CANCELLED | EXPIRED`, or `REJECTED(reason)`.
Rejection reasons: `MARKET_CLOSED, SYMBOL_HALTED, PRICE_OUTSIDE_LIMIT, BELOW_TICK, BAD_LOT, INSUFFICIENT_CASH, INSUFFICIENT_MARGIN, POSITION_LIMIT, ORDER_SIZE_LIMIT, NOT_TRADABLE_IN_PHASE, NO_SHORT_ALLOWED`.
**Sell size** is always computed from the open position (`ledger.position(instr)`), not from cash. *(A-03)*

### 5.3 Fill models
| Model | Use | Behavior |
|---|---|---|
| `idealized` | unit tests only; label `NOT_REALISTIC` | full fill |
| `conservative_ohlc` | default with daily data | a buy limit fills if `low ≤ limit` **and** the day is not locked on the buy side; quantity ≤ `participation_cap × volume`; price worse than VWAP with slippage |
| `queue_v1` | with depth/queue data | `filled(t) = clip(V_exec(t) − Q_ahead, 0, qty)`; without queue data: entry on a locked side = `unfillable` |
| `auction` | observation only until a rule is confirmed | orders are not executed in the auction |

Invariants:
- **No fill at the decision bar's price.** *(C-01)*
- **Without queue data and on the locked side ⇒ `unfillable`**, not filled, not "partially filled".
- Until calibration with `own_order_log`: `fill_model_calibrated = false` and every output is `UNCALIBRATED`.
- `assume_front_of_queue_fraction` is for sensitivity analysis only (default 0).

### 5.4 Costs
```
cost = notional × (commission[RULE] + exchange_fee[RULE] + depository_fee[RULE])
     + (SELL ? notional × sell_tax[RULE] : 0) + slippage + impact
slippage = notional × s0 × f(liquidity_bucket)           # calibrated, pessimistic default
impact   = notional × k × σ_daily × sqrt(qty / ADV)      # k calibrated
cap      : qty ≤ cap × ADV                                # cap from config
```
- **One single `CostModel`** for every path; rates only from `rule_at`.
- `ADV` from adjusted `trade_volume` filtered on `trade_date`; pre-warm mandatory; **a fall back to a default is never silent** (an error or `adv_fallback=true` in the output). *(G-04)*
- `cost_stress_multiplier` (1x and 2x) in config.

### 5.5 Ledger and settlement
Accounts: `CASH_FREE, CASH_BLOCKED_ORDERS, MARGIN_BLOCKED[instr], SETTLE_RECV[date], SETTLE_PAY[date], POSITION[instr] (lot-level), DIV_RECV[date], FEES, TAX, EQUITY`.
Invariants: the balance is always zero; sale proceeds are not usable before `settle_date`; without costs, `EQUITY` changes only through price and corporate actions.

### 5.6 Corporate actions
At `ex_date`, before open, in order: cash dividend (`DIV_RECV`), split/merger, capital increase, rights. `adj_factor` from the events table; **reconcile with the official/second-source series** and report differences. Rights: pessimistic default (sell the right or abandon).

### 5.7 Iran-specific states
- **Buy/sell locks:** `lock_up/lock_down` state from `MarketState`; `lock_streak`; an order on the locked side per 5.3.
- **Censored returns:** a lock-day return does not represent a "tradable price"; separate label and feature (section 7.3).
- **Halts/long closures:** a position cannot be exited; MTM with `stale=true` and (optionally) `stale_haircut`; the gap at reopening is recorded; closure days are dropped from volatility/Sharpe statistics (not zero).
- **Systemic exit risk:** `joint_lock_stress` (simultaneous sell queues across several positions); `market_lock_share_daily`.
- **Behavioral hypotheses [H]** (float, market maker, IPO) are only features/filters with a statistical test; never a code rule.

### 5.8 Fast path (vectorized)
- Goal: wide search/ML; simple assumptions.
- **Requirements:** (1) the same `CostModel` (cost parameter mandatory); (2) reject negative signals (`NO_SHORT_ALLOWED`) unless `short_allowed`; (3) signal-origin guard: regenerate the signal on data truncated at t−1 and compare (truncation test); (4) `execution lag ≥ 1` session.
- **Acceptance:** a promising result must be re-run on the reference engine and match within the recorded tolerance (parity test). *(A-06, B-05)*
- Output labeled `FASTPATH_SCREENING` and carries no "trust grade".

### 5.9 Determinism
One global `seed`; each random component has its own RNG (`seed + component_id`); two runs ⇒ identical output.

---

## 6. Portfolio and risk

- **Allocation:** volatility target, fractional Kelly, HRP, minimum variance with shrinkage; a turnover-cost-aware optimizer.
- **Constraints:** cap per name/industry/liquidity; `participation_cap`; `max_avg_days_to_exit`; free capital after margin.
- **Risk:** VaR/CVaR, liquidity and regime risk, factor analysis (market/size/value/momentum), `beta` to the market.
- **Stops:** daily/monthly loss cap, drawdown, a manual kill switch.
- **Long-only:** negative weights forbidden; output "avoided loss" for exit signals.
- The current "10 signal gates" component (`signal_decision_engine`) is enabled in this layer `portfolio/gates` only **after** a baseline passes and with gate 9 fail-closed (suspended until then).

---

## 7. ML architecture

### 7.1 Feature Store
- Each feature: `name, group, definition, window, inputs, knowledge_time_rule, version, leakage_test`.
- Packs: price/returns, liquidity, money flow (real/legal), fundamental (publication time), fund/NAV, market/FX/commodity, derivatives, events, calendar.
- **Lock features (Iran):** `lock_up_today, lock_down_today, lock_streak, limit_up_days_k, limit_down_days_k, market_lock_share_daily`.
- **Cross-sectional daily** normalization (rank→gaussian/robust z); winsorize with bounds up to T; missing values: `is_missing` + a cross-sectional fill; "report not yet published" must not leak.
- Cache keyed by hash(definition+data). **A feature without a `knowledge_time_rule` is rejected on entry.**

### 7.2 Leakage guard in the pipeline (not just tests)
A `FeatureGuard` at computation time: any feature with an input having `knowledge_time > asof` ⇒ error. Permanent tests: **canary** ("tomorrow's return" must be caught by the guard), **shift**, **label shuffle**, **knowledge_time audit**, **fold audit**, **universe audit**. *(F-04)*

### 7.3 Label Factory
| Label | Definition | Iran note |
|---|---|---|
| T1/T2 | horizon-h return from the **executable price** (`open[t+1]`→`open[t+1+h]` with costs) | never `close[t]`; *(C-06)* |
| T3 | triple-barrier `m×σ_k`, expiry h | a barrier crossed on a lock day ⇒ exit at the next day's executable price |
| T4 | probability of tradability/exitability | from `fillable`/`days_to_exit`/halts |
| T5 | future volatility | — |
| T6 | change in fund premium | depends on NAV data (suspended without it) |
| T7 | meta-label (was the base signal profitable net of costs?) | — |
- An entry on a buy-lock day or for a halted symbol ⇒ drop the sample or mark it `untradable`.
- Sample weight ∝ average uniqueness; store gross and net versions.

### 7.4 Dataset Builder
PIT universe; liquidity filter from config; `universe_log`; asset-class separation (equity/fund/bond/option/commodity-FX); **purge + embargo ≥ horizon h**; `regime_epoch` id on every sample.

### 7.5 Model Zoo and lifecycle
1. baseline: simple rules + linear/logistic regression; 2. trees (LightGBM/XGBoost); 3. time series (GARCH/HMM/VECM); 4. deep only after beating the tree baseline; 5. ensemble + calibrator only after the base model is accepted.
```
candidate → shadow → paper → live_small → live → retired
```
Promotion only through gates (section 10); automatic return to `shadow` on IC decay for K periods, strong drift, rising tracking error, or a rule change that violates the model's assumptions (the `regime_epoch` trigger).
**Every model:** a `model_card` (data, features, period, epochs, metrics, rules active during training, limitations) and a `run_manifest`. A model without both is `UNVERIFIED` (the current state of the 359 models). *(F-01, F-02)*

### 7.6 Training Orchestrator
- Nested walk-forward (expanding and rolling); **Optuna/Grid only inside the training fold**; the evaluation fold never takes part in parameter selection.
- Optional CPCV for path distributions/PBO; **TimeSeriesSplit/CPCV instead of ordinary KFold**. *(C-07)*
- `TrialRegistry`: every trial (hypothesis, parameters, seed, result) is recorded and counted; `n_trials` feeds DSR.
- **Single-look hold-out:** the time and model version are recorded when it is seen; afterwards no change for the same hypothesis (a new hypothesis = a new count).

### 7.7 Evaluation
- Daily statistics: IC, Rank IC, `ICIR`, share of positive days; classification: AUC, log-loss, Brier, calibration curve; deciles; MAE/RMSE.
- **Cross-sectional Rank IC only with enough symbols N** (not reported with a very small N).
- Economic: always from the reference engine (not from IC); net returns in three measures, Sharpe/Sortino, MDD, turnover, capacity, `days_to_exit`, profit concentration, `fillable_rate` by score decile.
- Paired comparison with BL-1..BL-3 and block bootstrap (long blocks).

### 7.8 Monitoring
Feature drift (weekly PSI/KS against training and the last 3 months); score distribution; rolling IC and calibration; paper-vs-backtest gap; automatic alert on a `rules` change (new epoch).

### 7.9 Retraining
Scheduled; a new model replaces the old only if it wins on held-out data and passes the gates (the existing `_min_accuracy_gain` is kept and completed with a shadow/paper stage). *(C-10)*

---

## 8. Statistical validation layer

| Tool | Use |
|---|---|
| DSR / PBO / White RC (SPA) | correction for the number of trials (with `N_eff`) |
| block bootstrap (long blocks) | wide confidence intervals |
| `N_eff` | effective number of symbols from the correlation matrix |
| `n_epochs` and leave-one-epoch-out | dependence on a single regime |
| destructive tests | cost x2, +1 day delay, shuffle, price noise, drop best months/largest symbol, parameters ±20% |
| stress scenarios | FX jump, large rally/crash, administered pricing, long closures, sustained sell queues |
| breakdown reports | by regime/epoch/year/industry |
| beta/timing split | return beyond the market |

---

## 9. Reporting and registry

### 9.1 Standard report (one template for all)
1. `run_manifest` and the **trust grade** (section 10).
2. Three measures (nominal/real/USD) and benchmarks (BL-1..BL-7 from `BASELINES.md`).
3. Risk: absolute **and buy-and-hold-relative** MDD, Sharpe/Sortino/Calmar, time under water.
4. Executability: `fillable_rate` (score decile), `days_to_exit`, capacity, `unfillable` and `rejections(reason)`.
5. Itemized costs (commission/tax/slippage/impact) with `rule_at` rates and epoch.
6. Statistics: DSR/PBO, `n_trials`, `N_eff`, `n_epochs`, leave-one-epoch-out, beta.
7. Controls: results of BL-3/BL-4/BL-5/BL-6 from the same run.
8. Warnings: rules at confidence C/D, `knowledge_time_assumed` data, `adv_fallback`, `UNCALIBRATED`.
- Persian narrative text is generated from a template; **every number in the text is reconciled with structured data**; an unsourced number is forbidden.

### 9.2 `run_manifest`
`experiment_id, hypothesis_id, data_hash, rules_hash, features_version, code_version, config_hash, seed, engine_id (reference|fastpath), fill_model, fill_model_calibrated, cost_model_version, universe_hash, epochs_covered, n_trials, rules_confidence_min, dq_score_min, suspended_modules, started_at, finished_at`.

### 9.3 Output tables
`orders, fills, rejections(reason), positions_daily, equity_daily(nominal, real, usd), exposures_daily, costs_breakdown, settlement_queue_daily, corporate_action_log, margin_log, exit_risk_daily, control_results, trust_gates, run_manifest`.

---

## 10. Result trust grade

Every report computes the gates below (numeric thresholds come from `acceptance.yaml`/config; no numbers in this document):

| Gate | Condition | Critical? |
|---|---|---|
| G1 rules | `rules_confidence_min` ≥ the owner's required level; no placeholders | yes |
| G2 data | `dq_score_min` ≥ threshold; `trade_date`; adjusted series; cash dividends present or label "no dividend adjustment" | yes |
| G3 time | zero `LookAheadError`; the canary is caught; a shift does not improve | yes |
| G4 controls | BL-3 negative/near zero; BL-4 negative; BL-5 abnormal and rejected; BL-6 does not improve | yes |
| G5 parity | reference engine vs fast path (if used) within tolerance | yes for fast path |
| G6 executability | `fillable_rate` reported; queue model calibrated or the result is `UNCALIBRATED` | no (label) |
| G7 statistics | `n_trials` counted; DSR/PBO; `n_epochs`; leave-one-epoch-out | yes |
| G8 benchmark | three measures; an edge over an appropriate benchmark per `acceptance.yaml` | yes |
| G9 reproduction | two runs ⇒ identical hash | yes |

**Grade:** any failed critical gate ⇒ **"unreliable"**; all critical gates pass and G6 `UNCALIBRATED` ⇒ **"reliable with limitations"**; everything passes and calibrated ⇒ **"reliable"**; a gate that cannot be measured ⇒ **"unknown"**. The grade is computed by code, not by text.

---

## 11. Code interfaces (Protocol)

```python
class PITStore(Protocol):
    def read(self, dataset: str, ids: list[str], start: date, end: date, asof: datetime) -> DataFrame: ...

class RuleSet(Protocol):
    def rule_at(self, key: str, scope: Scope, on: date) -> RuleValue: ...      # value + confidence + source_ref

class ExecutionModel(Protocol):
    name: str; calibrated: bool
    def fill(self, order: Order, state: MarketState) -> list[Fill]: ...

class CostModel(Protocol):
    def cost(self, fill: Fill, ctx: CostContext) -> CostBreakdown: ...         # only from RuleSet

class Strategy(Protocol):
    def on_event(self, ev: Event, ctx: Context) -> list[Order]: ...            # ctx.position(...) for sell sizing

class FeaturePack(Protocol):
    name: str; version: str
    def compute(self, store: PITStore, asof: datetime) -> DataFrame: ...       # with FeatureGuard

class LabelFactory(Protocol):
    def build(self, kind: str, store: PITStore, exec_model: ExecutionModel, asof_end: date) -> DataFrame: ...

class Model(Protocol):
    def fit(self, X, y, w) -> None: ...
    def predict(self, X) -> Scores: ...

class Validator(Protocol):
    def run(self, result: BacktestResult, controls: ControlResults) -> TrustReport: ...
```
Rule: no class touches files/internet/DB directly; only through Store/Adapter.

---

## 12. Directory layout and mapping from the current repo (Strangler)

```
src/
  core/          # time, calendar (Jalali/Gregorian), identifiers, TimeGuard, bitemporal
  rules/         # rules, rule_at, epochs
  data/          # adapters, ingestion, adjust, dq, universe
  features/      # packs + FeatureGuard
  models/        # labels, datasets, zoo, training, trial_registry, calibration, lifecycle, drift
  portfolio/     # allocation, constraints, risk, gates (suspended)
  execution/     # fill models, costs, queue, exit_risk
  backtest/      # kernel (clock, orders, ledger, corp_actions, mtm), fastpath
  validation/    # stats, controls, stress, trust_grade
  reports/       # standard report, narrative
tests/           # unit, property, golden, leakage, validity, integration
experiments/     # run_manifest + outputs
```

| Current module | Destination | Decision |
|---|---|---|
| `backtesting/engine/backtest_engine.py` | `backtest/kernel` | proposed reference (after parity) |
| `backtesting/engine/simulator.py`, `broker.py` | `execution/` + legacy | rewrite execution/ADV; keep `cost_model` |
| `backtesting/costs/iran_costs.py`, `domain/trading/iran_costs.py` | `execution/costs` | keep the formula, wire to `rule_at` |
| `services/backtest_framework.py` (Vectorized) | `backtest/fastpath` | rewrite (costs, guard, reject short) |
| `services/backtest_framework.py` (CPCV, DSR) | `validation/stats` | keep and wire in |
| `services/signal_backtest_engine.py` | `validation/signal_eval` | a **signal-outcome evaluator**, not an engine; costs from CostModel; `trade_date` column |
| `backtesting/strategies/*` | `src/strategies` | fix sell sizing |
| `backtesting/metrics/*`, `analytics` | `reports/metrics` | keep + relative MDD + consistent `profit_factor` |
| `backtesting/data/price_limits.py`, `market/rule_versioning.py` | `rules/` | migrate to the table |
| `ml/datasets/labeling.py` | `models/labels` | rewrite (executable) |
| `ml/models/sweeper.py` | `models/training` | rewrite (purged/CPCV + trial registry) |
| `services/feature_engine.py` | `features/packs` | keep + `knowledge_time` + FeatureGuard |
| `ml/artifacts.py` + `ml_artifacts/` | `models/registry` | fix the path; models `UNVERIFIED` |
| `services/auto_retrain_pipeline.py` | `models/lifecycle` | keep + shadow/paper |
| `services/quant_signal_orchestrator.py`, `signal_decision_engine.py` | `portfolio/gates` | suspended; gate 9 fail-closed |

Migrate module by module with an adapter; the old module keeps working until fully replaced; old/new outputs are compared and differences explained.

---

## 13. Flow of a run

### 13.1 Backtest
1. Load config → initial `run_manifest` → `rules_hash/data_hash`.
2. Build the PIT universe and load `curated` (adjusted) data with `TimeGuard`.
3. Generate signals (model or rule) from features up to `decision_time`.
4. Portfolio ⇒ orders with `earliest_exec_time`.
5. Reference engine: events in order; OrderManager → ExecutionModel → CostModel → Ledger; corporate actions and settlement; MTM.
6. Controls (BL-3..BL-6) on the same data and engine.
7. Metrics + Validation + Trust Grade.
8. Report + final `run_manifest` + registration in the Registry.

### 13.2 Training
1. Register the hypothesis and `hypothesis_id` before running; read `acceptance.yaml` (read-only).
2. Dataset Builder (PIT universe, purge/embargo, epoch).
3. Label Factory (executable).
4. Nested walk-forward; every trial in the `TrialRegistry`.
5. Statistical + economic evaluation from the reference engine; leakage controls.
6. `model_card` + registration in the Registry with status `candidate`.
7. Promotion to `shadow/paper/...` only through gates.

---

## 14. Test architecture

| Level | Key tests |
|---|---|
| Unit | `rule_at` (boundary/overlap), Jalali/Gregorian conversion, `add_business_days`, CostModel, sell sizing |
| Property (Hypothesis) | `filled ≤ qty`; no fill before `t_submit`; cash unusable before `settle_date`; ledger balance zero |
| Golden | 1 to 3 symbols, several months, the owner's hand computation; any result change without an ADR is forbidden |
| Leakage | look-ahead rejected; a shift does not improve; feature canary; label shuffle; fold/universe/knowledge_time audit |
| Validity (controls) | BL-3 ≈ zero/negative; BL-4 negative; BL-5 abnormal and rejected; BL-6 does not improve |
| Invariant | capital conservation; value continuity at `ex_date`; an N-month closure has no trades and records a gap |
| Parity | reference ⟷ fast path; reference ⟷ old Simulator (within tolerance) |
| Integration | pipeline on a small sample; determinism (two identical runs) |
| Regression | a code change must not change golden without a reason |
| Iran-specific | `NO_SHORT_ALLOWED`; a locked-side order without queue data ⇒ `unfillable`; two spellings of one symbol ⇒ one `instrument_id`; data with a wrong offset ⇒ warning |

---

## 15. Operations and live lifecycle

- Daily pipeline: ingest → DQ → adjust → features → predict → report, with retries and alerts.
- `shadow` (predictions without effect) → `paper` (several months, tracking error vs backtest) → `live_small` (loss cap, manual approval) → `live`.
- Automatic stop triggers: IC decay, drift, tracking error, rule change (epoch), gate failure.
- **Record from today:** depth/queue, snapshots, `own_order_log`, news with timestamps (history without timestamps never enters the backtest).
- Security: keys only in a secret store; no secrets in code/logs; read-only DB for analytical tools.

---

## 16. Traceability: audit finding ⇒ architecture element

| Finding | Architecture element |
|---|---|
| A-03 sell sizing | 5.2 (sell size from the position); property test |
| A-04 MDD | 9.1 (relative MDD); 10 G4 |
| A-06, B-04, B-05 | 0.1, 5.8, `parity`, `TimeGuard` |
| B-01 | 0.6, `BASELINES.md`, G4 |
| C-01, C-06 | 2.2, 5.3, 7.3 |
| C-02, C-03, C2 | 4, rule_at, epoch |
| C-04, C-05 | 3.1 adjustment/dividends |
| C-07 | 7.6 |
| C-08 | 3.1 PIT universe |
| D-03 | 6 (gate 9 fail-closed) |
| F-01, F-02 | 7.5 (`UNVERIFIED`, model_card) |
| F-04 | 7.2 FeatureGuard |
| G-01, G-02, G-03 | 3.1 (`trade_date`, bitemporal) |
| G-04, A-02 | 5.4 (ADV, no silent fallback) |

---

## 17. Out of scope / suspended

HFT and intraday without suitable data; deep models before a baseline; ensemble/calibrator/10 gates/agent-based/genetic until a baseline passes; derivatives/bonds/funds/commodities until the coverage matrix reaches `partial/full`; news without timestamps; public release before two successful paper periods.

## 18. Open decisions (owner only)

1. Approve ADR-001 (reference engine) and ADR-002 (`trade_date`); 2. `acceptance.yaml` and `reference_rates`; 3. official rule sources; 4. horizon (daily/weekly) and target capital/capacity; 5. hold-out window; 6. existence of `own_order_log` and depth/queue data; 7. market priority (suggestion: equities → gold/funds → bonds → options).
