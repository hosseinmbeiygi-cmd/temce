# CONSOLIDATED SPECIFICATION (EN) — Backtest and ML for the Iranian market (TSE / IFB / IME)
## Review of the submitted blueprints and deep-research report, with a corrected, self-contained specification

> **How to read this document.** Part A is the review verdict. Part B is the authoritative finding register (taken from the real `findings_new.csv`). Part C is the corrected architecture. Part D lists every number from the submitted material and marks it unsourced. Part E describes the tested reference code. Part F lists what only the owner can decide or supply.
> **Precedence:** `CLAUDE.md` > `SPEC_*` > `ARCHITECTURE.md` > `ARCHITECTURE_BT_ML.md` > this document.
> **What this document does not claim:** the correctness of any Iranian market rule, the profitability of any strategy, or that any audit finding is already fixed. I have not read the project code; findings come from the audit packages (done by another model) and are all still marked `open — re-verify before acting`.

---

# PART A — Review of the submitted material

## A.1 What was reviewed
1. Four iterations of the "Ultra-Production / Full Production Blueprint" (most sections repeat verbatim; the last adds a 49-finding matrix, SQL DDL, and Python classes, and is cut off inside the order-book class).
2. The deep-research report (venue/regulatory source trail, F01–F49 reconstruction, Gate-9 table, performance formulas).

## A.2 Verdict

| Item | Verdict |
|---|---|
| Blueprint as an executable specification | **Do not use as-is.** It contradicts the project rules (owner-only thresholds, no unsourced market numbers, long-only) and itself. |
| 49-finding matrix | **Partly wrong** (24 of 49 severities differ from the real CSV; its own body lists 15 critical while its summary says 10). Use Part B instead. |
| SQL/Python samples | **Several defects** (A.3.4). Replaced by the tested code in Part E. |
| Deep-research report | **Useful method, weak substance.** Good: evidence taxonomy, source manifest, fail-closed deployment gates, rollback. Weak: it could not read the CSV (which exists), so its "F01–F49" is a generic checklist that omits most real findings; regulatory claims rest on search snippets. |
| Ideas worth keeping | Bitemporal model, rules registry with intervals, L3 invariants, executable-label eligibility codes, purge/embargo, three-measure reporting, stress matrix, instrument module requirements, kill switch and rollback. All are re-stated in Part C with corrections. |

## A.3 Defects found

### A.3.1 Rule violations (critical)
- **Acceptance thresholds were written into the document** (Rank IC ≥ 0.045, ICIR ≥ 0.50, DSR ≥ 0.95, PBO ≤ 0.15, MDD ≤ 18% in one version and ≤ 22% in another, fillable rate ≥ 85%, unfillable profit = 0%, ≥ 4 epochs, real return ≥ +12%/yr, USD alpha ≥ +8%/yr, N_eff ≥ 8, avg days to exit ≤ 12, MCLD ≤ 3 days, and more). Per `CLAUDE.md`, only the owner registers these in `acceptance.yaml`, before the first run. "Industry standard" is not a justification.
- **Market numbers without a source or confidence level:** every fee, tax, cap, price band, epoch date, margin factor, settlement lag, session time (see Part D). Per `CLAUDE.md` these are confidence D until sourced.
- **Short selling assumed** (gold/silver pair trade "Short the bubbly asset", signed ±1 signals, conversion/reversal arbitrage, continuous delta hedging). The project default is long-only (`SPEC_IRAN_MARKET` section 1).
- **Scope inflation:** four full pipelines, online ML, Markov-switching regimes, and HFT-style infrastructure (LMAX Disruptor, shared-memory IPC, sub-microsecond parsing, FIX feed, Rust) are proposed before R1–R4 are done. The data is daily; HFT is out of scope (`ADR-005`).
- **Leveraged-ETF erosion formula** (16% per year for L=2, σ=40%) applies the foreign daily-reset model; `SPEC_VALUATION` section 7 says not to apply it unless the fund's structure is exactly that.
- **Absolute language:** "guarantee zero look-ahead", "guaranteed profit", "flawless". Tests detect leakage; they do not guarantee its absence.

### A.3.2 Contradictions inside the material
- MDD limit: 18% vs 22%.
- Two epoch tables overlap and disagree (for example a ±5% period to 1399/11/25 and a ±2% period in an overlapping window; end of the asymmetric period given as 1400/02/24 and as 2021-04-30).
- Total equity cost 1.2424% in the documents, round trip 1.47% (0.485% + 0.985%) in the code's SSOT; a third variant "0.00485 / 0.00540".
- Cash after a sale: "available at T+1 for repurchase" in one place, "available at T+2, fund purchase allowed at T+3" in another.
- "7-fold" vs "8-fold" control suite; label-shuffle limit |IC| < 0.005 vs 0.01.
- The vectorized engine is "removed completely" in one section and "kept for screening" in another.
- The **canary test is stated backwards** in one version (noise on the close of bar t must not change the signal for bar t; that is false by construction). A correct test perturbs data **after** t and checks that the signal at t is unchanged (truncation test).
- Three different things are called "Gate 9": the existing orchestrator signal gate 9 (finding D-03), the deep-research deployment Gate G9, and my earlier trust-grade G9. This document renames them (Part C.11): signal gate 9 stays as is, trust gates become **TG1–TG9**, deployment gates become **DG1–DG9**.

