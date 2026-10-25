# Integration Report — Assistant «engine» (fix/engine branch)

## 1. Consumer Impacts Table

| ID | Status | Files | Consumer Test |
|----|--------|-------|---------------|
| **E-C1** | fixed | `backtest_runner.py` | `test_backtest_runner.py::test_total_return_has_realistic_magnitude`, `test_units_use_real_capital`, `test_fee_is_deducted_from_units` |
| **E-C2** | fixed | `backtest.py`, `scorer.py`, `constants.py` | `test_backtest.py::test_daily_bubble_is_trailing_not_centered`, `test_indicators.py::test_sma30_is_trailing_mean`, `test_indicators.py::test_sma30_matches_audit_number` |
| **E-H1** | fixed | `signal_engine.py` | `test_signal_engine.py::test_fetch_returns_newest_window_in_chronological_order`, `test_fetch_closes_keeps_row_order_through_fallback`, `test_rsi_uses_latest_value_not_stale_window` |
| **E-H5** | fixed | `black76.py` | `test_black76.py::test_theta_matches_finite_difference` |
| **E-L6** | fixed | `black76.py` | `test_black76.py::test_years_to_expiry_past_raises`, `test_black76.py::test_years_to_expiry_uses_tehran_today` |
| **E-M6** | fixed | `live_signals.py`, `constants.py` | `test_live_signals.py::test_price_spike_threshold_is_configurable`, `test_live_signals.py::test_bubble_extreme_threshold_is_configurable` |
| **E-M7** | fixed | `live_signals.py`, `constants.py` | `test_live_signals.py::test_stale_prev_snapshot_is_discarded`, `test_live_signals.py::test_fresh_prev_snapshot_is_unwrapped`, `test_live_signals.py::test_legacy_prev_snapshot_still_readable` |
| **E-M8** | fixed | `live_signals.py` | `test_live_signals.py::test_missing_prev_score_skips_score_signal`, `test_live_signals.py::test_missing_curr_score_skips_score_signal` |
| **E-M9** | fixed | `macro_news.py` | `test_macro_news.py::test_neutral_title_with_dash_scores_zero`, `test_macro_news.py::test_numeric_sign_drives_the_score`, `test_macro_news.py::test_confidence_is_not_a_constant` |
| **E-M10** | fixed (+ schema dep) | `macro_news.py` | `test_macro_news.py::test_scorer_does_not_consume_macro_news`, `test_macro_news.py::test_macro_module_is_documented_as_informational` |
| **E-M11** | partial | `macro_news.py` | `test_macro_news.py::test_extract_published_at_parses_jalali_date`, `test_macro_news.py::test_extract_published_at_falls_back_without_date`, `test_macro_news.py::test_dedupe_key_is_stable_and_source_scoped`, `test_macro_news.py::test_dedupe_removes_repeated_events` |
| **E-M15** | fixed | `dca_planner.py` | `test_dca_planner.py::test_ladder_is_internally_consistent`, `test_dca_planner.py::test_plan_fee_calculation`, `test_dca_planner.py::test_plan_fee_jewelry` |
| **E-M16** | fixed | `bubbler.py` | `test_pricer_bubbler.py::test_bubble_pct_none_when_fair_invalid`, `test_pricer_bubbler.py::test_implied_usd_none_when_xau_invalid` |
| **E-M17** | fixed | `pricer.py`, `bubbler.py` | `test_pricer_bubbler.py::test_pricer_and_bubbler_share_one_purity_definition` |
| **E-M18** | fixed (doc + assert) | `constants.py` | `test_pricer_bubbler.py::test_minting_costs_are_in_toman_scale` |
| **E-L2** | fixed | `scorer.py`, `constants.py` | `test_scorer.py::test_tsetmc_point_split_matches_component_weight` |
| **E-L3** | fixed | `scorer.py`, `constants.py` | `test_scorer.py::test_fund_flow_minor_drop_band_is_named` |
| **E-L4** | fixed | `scorer.py`, `constants.py` | `test_scorer.py::test_threshold_boundaries_are_inclusive` |
| **E-L1** | fixed (one item remains) | `pricer.py`, `signal_engine.py` | `test_signal_engine.py::test_dead_helpers_stay_removed` |
| **parity tests** | fixed (new coverage) | `tests/gold_desk/test_parity.py` | 6 tests |

### E-L1 — Dead Code Report

Three locations of "dead code" found via repo-wide grep (including tests, `app/`, `services/`, `jobs/`, `api/`):

- `pricer.fair_gram_weight` — truly no consumer → removed
- `signal_engine.get_xau_rsi` / `get_xau_ema` — truly no consumer → removed
- `constants.py:161` (= `REDIS_KEY_WATCHLIST`) — **has consumer**: `api.py`. Report was incorrect; unmodified code remains (Rule 6).

### Methodology Note

In three modules (`pattern_detector`, `backtest_runner`, `macro_news`) multiple IDs were fixed simultaneously in a single rewrite, so one commit covers multiple IDs:

- `9294cfa1` ⇒ E-H6, E-C3, E-M12, E-M13, E-M14
- `4fd05334` ⇒ E-C1, E-H2, E-H3, E-H4
- `9a383d3b` ⇒ E-H5, E-L6
- `fd0a0665` ⇒ E-M6, E-M7, E-M8
- `dd0b5ec9` ⇒ E-M9, E-M10, E-M11
- `2ca2c2c3` ⇒ E-M17, E-M18
- `d354fbff` ⇒ E-L2, E-L3, E-L4
- `48c78f99` ⇒ `indicators.py` module (underlying E-C2/H6, independent identifier)

