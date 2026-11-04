# Plan: Fix backtest/ML audit findings + wire into app

## 0. Correction to the audit (verified against real code)

- **F1 REJECTED** — `simulator.py` fills at current bar's close + broker-applied slippage, by design (bar-based engine, not tick). `execution_simulator.py` with "next-bar-open" is unrelated dead code. No same-bar look-ahead bug exists here. **No fix needed.** I will not implement next-bar-open fills since that would be a strategy-logic change not requested and not actually a bug.
- **Dead-code discovery**: `backtesting/optimization/walk_forward.py`, `backtesting/experiment/purged_walk_forward.py`, `backtesting/metrics/deflated_sharpe.py` are never imported by the production path (`BacktestRunner` → `BacktestSimulator`). ML training uses `training_service.py` (manual time-based split), NOT the leaky `cv_trainer.py`/`hyperparameter_tuning.py`/stacking in `boosting_models.py`.
  - This means: fixing the leaky modules matters for correctness/hygiene, but the bigger win is **deleting the leaky dead paths** and **wiring the correct dead paths (PurgedWalkForward, DSR) into production**, since right now production has *no* purge/embargo and *no* DSR/PBO at all.
- Everything else (F2–F10, M1–M9, C1–C4) is CONFIRMED or PARTIAL per the three verification sub-agent reports. Full evidence table will go in the final report.

## 1. Fix order (P0 → P1 → P2), each with a test

**P0**
1. F3 double-fill: `microstructure_engine.py` — match only the incoming order's side, not both.
2. F7 corporate actions: fix `_cutoff_index`, wire `adjust_prices_with_dates` into simulator/data layer, keep `adjust_volume` (already correct per verification).
3. M4 intrabar look-ahead: `technical_features.py` — exclude current bar from rolling windows (`[start:i]` not `[start:i+1]`), shift supporting series by 1.
4. M1/M3: delete/neuter leaky `cv_trainer.py` cross_val_score(int) and `hyperparameter_tuning.py`; replace with `TimeSeriesSplit(gap=...)` from `evaluation/cross_validation.py`. Fix `boosting_models.py` OOF stacking to use the same gapped splitter.
5. F8/F9: wire `PurgedWalkForward` into `walk_forward.py`'s optimizer path (or replace its naive split), select best params on **OOS** Sharpe + DSR, not IS sum. Fix `wf_efficiency` units.
6. C1: enforce lag contract — `ml_signal_strategy.py`/`forecast_signal_strategy.py` predictor must receive only shifted/closed-bar features, not the raw current bar with `close`.