### A.3.3 The 49-finding matrix compared with the real `findings_new.csv`
The IDs (49) and the totals (10 critical, 19 high, 7 medium, 6 low, 7 info) match the CSV. But:
- The matrix's own body labels give 15 critical, 15 high, 9 medium, 6 low, 4 info, which does not equal its summary.
- **24 severities differ from the CSV:**

| ID | CSV severity | Matrix severity |
|---|---|---|
| B-01 | critical | high |
| B-02 | info | high |
| B-03 | info | medium |
| B-06 | high | medium |
| C-01 | critical | high |
| C-04 | high | critical |
| C-05 | high | critical |
| C-06 | high | critical |
| C-07 | high | critical |
| C-10 | info | medium |
| D-02 | medium | low |
| D-04 | high | low |
| E-01 | medium | high |
| E-02 | high | medium |
| E-03 | low | medium |
| E-04 | medium | high |
| F-03 | medium | info |
| F-04 | high | critical |
| F-05 | info | medium |
| G-03 | high | critical |
| H-01 | medium | critical |
| H-02 | info | low |
| I-03 | low | info |
| G-06 | low | medium |

- **Interpretation errors:** B-03 is "detrended net about −59% = cost drag", not "riding the index trend"; C-10 is informational (retrain does not replace blindly), not a defect; F-02 concerns the metadata of **one** sample model, not "delete the model and void all results"; H-01/H-02 say the sensitive keys are on disk and **not tracked in git**, not "leaked in the repo"; G-04's 8.4e9 comes from `trade_volume` (shares), not "rials"; A-06's −60.17% came from an **external harness** applying costs, not from the engine (the engine has no cost hook).

### A.3.4 Code defects in the submitted samples
- `fetch_adjusted_price_series`: uses `mid_price` of an order-book snapshot as the "raw price" (should be the official close); applies `EXP(SUM(LN(split_ratio)) OVER (ORDER BY event_time DESC))` which accumulates in the wrong direction for backward adjustment and ignores cash dividends and rights entirely.
- `RuleRegistry`: no instrument/scope in `rule_at`; overlap check compares neighbors across **all** rules (false positives across scopes, misses within scope); `rule_confidence DEFAULT 1.0` makes unsourced rules look fully trusted; the diagram echoes the placeholder value +0.03.
- `CHECK (knowledge_time >= event_time)` is wrong for announcements and rules published **before** their effective date.
- `NOT NULL` on `limit_low/limit_high/volume_base` forces someone to invent values.
- `VirtualOrderBookMatcher`: default `cancel_decay_factor = 0.15` is an uncalibrated invented parameter; the class is cut off before the fill logic.

### A.3.5 Deep-research report
- Treats `findings_new.csv` as unavailable; F01–F49 therefore omit most real findings (no sell-sizing bug, no MDD equality, no artifact-path bug, no `gregorian_date` bug, no gate-9 fail-open).
- Statuses "partially verified" for rules (price bands, IME certificates, margin) rely on search snippets; the pages were not readable. Treat them as **unverified**.
- **Sign error:** nominal P&L is written as ending value minus withdrawals; withdrawals must be **added** (they are money already returned to the investor). Correct: `P = ending_value + withdrawals − contributions`.
- Good and kept: status taxonomy, source manifest fields, publication-vs-effective-date separation, per-source access-failure recording, kill-switch triggers, rollback drill.

## A.4 Net result
No number from the submitted blueprints is carried into the specification as a value. Each appears only in Part D as "proposal, unsourced". The corrected design is Part C; the corrected code is Part E.

---

# PART B — Authoritative finding register (from the real `findings_new.csv`)

All entries: **status open, re-verify before acting**. "Step" refers to `REMEDIATION_PLAN.md`.

