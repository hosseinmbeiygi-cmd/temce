# SPEC_DATA_SCHEMAS — Draft schemas (sections 0 and 1 needed for stages 1 and 2)

> **Status: proposed.** Per `CLAUDE.md`, reconcile with real samples and `information_schema` before relying on it. The "observed" columns in section 2 come from real audit output (`audit/REPORT_FULL.md` sections C3 and G1); section 1 is a target design, not current reality.

## 0. General conventions
1. **Price unit:** rial; `decimal` (not float) in the `adjusted`/`curated` layers.
2. **Time:** UTC + `Asia/Tehran`; never a fixed offset. Dates both Gregorian (`trade_date: date`) and Jalali (`jalali_date: varchar 'YYYY-MM-DD'`); conversion only with a tested library.
3. **Bitemporal:** every record has `event_time` (the event) and `knowledge_time` (when it became available to us); `ingested_at` is the insert time; **a correction = a new version, not an overwrite**. A backtest at T sees only `knowledge_time ≤ T`. If the source has only `event_time`: a fixed conservative `assumed_latency` + flag `knowledge_time_assumed=true`.
4. **Identifier:** stable `instrument_id` (UUID) + `symbol_history`; symbols are matched in normalized form (unify Arabic/Persian "ی/ي", "ک/ك", half-space, digits), not the raw string.
5. **Layers:** `raw` → `clean` → `adjusted` → `curated`; each layer rebuildable from the previous.
6. **Explicit rejection:** an invalid row goes into `dq_rejections` with a reason; silent deletion is forbidden.

## 1. Target tables

### instruments / symbol_history
```
instruments(instrument_id PK, instrument_class, market, segment, isin NULL, created_at)
symbol_history(instrument_id, symbol_norm, symbol_raw, from_date, to_date NULL, source_ref)
```
Constraint: `symbol_history` intervals for one `instrument_id` must not overlap. Delisted symbols are not deleted (they get a `to_date`).

### calendar / market_status_events
```
calendar(date PK, jalali_date, is_trading_day, market_status, segment, source_ref)
market_status_events(event_id PK, scope(market/segment/symbol), status, from_ts, to_ts NULL, source_ref, knowledge_time)
```
`market_status ∈ {open, closed_holiday, closed_unscheduled, halted_symbol}`. Holidays have no fabricated trade records; they are dropped from volatility/Sharpe computations (not set to zero).

### rules
```
rules(rule_key, scope, value, unit, effective_from, effective_to NULL, source_ref, confidence, verified_by, knowledge_time)
```
Overlapping intervals for `(rule_key, scope)` ⇒ error. Access only via `rule_at(key, scope, date)`.

### equity_daily (data contract, ARCHITECTURE section 24)
```
keys: (instrument_id, trade_date, knowledge_time)
open, high, low, close, last: decimal rial
volume: int64; value: decimal; trade_count: int64
base_volume: int64 NULL
price_limit_upper, price_limit_lower: decimal NULL   # from rules, not from the source
status: enum {open, halted, closed, suspended}
jalali_date, regime_epoch, source_id, knowledge_time_assumed: bool
checks: low ≤ open,close ≤ high; close within limits unless a registered exception; volume,value ≥ 0; key uniqueness
freshness_sla: next trading day by 20:00
```

### corporate_actions / adjust_factors
```
corporate_actions(event_id PK, instrument_id, action_type, ex_date, ratio NULL, cash_per_share NULL,
                  record_date NULL, source, source_ref, knowledge_time)
adjust_factors(instrument_id, trade_date, adj_factor, method_version, computed_at, based_on_event_ids)
```
`action_type ∈ {bonus, cash_dividend, capital_increase_contribution, capital_increase_reserves, split, merger, rights}`. The adjustment factor comes only from this table; portfolio-value continuity test at `ex_date`; reconcile with the official/second-source series and report daily differences (`SPEC_VALUATION` section 1).

### real_legal_daily
```
(instrument_id, trade_date, buy_real_count, buy_legal_count, sell_real_count, sell_legal_count,
 buy_real_volume, buy_legal_volume, sell_real_volume, sell_legal_volume, *_value, knowledge_time)
```
Without a real `knowledge_time` ⇒ `assumed_latency` + flag; features built on it raise a warning.

### universe_log
```
(date, instrument_id, in_universe: bool, reason)   # reason for excluding each symbol each day (SPEC_ML section 1)
```

## 2. Current state (observed in the audit; not design)

| Current table | Observed columns | Problem (ID) | Migration target |
|---|---|---|---|
| `brsapi_historical_daily` (5,554,625 rows) | `symbol, date(Jalali varchar), time, trade_count, trade_volume, trade_value, price_min, price_max, price_yesterday, price_first, price_last, price_last_change, price_last_change_pct, price_close, price_close_change, price_close_change_pct, created_at, ins_id, instrument_id, updated_at, gregorian_date, shamsi_date` | `gregorian_date`/`shamsi_date` = sync date not trade date (G-01); `updated_at` ⇒ upsert overwrites; not a hypertable; no knowledge_time (G-03) | add `trade_date`, `first_seen_at`; keep the columns; `equity_daily` as a view/new layer |
| `brsapi_historical_real_legal` (4,897,659) | `symbol, date, buy/sell_real/legal_count/volume/value, gregorian_date, shamsi_date, created_at, updated_at` | same problems | `real_legal_daily` |
| `corporate_action_events` (586 rows) | `symbol_id, ex_date, action_type, ratio, dps, source, codal_ref, notes, created_at` | only `capital_increase`, all `dps=0` (C-05) | add `cash_dividend` and other types |
| `corporate_actions` | `symbol, action_type, ex_date, record_date, params, applied, source, raw_text` | **0 rows** | decide: merge with the above or drop |
| `daily_adjust_factors` (621,818) | `symbol_id, trade_date, adj_factor, computed_at` | the backtest does not use it (C-04); source/method unknown | `adjust_factors` with `method_version` |
| `vw_daily_history_adjusted` | — (view) | unused | basis for adjusted loading after reconciliation |
| `symbols` (511 rows) | — | fewer than the 2407 historical symbols (C-08) | `instruments`/`symbol_history` |
| `brsapi_nav_records` (3,588), `brsapi_gold_coin_history` (44,965), `brsapi_codal_announcements` (78,789) | unknown | no knowledge_time | enter the coverage matrix after R2 |
| `brsapi_currency_history`, `brsapi_option_snapshots` | a generic query failed (different schema) | G-06 | examine separately |

## 3. Migration (Strangler)
1. New columns/views **alongside** the current tables; dropping or changing a current column is forbidden.
2. Every migration: a proposed SQL file + a rollback test + an "old vs new" reconciliation test; the owner executes it.
3. Differences between old and new output must be explained (often a sign of an old bug).

## 4. DQ checks (auto-generated from the contract)
- Price inconsistency (low ≤ open,close ≤ high), impossible jumps, price outside the `rule_at` limit of that day.
- Negative or inconsistent volume/value; duplicates; gaps against the calendar; a holiday with trades.
- Ex-date drop: the price drop at a cash-dividend `ex_date` must be consistent with the dividend amount (no dividend event ⇒ warning).
- Difference against the second source/official series; DQ Score per dataset; below threshold ⇒ warning/stop the backtest.