All other IDs (E-C5, E-H1, E-L5, E-M16, E-M4, E-M3, E-M5, E-L7, E-L8, E-C2, E-M15, E-L1) each have their own single-commit fix.

---

## 2. Behavioral Changes Summary

### C1: `ScoreResult.decision` can be `"NO_DATA"`
- `total` remains numeric for chart display
- `hard_stop_active=True` takes priority over `NO_DATA` (RED)
- Schema must accept `NO_DATA` in `Literal` + add `raw_total`, `available_weight`, `data_coverage_pct` fields

### C2: `BubbleResult.bubble_pct` / `implied_usd` can be `None`
- `bubble_abs` remains numeric (diff with fair≤0 defines it)
- scorer computes None as "missing component"

### C3: `/snapshot`, `/score`, `/signals/recent` → HTTP 503
- Response: `{"success": false, "error": "snapshot_unavailable"}`
- No internal error text exposed (details only in logs)

### C4: `current_score` no longer read from client
- Back-end reads from snapshot server; front-end removed from send

### C5: `POST /dca/plan` returns `{"success": true, "data": DCAResponse}`
- `POST /telegram/test` also accepts `chat_id` from JSON body (query kept for compatibility)

### C6: Macro analysis is informational only
- `/macro` response includes `"affects_score": false`

### C7: `pnl_pct` can be `null`; `priced_cost` field added
- Soft-delete only (deleted_at), hard-delete with `?force=true`

### C8: `/health` — `brsapi_ok` real; Redis/DB down → HTTP 503

### C9: `/metrics` requires API-token with scope `"metrics"` (not JWT)

### C10: WebSocket cadence
- When ≥1 client connected: every 10s `{"type":"hot",...}` and every 300s `{"type":"snapshot",...}`

### C11: New motor constants only in `constants.py` (assistant 1)
- Assistant 2 adds needed constants in new `src/gold_desk/config_backend.py` without editing `constants.py`

---

## 3. Handoff Requests ( documented in `docs/fixes/handoff_engine_to_backend.md` )

1. `schemas.py`: `ScoreBlock.decision` must accept `"NO_DATA"`
2. `snapshot_service.py`: `_soft_check` must accept `None` (`bubble_pct` can be None)
3. `schemas.py`: `FundBlock.bpr` must be `float | None`
4. `api.py`: `GET /macro` must return `"affects_score": false`
5. `api.py`: `ValueError` in `/options/price` and `/options/collar` must return 400

---

## 4. Unfinished Section 8 Tests from Original Report

| # | Test | Reason |
|---|------|--------|
| 4 | `fifo_realized` with two symbols | `portfolio.py` outside my scope (another assistant on C4) |
| 9 | `compute_returns` with trade + holding | Same reason (H8 in `portfolio.py`) |

All other proposed Section 8 tests were written. Item 8 (`live_signals.detect_and_broadcast` with stale prev) was tested at the pure function `_unwrap_prev_snapshot` level, since the `detect_and_broadcast` path depends on Redis and WS and is not unit-test controllable.

---

## 5. Open Questions

1. **`NO_DATA` in UI what does it mean?** I decided `hard_stop` takes priority over `NO_DATA` (safety > data coverage). If product wants "data always insufficient" to be winner, two conditions in `scorer.compute_score` must be swapped.
2. **In `NO_DATA` state, `total` remains numeric** (per C1 and for charts) but user might see "100" and assume GREEN. Data coverage must be displayed in front-end.
3. **BrsApi currency unit (Toman or Rial?)** — Section 1 also asked this; I made no unit conversion in my scope.
4. **`COIN_MINTING_COSTS` unit**: `services/gold/constants.py` has IRR comment, `constants.py` has `..._TOMAN`. I only added a range assertion to prevent 10× error; source of truth should be unified.
5. **DXY series** in `brsapi_gold_currency_pro_daily_history` — exists and current? If not, third hard stop is effectively dead (not a bug, data absence).
6. **Risk-free rate and IV source**: Both input parameters/constants, not read from DB. Outside my fix list, but `theta` correction now shows correct sensitivity.
7. **CBI news publication date**: `cbi.ir` does not show date in HTML for any headline; if date is in the text it parses, otherwise fetch time substitutes. Product decision needed: make `published_at` nullable or use a news source with publication dates.
8. **`TRANCHE2_PULLBACK_*` thresholds and out-of-sample horizons** (3–5% adjustment, 5-day event, 30% OOS) — taken from report text, no external source.
9. **`live_signals` snapshot range assumed 300 seconds** (`LIVE_SNAPSHOT_INTERVAL_SEC`). If job runs with different interval, this constant must be read from configuration.

---

## 6. Files Touched (for pathspec-commit)

docs/fixes/engine_CHANGELOG.md
src/gold_desk/constants.py
src/gold_desk/pricer.py
src/gold_desk/bubbler.py
src/gold_desk/scorer.py
src/gold_desk/live_signals.py
src/gold_desk/dca_planner.py
src/gold_black76.py (likely typo, should be black76.py)
src/gold_desk/signal_engine.py
src/gold_desk/pattern_detector.py
src/gold_desk/backtest_runner.py
src/gold_desk/nav_checker.py
src/gold_desk/macro_news.py
src/gold_desk/parity.py
tests/gold_desk/test_parity.py
tests/gold_desk/ (updated: test_backtest_runner.py, test_black76.py, test_live_signals.py, test_macro_news.py, test_dca_planner.py, test_pricer_bubbler.py, test_scorer.py, test_pattern_detector.py, test_signal_engine.py)
indicators.py (new module)
docs/fixes/integration_report.md