| ID | Severity | Area | Summary | Step | Status |
|---|---|---|---|---|---|
| A-01 | info | backtest | sell tax 0.5% and clearing 0.085% ARE applied via cost_model; previous claim of commission-only is wrong | R1 (note) | open |
| A-02 | high | backtest | _compute_slippage caps at 150bps; first buy ~913M triggers full 1.5% slippage from ADV fallback | R1 | open |
| A-03 | critical | backtest | sell branch sizes qty from cash not position; position never fully closed -> 1-share decay | R1 | open |
| A-04 | critical | backtest | MDD 38.73 equals raw buy-and-hold price MDD; insensitive to strategy | R1 | open |
| A-05 | high | backtest | total cost ~constant 21.08-21.21M because gross notional ~1.17B constant; 64% from first fill | R1 (explained) | open |
| A-06 | critical | backtest | three engines not comparable: Vectorized has no cost hook; Simulator +28.25% vs Vectorized -20.94% | R1 | open |
| A-07 | high | backtest | DEFAULT_TRANSACTION_COSTS stock=0.003 flat vs SSOT round-trip 0.0147 (4.9x low) | R1 | open |
| B-01 | critical | backtest | random baseline in Simulator is really buy&hold (none of 200 seeds negative) | R4 | open |
| B-02 | info | backtest | clean harness random long/flat negative in 1000/1000 runs with SSOT costs | R4 (positive) | open |
| B-03 | info | backtest | detrended series net ~-59% (cost drag) | R4 | open |
| B-04 | critical | backtest | foresight measurable in Vectorized (+264%..+772%) but invisible in Simulator | R1 | open |
| B-05 | high | backtest | VectorizedBacktest has no signal-origin/truncation guard; proposed test fails | R1 | open |
| B-06 | high | backtest | _compute_slippage cap eats foresight profits on 86 flips | R1 | open |
| C-01 | critical | backtest | Simulator fills at decision bar close; BacktestEngine fills next bar open - inconsistent | R1 | open |
| C-02 | high | backtest | IRAN_LIMIT_HISTORY time-aware but dead code; 2024 rule set to 0.03 as example | R3 | open |
| C-03 | medium | backtest | versioned rules (tick/T+2/session) exist but not wired to backtest | R3 | open |
| C-04 | high | data | backtest reads RAW price_close; vw_daily_history_adjusted unused | R2 | open |
| C-05 | high | data | corporate_action_events only capital_increase, all dps=0; corporate_actions empty | R2 | open |
| C-06 | high | ml | label uses close[t] while execution uses open[t+1]; locked/suspended days not handled | R5 | open |
| C-07 | high | ml | GridSearchCV cv=5 on time series (no purge/embargo); DSR defined but unused | R5 | open |
| C-08 | high | data | survivorship: distinct_symbols_last_90d == all_time (2407); no delisted symbols | R2 | open |
| C-09 | info | ml | float_turnover_pct and net_inst_ratio bugs from HIDDEN_ERRORS_REPORT are fixed | R5 (regression tests) | open |
| C-10 | info | ml | retrain only sticks if holdout accuracy improves by 0.02 (not blind replace) | R5 | open |
| D-01 | low | docs | module counts inconsistent (backtesting 275 claimed vs 298 py files; services 103 vs 162) | R6 | open |
| D-02 | medium | docs | goal-doc numbers stale (36.73%->38.43%; -4.03%->-3.73%) | R6 | open |
| D-03 | critical | orchestration | Gate 9 is fail-OPEN (portfolio_approved=True) contradicting fail-closed claim | R6 | open |
| D-04 | high | backtest | profit_factor returns inf while AnalyticsEngine floors at 1.0 - inconsistent | R1 | open |
| E-01 | medium | tests | 27 API backtest tests fail on 401 auth despite DB+Redis available | R6 | open |
| E-02 | high | tests | 6 failures: AttributeError ScoringEngine._smooth_phase/_phase_history (stale tests) | R6 | open |
| E-03 | low | tests | fail: expects empty factor table but daily_adjust_factors has 621818 rows | R6 | open |
| E-04 | medium | backtest | run_backtest returns success on empty data (test flaky) | R1 | open |
| E-05 | high | tests | missing validity tests (random approx 0, label shuffle, feature canary, book survival) | R4 | open |
| F-01 | critical | ml | ArtifactManager root=data/models but artifacts in ml_artifacts -> load fails -> ML signal zeroed | R5 | open |
| F-02 | high | ml | stored xgboost model reports directional accuracy 0.183, R2 -0.545 | R5 | open |
| F-03 | medium | ml | exploratory Ridge: pooled IC 0.118; daily RankIC 0.305+-0.449 (ICIR 0.68) | R5 (ignore number) | open |
| F-04 | high | ml | canary future-return feature accepted silently (IC 0.999) | R5 | open |
| F-05 | info | ml | label shuffle drives IC to ~0 (good) | R4 (positive) | open |
| G-01 | critical | data | gregorian_date/shamsi_date are sync dates not trade dates; multiple trade dates share one gregorian_date | R2 | open |
| G-02 | critical | data | future prices filtered on gregorian_date (wrong column, it is sync date) | R2 | open |
| G-03 | high | data | main table is not a hypertable; no knowledge_time/versioning; upsert overwrites | R2 | open |
| G-04 | high | backtest | ADV sync fallback 1,000,000 vs resolved ~8.4e9 for khodro (thousands-x cost swing) | R1/R2 | open |
| H-01 | medium | security | 6 sensitive keys on disk; .env gitignored/untracked (no value printed) | R6 | open |
| H-02 | info | security | 0-byte file, no hardcoded key; no secrets in code/docker-compose | R6 | open |
| H-03 | medium | security | scraped data ToS undocumented (BrsApi/TGJU) | R6 | open |
| I-01 | low | structure | four overlapping report dirs (reports/new_reports/symbol_reports/new_symbol_reports) | R6 | open |
| I-02 | low | structure | one-off root scripts; gen_all.py is 15 bytes; mkpages.py 300 bytes | R6 | open |
| I-03 | low | structure | empty dir vs root BrsApi_Forecasting app | R6 | open |
| G-05 | high | data | corporate_action_events only capital_increase and all dps=0; corporate_actions has 0 rows | R2 | open |
| G-06 | low | data | brsapi_currency_history and brsapi_option_snapshots error on generic column queries (different schema) | R2 | open |
---

