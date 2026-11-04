# ADR_DRAFTS — Draft architecture decisions (status of all: **proposed, awaiting owner approval**)

> After approval, move the rows to the ADR table in `ARCHITECTURE.md` section 20. Until approved, Claude Code must not apply them.

## ADR-001 — Reference engine for reports
- **Proposal:** the event-driven path (`BacktestEngine`, execution at the first allowed phase after the decision) is the only source of a "reportable number". Vectorized is for screening only, with a cost parameter and a signal-origin guard; every promising result is re-run on the reference engine and must match within the recorded tolerance. `BacktestSimulator` is either fixed (execute after the decision, sell from the position) or retired; `SignalBacktestEngine` takes costs only from the single shared source.
- **Why:** `SPEC_BACKTEST` sections 1 and 14; evidence A-06, C-01.
- **Validity condition:** the full code of `BacktestEngine` was not read in the audit; first run the parity and leakage tests (R1.3). Execution at the next open is not enough for the Iranian market either (locks/queues); results are reported with `fillable_rate` and the label `UNCALIBRATED` until R7.
- **Consequence:** services (`backtest_service`) switch to the reference engine.

## ADR-002 — Trade date vs ingest date
- **Proposal:** a new column `trade_date` (real trade date, derived from the Jalali `date` with a tested conversion) and `first_seen_at` (non-overwritable). Existing `gregorian_date`/`shamsi_date` are not removed; documentation calls them "ingest/sync date". No time filter on an ingest column.
- **Why:** G-01, G-02, G-03.
- **Owner question:** is `gregorian_date` intentionally the sync time, or an ingest bug? (If it is a bug, the ingest itself must be fixed.)
- **Consequence:** migration only as proposed SQL; execution by the owner.

## ADR-003 — Rule epoch and independent-sample risk
- **Proposal:** every major rule change (price limit, base volume, hours, order cap, closure) is a `regime_epoch`; the epoch id is attached to data/features/labels/reports; evaluate with leave-one-epoch-out and report `n_epochs`.
- **Why:** `SPEC_IRAN_MARKET` sections 6 and 14.

## ADR-004 — Three-measure reporting and benchmarks
- **Proposal:** all reports are nominal/real/USD with the benchmarks of `BASELINES.md`; without an edge over an appropriate benchmark a strategy is not accepted; a result that is positive only in nominal terms carries a warning.
- **Why:** `ARCHITECTURE` section 10.4, `SPEC_IRAN_MARKET` section 7.

## ADR-005 — Status of stored models and suspended modules
- **Proposal:** the 359 models in `ml_artifacts/` are `UNVERIFIED` until audited; ensemble, calibrator, regime, 10 gates, agent-based and genetic modules are `suspended` until one simple baseline passes `acceptance.yaml`.
- **Why:** F-01, F-02, `SPEC_ML` section 12 (deep models only after a baseline).