**P1**
7. F2 latency: assign the return value of `apply_to_timestamp`; seed the RNG (deterministic jitter) for reproducible backtests.
8. F4 costs: delete legacy `backtesting/commission.py` (dead tax_pct), require per-symbol ADV (no 1_000_000 hardcode — raise if missing), keep single canonical `engine/commission.py` cost path.
9. F5/F6: PIT universe filters — add `as_of` param to `StatusFilter`/`LiquidityFilter`/`PriceFilter`; add delisted-handling (terminal value / drop from NAV at delist date rather than freezing at last close).
10. M5/M6: fix `labeling.py` volatility_regime to use rolling/expanding median not full-sample; align X/y indices explicitly with an assertion; privatize/remove unused leaky `normalize()` and ensure `selection.py` is never called pre-split (or add a guard requiring pre-split data).
11. M7/M8: cost-aware threshold optimizer (optimize net PnL/Sharpe after commission, on a dedicated calibration fold, not the test set); wire `CalibratedClassifierCV`-based calibration into `predictor.py`; fix `batch_predict` shape bug; fix AUC-on-hard-predictions and MAPE-near-zero in `evaluation/metrics.py`.
12. C2: confirm/extend walk-forward to retrain model per window (already does if using `walk_forward.py`'s `_optimize_window`); make sure the wired path actually calls model fit per window, not reused static predictions.

**P2**
13. F10: fix `win_rate` crash (no `FillEvent.net_profit` — compute from entry/exit), bar-frequency-aware annualization (don't hardcode sqrt(252)), fix `deflated_sharpe.py` to use `sharpe_max` and consistent kurtosis convention.
14. M9: validation-loss-based early stopping in `base_deep.py` (use `X_val`/`y_val` already accepted), real seed control, real version stamping (hash/timestamp) instead of `"1.0"`.
15. C3/C4: add DSR/PBO reporting with `n_trials` to the walk-forward report output; make reported Sharpe net-of-cost by construction (already true in production broker path — confirm and document).

## 2. New service layer (backend)

- New module `backtesting`/`ml` → app bridge: `services/signal_service.py` (or extend existing `services/alert_service.py` neighbor) that:
  - Reads from existing `models/signal.py` (`SignalModel`) and `models/backtest.py` (`BacktestRunModel`) — these tables already carry confidence, backtest_stats, model_version, etc. **Reuse, don't duplicate.**
  - Adds a thin ML-health view over `models/ml.py` (`MlModelVersionModel`) for `/api/model/health`.
- New endpoints in `apps/api/endpoints/` (new file `ml_signals.py`), registered in `router.py`, following existing auth pattern (public read where `signals.py`/`screener.py` are public; `Depends(get_current_user)` where user-scoped):
  - `GET /api/signals?symbol=...` — likely already covered by existing `/signals`; extend response schema to add confidence/risk/explainability/backtest_metrics/model_version if missing (verify first).
  - `GET /api/signals/gold-silver` — new, filters existing signal source to gold/silver market with metals-specific backtest metrics.
  - `GET /api/screening` — extend existing `/screener` response with ML fields rather than new endpoint, if that matches existing frontend usage.
  - `GET /api/alerts` — already exists; extend creation path to support cost-aware ML-threshold alerts.
  - `GET /api/backtest/summary?strategy=...` — extend existing `/backtests` endpoints if a summary view doesn't already exist.
  - `GET /api/model/health` — new, surfaces last retrain time, drift flag, DSR/PBO of current production model from `MlModelVersionModel.metrics`.
  - Cache via existing `core/cache_manager.py` `get_or_compute`, gate rollout via `core/feature_flags` (`USE_BACKTEST_SIGNALS`).
- I will verify exact current response schemas of `/signals`, `/screener`, `/backtests`, `/alerts` before deciding "extend" vs "add new" for each, since duplicating existing endpoints would violate "preserve public APIs."

## 3. Frontend integration

- Reuse `components/signals/SignalCard.tsx` (already has confidence gauge, grade badges, direction) — extend its prop type with `risk_score`, `backtest_metrics`, `explainability` if not already present (verify first).
- New shared components (per request): `BacktestSummary`, `RiskBadge`, `AlertToggle`, `ExplanationPanel`, `ModelHealthIndicator` — build only what doesn't already exist (e.g. `AuditBadge.tsx`/`SignalBadge.tsx` may cover RiskBadge needs; check before creating a duplicate).
- Wire into: `screener`/`smart-screener` pages, `markets/gold` + `markets/silver` pages, `alerts` page, symbol detail page. Add a small `ModelHealthIndicator` to the app header/footer layout.
- Use existing React Query setup for data fetching; follow `goldApi.ts`/`currencyApi.ts` pattern for a new `signalsApi.ts` if needed.

## 4. Testing

- Python unit tests (pytest, matching existing test layout — will check `tests/` structure first) for each P0/P1 fix: double-fill, corporate action cutoff, intrabar shift, gapped CV, purge/embargo gap enforcement, lag contract, cost-aware threshold, calibration wiring.
- Leakage test: assert feature at bar i uses no data from bar i or later.
- Purge/embargo test: assert train/val gap >= horizon + max_window.
- Cost-aware test: assert chosen threshold maximizes net-of-cost objective, not raw F1.
- API integration tests for new/extended endpoints (schema + auth).
- Frontend: component render tests for new/extended components if a test runner (Jest/Vitest/RTL) is already configured — will check before adding a new one.

## 5. Walk-forward rerun & report

- Run the now-wired PurgedWalkForward end to end on available data, record: net Sharpe, MaxDD, turnover, DSR/PBO with n_trials, OOS vs IS gap, cost sensitivity (×0.5/×1/×2), regime stability (bull/bear/high-vol split).
- Compare against whatever baseline numbers exist in any current backtest report/DB rows (if none exist, state that clearly and report only post-fix numbers — per audit, "claimed backtest report" was listed as missing input).
- Final report deliverable: executive summary, confirm/reject table (already drafted from verification), before/after evidence, test results, reliability scores (0-100) for backtest/ML/overall, 7/30/90-day plan, open questions.

## 6. Explicit assumptions (will state in final report)

- No raw data sample / holiday calendar / original claimed backtest numbers were provided — baseline comparison will be "before" = current code behavior measured now, not historical claimed results.
- Universe = current active symbols per existing DB, TSE ±5% limit + T+1 enforced per original assumption.
- Will not change strategy logic — only leakage/correctness fixes, per constraint.