# PART C — Corrected architecture

## C.1 Principles
1. One reference engine and one cost model; the fast path is screening only.
2. Time first: every read has `knowledge_time <= decision_time`; every fill is after `decision_time`.
3. Rules are data: `rule_at()` only; unsourced rule = confidence D = result flagged "unreliable".
4. Long-only by default; "bearish" means exit or reduce weight.
5. Executability is first-class: `fillable_rate`, `unfillable`, `days_to_exit` accompany every result.
6. Measurement is validated before strategies: positive and negative controls run on the same data and engine.
7. ML consumes only validated data and engine; acceptance only via owner-registered `acceptance.yaml`.
8. Three measures (nominal, real, USD) against appropriate benchmarks; independent-sample count (`N_eff`, epochs) reported.
9. Reproducibility: `run_manifest`; two runs give identical output.
10. Suspend instead of guess: data marked none/unknown suspends the dependent module; no substitute data or rules are invented.

## C.2 Time model
| Name | Meaning |
|---|---|
| `trade_date` | real trading date of the observation (never the sync date) |
| `event_time` | when the event happened (trade, order event, session change, effective time of a corporate action) |
| `knowledge_time` | when the system could first see it; corrections are new rows with a later `knowledge_time` |
| `ingested_at` / `first_seen_at` | insert time; never overwritten |
| `decision_time` | all inputs with `knowledge_time <= decision_time` are available |
| `earliest_exec_time` | first allowed execution phase strictly after `decision_time + delay` |
| `settle_time` | `add_business_days(trade_date, rule_at('settlement_days'))` using the venue calendar |

Rules and announcements: `knowledge_time` may be **earlier** than `effective_from` (published before taking effect). The inequality `knowledge_time >= event_time` is enforced only for market observations. Jalali and Gregorian dates are both stored; the canonical key is `trade_date` (Gregorian) with timezone `Asia/Tehran`.

## C.3 Data layer (target schemas; PostgreSQL syntax; proposed, reconcile with real samples)
```sql
-- Daily bars (curated layer). Rule-derived columns are nullable: never invent values.
CREATE TABLE curated.equity_daily (
  instrument_id   uuid        NOT NULL,
  trade_date      date        NOT NULL,
  jalali_date     char(10)    NOT NULL,
  open_price      numeric(18,4), high_price numeric(18,4), low_price numeric(18,4),
  close_price     numeric(18,4), final_price numeric(18,4),
  volume          bigint CHECK (volume >= 0),
  value           numeric(24,4) CHECK (value >= 0),
  trade_count     integer CHECK (trade_count >= 0),
  status          text   NOT NULL,                      -- open | halted | closed | suspended
  base_volume     bigint,                               -- from rules, nullable
  limit_low       numeric(18,4), limit_high numeric(18,4),   -- from rules, nullable
  regime_epoch    text,
  event_time      timestamptz NOT NULL,
  knowledge_time  timestamptz NOT NULL,
  knowledge_time_assumed boolean NOT NULL DEFAULT false,
  source_id       text NOT NULL,
  CHECK (knowledge_time >= event_time),
  PRIMARY KEY (instrument_id, trade_date, knowledge_time)
);

-- Order-book events (only if real L3/L2 data exists; otherwise this module is suspended).
CREATE TABLE curated.book_event (
  instrument_id uuid NOT NULL, trade_date date NOT NULL,
  event_time timestamptz NOT NULL, knowledge_time timestamptz NOT NULL,
  seq bigint NOT NULL, event_type text NOT NULL,        -- add | modify | cancel | trade | status
  side char(1), price numeric(18,4), quantity bigint, order_ref text,
  PRIMARY KEY (instrument_id, trade_date, seq, knowledge_time),
  CHECK (knowledge_time >= event_time)
);

CREATE TABLE curated.corporate_action (
  event_id bigserial PRIMARY KEY, instrument_id uuid NOT NULL, action_type text NOT NULL,
  ex_date date NOT NULL, ratio numeric(14,8), cash_per_share numeric(18,4),
  subscription_price numeric(18,4), record_date date,
  source_ref text NOT NULL, knowledge_time timestamptz NOT NULL
);   -- action_type: bonus | cash_dividend | rights | split | merger

CREATE TABLE ref.rule (
  rule_key text NOT NULL, scope text NOT NULL, value jsonb NOT NULL,
  effective_from date NOT NULL, effective_to date,
  source_ref text, confidence char(1) NOT NULL DEFAULT 'D' CHECK (confidence IN ('A','B','C','D')),
  verified_by text, knowledge_time timestamptz NOT NULL,
  CHECK (effective_to IS NULL OR effective_from < effective_to),
  EXCLUDE USING gist (rule_key WITH =, scope WITH =,
          daterange(effective_from, effective_to, '[)') WITH &&)       -- overlap per (rule_key, scope)
);

CREATE TABLE ref.symbol_history (instrument_id uuid NOT NULL, symbol_norm text NOT NULL,
  symbol_raw text NOT NULL, from_date date NOT NULL, to_date date, source_ref text);
CREATE TABLE ref.calendar (trade_date date PRIMARY KEY, jalali_date char(10) NOT NULL,
  is_trading_day boolean NOT NULL, market_status text NOT NULL, source_ref text);   -- includes unscheduled closures
CREATE TABLE ops.dq_rejection (id bigserial PRIMARY KEY, source_table text, failed_rule text,
  raw_payload jsonb, detected_at timestamptz DEFAULT now(), severity text);
CREATE TABLE ops.source_manifest (source_id text, url text, retrieved_at timestamptz, publication_date date,
  effective_date date, sha256 text, language text, translation_version text, access_status text, note text);
```
(The `EXCLUDE ... gist` constraint needs the `btree_gist` extension.) Existing tables are migrated with the strangler approach: add `trade_date` and `first_seen_at` beside current columns; never drop or reinterpret existing columns (see `SPEC_DATA_SCHEMAS.md`).

