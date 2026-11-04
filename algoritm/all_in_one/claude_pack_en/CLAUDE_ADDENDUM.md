# CLAUDE_ADDENDUM — sections to append to the end of `CLAUDE.md`

> Source: `SPEC_IRAN_MARKET.md`, `SPEC_BACKTEST.md` section 14, and the audit findings (`AUDIT_STAGE0.md`). These rules are on par with the non-negotiable rules of `CLAUDE.md`.

## Iranian market rules
1. **Long-only by default.** `short_allowed` is a time-dependent rule that defaults to false. A sell order without a position is rejected with `NO_SHORT_ALLOWED`. A "bearish signal" means exit / reduce weight, not negative exposure. No test may treat an inverted signal as a short strategy.
2. **Execution never happens at the decision bar's price.** The first allowed execution is after `decision_time` plus delay. An order on the locked side without queue data is `unfillable`. Until calibration with `own_order_log`, every queue/lock result carries the label `UNCALIBRATED`.
3. **The fast (vectorized) path is never a final report.** The reference for reports is the event-driven path (ADR-001). A promising fast-path result must be re-run on the reference path and match within the recorded tolerance.
4. **Dates:** trade date (`trade_date`) is not the ingest/sync date. No time filter may use an ingest column. Jalali/Gregorian conversion only with a tested library.
5. **Adjusted prices:** backtests and labels run on the adjusted series; adjustment comes from the events table (including cash dividends), with a continuity test and a reconciliation against the official/second-source series.
6. **Rules:** every market number only via `rule_at(key, scope, date)`. "Example"/placeholder values are forbidden. A rule without `source_ref` is confidence D, and every dependent result is "unreliable".
7. **Every backtest report must contain** (otherwise it is incomplete and not acceptable): three measures nominal/real/USD; benchmarks (buy-and-hold, equal-weight, and when data exists: gold/coin, USD, fixed-income fund, deposit); `beta` and value added beyond market timing; `N_eff`; `fillable_rate` (by score decile, with a calibration label); `n_epochs`; `n_trials`; `run_manifest`.
8. **The random baseline** is only "random with matched exposure" (200 seeds) and "random on a detrended series"; never a fixed 90%-of-cash sizing strategy that is effectively buy-and-hold.
9. **Positive-control test:** a look-ahead strategy aligned with the execution price must, on every path, either produce abnormal returns and be **rejected** by the leakage test; if it is not rejected, that path is forbidden for reporting.
10. **ML:** a model without a `model_card`, `run_manifest` and a "validated" label is not trusted (the 359 existing models are currently `UNVERIFIED`). Ensemble / 10-gate engine / agent-based / genetic modules stay `suspended` until a baseline passes `acceptance.yaml`.

## Remediation rules
11. Re-verify every finding in `AUDIT_STAGE0.md` yourself before acting (file:line, run a test). If it does not match the audit, report it and stop.
12. **Test first, then fix** (a failing test that shows the bug, then the fix). Changes to existing files only as patches in `patches/`.
13. DB read-only; migrations only as proposed SQL files; never read `.env*`; never print a secret value.
14. After every fix, record before/after output on the same R0 window so the effect of each fix is traceable; an unexplained change in results is reported to the owner.
15. Report weak-but-honest results; fixes must not be made to "improve" results.