## C.4 Rules registry
- Scope resolution: `symbol > segment > market > global`; exceptions are explicit rows.
- Intervals are half-open `[from, to)`; missing rule raises `RuleNotFound` and marks the dependent observation `eligible = false` with reason `missing_rule`.
- Every result carries `rules_confidence_min`; any C or D rule makes the trust gate TG1 fail.
- Rule keys (no values here): `short_allowed`, `price_limit`, `base_volume_rule`, `tick_size`, `lot_size`, `session_phases`, `order_types`, `order_size_limit`, `position_limit`, `commission_rate`, `exchange_fee`, `depository_fee`, `sell_tax`, `min_commission`, `settlement_days`, `buy_cash_timing`, `credit_allowed`, `valuation_price`, `auction_matching`, `market_status`, `trading_week`, `option_settlement_style`, `option_margin_formula`.
- `regime_epoch`: a new epoch for every major rule change; evaluation uses leave-one-epoch-out and reports `n_epochs`.
- A published rule is not an effective rule: store publication date, effective date, and our `knowledge_time` separately.

## C.5 Reference execution engine
- **Lifecycle:** `NEW → ACCEPTED → WORKING → PARTIALLY_FILLED → FILLED | CANCELLED | EXPIRED`, or `REJECTED(reason)` with reasons `MARKET_CLOSED, SYMBOL_HALTED, PRICE_OUTSIDE_LIMIT, BELOW_TICK, BAD_LOT, INSUFFICIENT_CASH, INSUFFICIENT_MARGIN, POSITION_LIMIT, ORDER_SIZE_LIMIT, NOT_TRADABLE_IN_PHASE, NO_SHORT_ALLOWED, MISSING_RULE`.
- **Sell size comes from the open position, never from cash** (finding A-03).
- **Fill models:** `idealized` (unit tests only), `conservative_ohlc` (default for daily data), `queue_observed` (needs real event data), `auction` (observe only until a rule is confirmed).
- **Queue invariants** (implemented in Part E): fill only after the queue ahead is cleared by observed trades or observed cancellations ahead; `filled <= qty`; no event before submit; without queue data on a locked side the entry is `unfillable`. No decay or cancellation rate is assumed; results are `UNCALIBRATED` until checked against `own_order_log`. The book must satisfy conservation: `initial = executed + cancelled + remaining` per order.
- **One cost model** for every path, reading rates only from `rule_at`; ADV from adjusted `trade_volume` filtered on `trade_date`; a fallback value is never silent (`adv_fallback = true` or error). Note the unit: `trade_volume` is in shares, not rials.
- **Ledger and settlement:** double entry, blocked cash, settlement receivable per `settle_time`; sale proceeds unusable before settlement; opportunity cost of frozen cash is reported **once** (either through the ledger or as a separate line, never both). Reference rate for opportunity cost is an owner decision (`reference_rates`).
- **Corporate actions** at `ex_date` before open: dividend, split/merger, capital increase, rights; adjustment factors from the events table and reconciled against the official or second-source series.
- **Locks and halts:** lock state from market data; lock-side order without queue data is unfillable; halted positions cannot exit, are marked `stale`, and "halted more than N days" triggers **entry prohibition and exit-blocked flag**, not an automatic forced exit (a halted symbol cannot be sold).
- **Fast path:** same cost model, rejects negative signals unless `short_allowed`, signal-origin guard (truncation test), execution lag at least one session; output labeled `FASTPATH_SCREENING`; promising results must be re-run on the reference engine within a recorded tolerance.

## C.6 Executable labels, validation, leakage
- Label from executable prices: entry `open[t+1]`, exit `open[t+1+h]`, with buy and sell fees and slippage; an ineligible sample carries a reason code (`missing_execution_rule`, `untradable_entry`, `untradable_exit`, `locked`, `halted`), never a silent zero. (Implemented as `labels.executable_label`.)
- Walk-forward with purge and embargo; training sample kept only if `label_end + embargo < test_start`; boundary inclusion defined once. The embargo length is at least the label horizon; its value is a config choice, not a constant here.
- Hyperparameter search only inside the training fold; every trial recorded in a trial registry; `n_trials` feeds DSR; single-look hold-out with time and model version recorded.
- Permanent tests: feature canary ("tomorrow's return" must be caught by the pipeline), shift test, label shuffle, `knowledge_time` audit, fold audit, universe audit (delisted symbols present in history).
- Cross-sectional Rank IC is reported only with enough symbols; with very few symbols it is not computed.

## C.7 Instrument modules (all `suspended` until data and rules exist)
| Module | Data required | Rules required (via `rule_at`) | Model note | Gate before enabling |
|---|---|---|---|---|
| Equities | daily bars (adjusted), real/legal flows with `knowledge_time`, status and lock flags, base volume | price limit, tick, lot, fees, tax, settlement, base volume | `conservative_ohlc`, then `queue_observed` when event data exists | R1–R4 passed |
| Funds incl. leveraged | NAV with publication time, portfolio composition, prospectus (leverage, reset frequency, fees, financing, creation/redemption) | fund-class fees, price limit, valuation price | Path-wise simulation of the fund's **own** rebalancing rule; the closed-form drag `(L²−L)σ²T/2` is only a sanity check, not a model; intraday NAV estimate needs published composition and is a nowcast with its own error series | prospectus parsed and reconciled against official NAV |
| IME gold/silver certificates and futures | certificate and futures prices, official product specs (unit, lot, purity, custody, delivery), FX reference chosen by the owner, global ounce with timestamp alignment | fees, tick, settlement, margin, expiry/roll | Fair value `XAU/31.1034768 × FX_ref × weight × purity (+ spec premiums)`; **no bubble series without an explicit FX reference** (`SPEC_VALUATION` section 9); physical-delivery floor only if delivery cost and lot are in the spec | official specs and an FX reference registered |
| Options | contract specs, quotes with bid/ask, open interest, underlying price, discrete dividends, rate curve as-of | settlement style, margin formula, tick, fees, exercise rule | Stock options: BSM with escrowed discrete dividends (`SPEC_VALUATION` section 6). **Black-76 only if the underlying is a futures/forward**. Rate curve must be an as-of snapshot; the zero-coupon assumption for treasury bills is `[VERIFY]` per instrument | margin machine reconciled against official worked examples |

Not accepted from the submitted blueprints: pair trades that require shorting, hedging rules that need shorting, "guaranteed" arbitrage, hard-coded betas and lags, fixed-threshold spread signals.

## C.8 Portfolio and risk
Long-only; position, industry and liquidity caps; participation cap against ADV; liquidity-lock index defined from observed lock and exit-time data (not from assumed constants); joint-lock stress (many names locked on the sell side at once); loss and drawdown stops; manual kill switch. Optimizers (HRP, shrinkage mean-variance, fractional Kelly) are allowed after the baseline passes. Meta-labeling (a second model for sizing and fill probability) is allowed after a primary baseline passes.

## C.9 Reporting (three measures, corrected)
```
nominal P&L           = ending_value + withdrawals − contributions            (withdrawals ADD)
nominal IRR           = XIRR on signed flows (outflow < 0, inflow > 0)
real flow             = cf × CPI(base) / CPI(date of cf)                       (caller chooses CPI vintage)
real IRR              = XIRR on real flows
USD flow              = cf_rial / FX_rial_per_usd(date)                        (FX definition, side, timestamp registered)
USD alpha             = IRR_USD(strategy) − IRR_USD(benchmark)                 (benchmark and holding period registered)
```
CPI: use the vintage actually published when the report is produced; for any **decision-time** use of inflation, use only values with `knowledge_time <= decision_time`. Units: confirm rial vs toman for every series (1 toman = 10 rials).
Every report also contains: benchmarks (buy-and-hold, equal-weight, gold/coin, USD, fixed-income fund, deposit when data exists), absolute and benchmark-relative MDD, `beta` and value beyond market timing, `N_eff`, `fillable_rate` by score decile with the calibration label, `n_epochs`, leave-one-epoch-out, `n_trials`, DSR/PBO, itemized costs, `run_manifest`.

## C.10 Stress matrix (conditions only; thresholds from `acceptance.yaml`)
| Scenario | Control | Failure |
|---|---|---|
| Locked limit book | observed-event replay; no synthetic crossing | any fill without an observed crossing |
| Regime change | split by epoch; leave-one-epoch-out | pooled rule or no drift report |
| FX shock | revalue rial and USD with spread and haircut | unexplained sign change |
| Fee/tick/limit change | `rule_at` before and after the change | future value used for the past |
| Queue decay | calibration by rank bucket and regime | no interval or failed calibration |
| Partial fills | conservation of quantity | `initial != executed + cancelled + remaining` |
| Margin change | machine reconciled to official examples | unknown parameter |
| Rate curve | as-of snapshot only | curve from the future |
| Leveraged fund | path-wise decomposition into beta, fees, financing, tracking error, drag | unexplained residual |
| Data/model drift | monitor features, calibration, fill rate, P&L | continuing after a breach or outage |

## C.11 Gates (names fixed to avoid the three-way "Gate 9" collision)
**Trust gates (per result), TG1–TG9:** TG1 rules (no confidence C/D, no placeholders); TG2 data (DQ, `trade_date`, adjusted series, dividends present or labeled); TG3 time (no `LookAheadError`, canary caught, shift does not improve); TG4 controls (random matched-exposure not positive, detrended random negative, aligned foresight abnormal and rejected, shift does not improve); TG5 parity (reference vs fast path); TG6 executability (`fillable_rate` reported; calibrated or labeled `UNCALIBRATED`); TG7 statistics (`n_trials`, DSR/PBO, epochs, leave-one-epoch-out); TG8 benchmark (three measures; edge over appropriate benchmark per `acceptance.yaml`); TG9 reproduction (identical hash). Grade is computed by code: any failed critical gate ⇒ "unreliable"; all pass but `UNCALIBRATED` ⇒ "reliable with limitations"; all pass and calibrated ⇒ "reliable"; unmeasurable ⇒ "unknown".

**Deployment gates (per model), DG1–DG9:** DG1 source file and finding register complete; DG2 venue/instrument coverage and freshness; DG3 event/knowledge-time tests; DG4 complete `rule_at` registry for the model's scope; DG5 order-book/queue/lock/partial-fill tests (or `UNCALIBRATED` banner); DG6 label, friction mask, purge/embargo, fold manifest; DG7 independent reproduction of the three economic measures; DG8 model card, ownership, approval, audit log; DG9 signed manifest, kill switch, tested rollback.

**Kill-switch triggers:** missing/stale/contradictory/future-dated data or rule; unresolved instrument or venue; price outside limit or tick grid; locked book with no crossing event; book conservation violation; duplicate or impossible own-order fill; unknown margin parameter; monitoring or logging failure; hash mismatch between code, rules and manifest; no valid rollback artifact. Manual exceptions can never turn an unknown rule or missing data into an eligible trade.

**Signal gate 9 (existing code, finding D-03):** must be fail-closed; this is a separate item from TG9 and DG9.

## C.12 Evidence and source management
Status taxonomy for every claim: `verified` (primary source, date, implementation and reproducible test), `partially_verified` (some support but not the full text/date/test), `unverified`, `implementation_required`, `blocked`, `rejected` (for example a synthetic fill or an unknown rule used as known). A search-result snippet or a site domain is **not** a verified rule. Every source gets a manifest row (URL, retrieval time, publication date, effective date, hash, language, translation version, access status). Pages that could not be fetched are recorded as access failures and never used to set a parameter.

## C.13 Roadmap (unchanged order; see `REMEDIATION_PLAN.md`)
R0 freeze and baseline → R1 measurement correctness → R2 data correctness → R3 rules table and epochs → R4 validation harness and standard report → R5 ML baseline → R6 tests, controls, cleanup → R7 queue/lock/exit calibration (needs own-order data). No ML work before R4 passes. Production deployment is blocked at present: no strategy, venue, instrument or regime is production-ready on the available evidence.

---

# PART D — Parameter register: every number from the submitted material (all UNSOURCED)

Use these only as proposals to verify against official documents. Do not put them in code or in `acceptance.yaml`.

| Parameter (as submitted) | Where | Problem |
|---|---|---|
| Equity fees 0.3712% buy / 0.3712% sell + 0.5% sell tax = 1.2424%; Fara-bourse 0.3632% (1.2264%); funds 0.075% each (0.15%); gold funds 0.15%; gold/silver certificates 0.125% each (0.25%); options 0.05% each (0.10%); treasury bills 0.036% each (0.072%); rial caps (350M, 50M, 10M, 20M) | fee matrix | no source; conflicts with code SSOT (0.485% buy / 0.985% sell) and with another variant (0.00540) |
| Price-band epochs (±5%, ±10% leveraged, −2%/+6%, ±7%, ±1/±2/±3%) with dates | epoch tables | two versions disagree and overlap; no source |
| Settlement lags T+1/T+2 per instrument; cash usable at T+1 vs T+2/T+3; 12:29/12:30 and 13:30 times | ledger section | internally inconsistent; no source |
| Margin factor 1.40; option/futures margin parameters | JSON example | no source |
| Acceptance numbers (IC 0.045, ICIR 0.50, DSR 0.95, PBO 0.15, MDD 18%/22%, fillable 85%, unfillable-profit 0%, epochs ≥ 4, real +12%, USD alpha +8%, N_eff ≥ 8, days to exit ≤ 12, MCLD ≤ 3, Sharpe delta +0.35, positive regime share) | acceptance tables | owner-only; not to be set by documents |
| Queue parameters: base cancellation 15%–30%; reject if P(Fill) < 0.70; lock if ask = 0 and bid queue > 10× average minute value; lock if queue > 5× ADV; cancel_decay 0.15; Poisson iceberg | VOB sections | uncalibrated inventions; calibration requires own-order logs |
| Slippage γ1 = 0.0015, γ2 = 0.05, α = 0.5 | slippage model | uncalibrated; square-root form is a hypothesis to test |
| Leveraged ETF: σ = 40%, drag 16%/yr, spread triggers +8%/−3%, BPR < 0.8, 50-symbol basket | ETF pipeline | assumptions; structure per fund unknown |
| FX betas (gold 1.0, silver 1.15–1.35, exporters 0.15/0.85, domestic −0.30) and lags (0, 5 days, 1 day) | transmission matrix | unsupported estimates; must be estimated from data with intervals |
| GSR trade thresholds +2.5σ/−2.0σ; fair gold ×0.995; covered-call "35%–50% per year" | metals/options pipelines | strategy claims without evidence; pair trade needs shorting |
| Meta-label sizing `2·max(0.5,p)−1`, no order if p < 0.6; loss penalty θ_lock ≥ 5 | ML sections | arbitrary; to be tuned inside folds if used |
| "Halted more than 10 business days ⇒ forced exit"; embargo "≥ 5 days" | universe/CV | forced exit impossible on a halted symbol; embargo must be ≥ label horizon |
| Example run manifest values (IRR 0.4285, real 0.0812, USD 0.0435, fillable 0.912, DSR 0.971, PBO 0.082, N_eff 11.4, verdict "ACCEPTED_PRODUCTION_GRADE") | JSON | illustrative only; must not be mistaken for a result |

---

# PART E — Tested reference code (`reference_impl/`)

Small, dependency-light implementations of the corrected ideas, each with an automated test. Run: `python3 reference_impl/test_all.py` (9 tests; all pass in my run, 2026-10-12).

| File | What it does | Tested properties |
|---|---|---|
| `pit.py` | latest known version per key at `asof`; `LookAheadError` | later corrections stay invisible before their `knowledge_time` |
| `rules.py` | rules registry with scope chain, half-open intervals, overlap check per `(key, scope)`, default confidence `D`, `RuleNotFound` | overlap detection, scope precedence, half-open end, missing rule raises |
| `adjust.py` | backward adjustment for bonus, cash dividend, rights (TERP), split | no jump at the ex-date for each event type |
| `purged_cv.py` | purged walk-forward with embargo | for every train sample `label_end + embargo < test_start`; train and test disjoint (randomized) |
| `returns.py` | nominal P&L (withdrawals add), XIRR, CPI deflation, USD conversion | CPI doubling over a year turns a 100% nominal return into 0% real; FX doubling gives 0% USD |
| `queue_tracker.py` | observed-only queue position, partial fills, locked-side rule | `filled <= qty`, `ahead >= 0`, fills monotone, no event before submit, no fill until the queue ahead clears (randomized) |
| `labels.py` | executable label with ineligibility reason codes | numeric example and reason codes |

Limits: the code has no database layer, no L3 model beyond the observed tracker, and no instrument modules; the adjustment code assumes the reference price is the last raw close before the ex-date (rule `[VERIFY]` per `SPEC_VALUATION`).

---

# PART F — What only the owner can decide or supply
1. Approve ADR-001 (reference engine) and ADR-002 (`trade_date`); register `acceptance.yaml` and `reference_rates` (FX reference, risk-free, inflation index and lag).
2. Official rule sources and effective dates (price limits, base volume, fees and taxes, hours, settlement, closures, option/futures margin).
3. Whether `gregorian_date` is intentionally the sync time or an ingest bug.
4. Data: L3 or depth snapshots, real/legal flows with publication time, NAV and fund composition, IME product specs, free-market FX series with definition and timestamps, CPI with vintage, `own_order_log`.
5. Which instrument classes, in what order (suggestion: equities first; funds, metals, bonds, options later).
6. Hold-out window; capital and capacity targets.
7. Legal terms for scraped sources.
