# CLAUDE_CODE_PROMPTS — One prompt per remediation step for Claude Code

> Usage: give each step in a **fresh session**. When it ends, read the report and start the next step only after your own approval.
> All prompts begin with the shared block below (copy it above each prompt). Report format at the end of each step: the "Stage N Report" template at the end of `PHASES_AND_PROMPTS.md`.

## Shared block (above every prompt)
```
First read, in this order: CLAUDE.md (with CLAUDE_ADDENDUM appended), AUDIT_STAGE0.md, this step's section in
REMEDIATION_PLAN.md, the reference SPEC for this step, and the previous step's report (if any).
Rules: (1) Re-verify every audit finding yourself before acting (file:line + a small run); if it does not match,
report it and do not proceed. (2) Write tests first (a test that shows the bug), then fix. (3) Do not edit or
delete existing files directly; put a patch (diff) in patches/. New code in src/ and tests/. (4) DB is read-only;
migrations only as proposed SQL files. (5) Never read .env* and never print a secret value. (6) Do not invent
numbers/columns/APIs from memory; rely on real samples or documents; unknown = TODO(verify)/TODO(source).
(7) Report weak-but-honest results. (8) Every run has a run_manifest in experiments/.
(9) End of step: the stage report, then STOP; do not start the next step.
```

---

## Step R0 — Freeze and baseline
```
Reference: AUDIT_STAGE0.md, audit/REPORT_FULL.md sections A, B, E.
Goal: record the current "known-bad" state and re-verify the critical findings. Do NOT change any code in this step.

Tasks:
1) If allowed, `git tag pre-remediation`. Ask me whether a DB backup exists; do not take one yourself.
2) Rerun the baseline in experiments/R0/:
   - the ml_signal path for وپترو, وساخت, خودرو, وسپه, خبهمن; window 2024-01-01 to 2024-12-29; capital 1 billion.
   - experiments A to D on خودرو, same window (A heuristic proxy, B random seed 7, C look-ahead, D look-ahead lagged one day).
   - full pytest of tests/ (long; store raw output, do not summarize).
3) Split the 175 pytest failures into three groups: "environmental" (401/429/DB/Redis), "logical/bug", "stale".
   Table: file | count | group | exact error.
4) Re-verify these 10 critical findings: A-03, A-04, A-06, B-04, C-01, D-03, F-01, G-01, G-02, C7.
   For each: path:line, the exact code line, a small run that shows it, and a status (confirmed / rejected / unknown).
   If a finding is rejected or differs, say so explicitly.
5) Compare two identical ml_signal runs for خودرو; output must be bit-identical. If not, state the cause.
6) List anything ambiguous or unverifiable in tasks 4-5 under "Not verified", with the reason.

Deliver: experiments/R0/, the re-verification table, the failure-grouping table, the stage report.
End: STOP and wait for my approval.
```
**Gate:** `experiments/R0/` reproducible; re-verification table; your approval.

---

## Step R1 — Measurement correctness
```
Reference: REMEDIATION_PLAN.md section R1; ARCHITECTURE_BT_ML.md sections 0, 2, 5, 14; SPEC_BACKTEST.md sections 1, 2, 3, 5, 6,
13, 14; SPEC_IRAN_MARKET.md section 1; ADR_DRAFTS.md; the R0 report (experiments/R0/).
Precondition: apply ADR-001 (reference engine) only if I have approved it; if not, ask before R1.3.
Goal: trustworthy measurement in the reference engine. Add no new model, feature or rule.

Tasks (in order; each with its test first):
 R1.1 Sell sizing in MlSignalStrategy must come from the position size, not from cash. Test: after a sell signal the
      position is zero; fills do not decay to 1 share.
 R1.2 No order may fill at the decision bar's price; the first execution is after decision_time + delay. Property test:
      fill_time > decision_time; a leakage test with a look-ahead strategy aligned with the execution price (must be rejected).
 R1.3 Parity test between the reference engine and Simulator/Vectorized/SignalBacktestEngine on the simplest strategies
      (no queue). If results differ, state the cause with the code line. The full code of BacktestEngine was not read in the
      audit; read it yourself and report its limitations.
 R1.4 One cost model for all engines (currently the existing SSOT rates; R3 will wire rule_at later). Vectorized takes a
      cost parameter; SignalBacktestEngine drops the fixed 0.003. Test: each engine's rate / SSOT = 1.0.
 R1.5 ADV: pre-warm in direct runs; no silent fallback (raise or set adv_fallback=true in the output). Investigate the
      suspicious ~8.4e9 for خودرو against a hand computation from trade_volume and report (fixing the time column depends on R2; report only).
 R1.6 Vectorized rejects negative signals (NO_SHORT_ALLOWED) unless short_allowed; add the signal-origin (truncation) guard.
      Test: audit_out/_proposed_tests/test_vectorized_signal_origin.py passes.
 R1.7 Consistent, JSON-safe profit_factor; to_dict on MarketSignal; current_value in BacktestRun; empty data => explicit
      failure. Test: json.dumps without allow_nan succeeds.
 R1.8 Report MDD relative to buy-and-hold in addition to absolute. Test: MDD of two strategies with different behavior differs.

Constraints:
- Any change of results versus R0 must be reported with its cause; unexplained change = report to me.
- Ask me for the hand-computed golden (1-3 symbols, a few months); do not derive it from the code's own output.
- No random strategy with fixed 90%-of-capital sizing; the random baseline is only matched-exposure, 200 seeds (BASELINES.md BL-3).
- Until R7 run with fill_model_calibrated=false and the label UNCALIBRATED.

Deliver: patches/, tests/validity/ and tests/unit/, a before/after table on R0, the TODO(verify) list, the stage report.
End: STOP and wait for my approval.
```
**Gate:** `SPEC_BACKTEST` section 13 invariants 1, 3, 4, 5, 6, 7, 11, 12 green; hand-computed golden approved; every change versus R0 explained.

---

## Step R2 — Data correctness
```
Reference: REMEDIATION_PLAN.md section R2; SPEC_DATA_SCHEMAS.md; SPEC_VALUATION.md section 1; SPEC_DATA_SOURCES.md;
ARCHITECTURE.md section 3.
Goal: reliable data for backtesting: trade date, adjustment, cash dividends, historical universe, quality.
Constraints: table structure only from information_schema/real samples; invent no column from memory.
Tasks:
 1) trade_date and first_seen_at: design + proposed migration (SQL, do NOT execute) + Jalali/Gregorian conversion with a round-trip test.
 2) Move all time filters to trade_date (patch).
 3) Adjusted-price loading in backtest_service (patch), ex-date continuity test, reconciliation with the official/second-source series and a difference report.
 4) Cash dividends: find the data source; absence = suspended + the label "no dividend adjustment".
 5) symbol_history and a dated universe; count and list delisted symbols.
 6) DQ: a full report; do not hide failures.
 7) Investigate the ADV ~8.4e9 for خودرو against a hand computation from trade_volume.
Deliver: code/patches, proposed SQL, tests, the DQ report, a list of anomalies. End: STOP.
```
**Gate:** the stage 2 test matrix of `PHASES_AND_PROMPTS.md`; DQ report; your approval.

---

## Step R3 — Time-dependent rules table
```
Reference: REMEDIATION_PLAN.md section R3; ARCHITECTURE.md sections 4, 21, 22, 23; SPEC_IRAN_MARKET.md section 6;
rules/RULES_COLLECTION_GUIDE.md; rules/rules_template.csv.
Goal: rule_at as the only access path to rules; remove market constants from code; epochs.
Constraints: write NO rule value from memory; only the structure, tests and what I place in rules/. A row without
source_ref is confidence D and TODO(source).
Tasks: implement rules + rule_at (+ overlap/boundary/bitemporal tests); wire price_limits and rule_versioning;
remove the 0.03 placeholder; replace constants in broker.py and iran_costs.py with rule_at (patch); regime_epoch;
policy_events; market_status and the test "N-month closure with an open position"; a test reconciling limits with real daily changes.
Deliver: code, tests, a grep gate (no rule numbers in code), report. End: STOP.
```
**Gate:** stage 1 tests of the matrix; results depending on a source-less rule are "unreliable".

---

## Step R4 — Validation harness and standard report
```
Reference: REMEDIATION_PLAN.md section R4; BASELINES.md; SPEC_IRAN_MARKET.md sections 2, 3, 7, 14; SPEC_ML.md section 10;
audit/REPORT_FULL.md section B (harnesses) and E4 (proposed tests).
Goal: permanent validity tests + one report template.
Tasks: tests/validity/ with the 7 audit-proposed tests + a positive control (aligned look-ahead) and a negative control;
baselines per BASELINES.md; the standard report (three measures, benchmarks, beta, N_eff, fillable_rate labeled
UNCALIBRATED, n_epochs, n_trials, DSR/PBO, leave-one-epoch-out, run_manifest).
Constraints: invent no acceptance threshold; only read acceptance.yaml.
Deliver: code, tests, one sample report, stage report. End: STOP.
```

---

## Step R5 — ML (after R1 to R4 and after acceptance.yaml is filled)
```
Reference: REMEDIATION_PLAN.md section R5; all of SPEC_ML.md; SPEC_IRAN_MARKET.md sections 2, 3, 5, 6; acceptance.yaml
(read-only; if not registered, STOP).
Goal: an honest ML pipeline with a simple baseline; judged only by acceptance.yaml.
Tasks: fix the artifact path; an audit table of the 359 models (UNVERIFIED); labels from executable prices; walk-forward
with purge/embargo >= horizon; record n_trials; leakage guard (the canary must be detected); feature knowledge_time;
one baseline (Ridge or LightGBM) over several years/symbols; compare with BL-1..BL-3 after costs; a single-look hold-out
with time and version recorded.
Constraints: ensemble / 10 gates / deep / genetic stay suspended; after seeing the hold-out, no change for the same hypothesis.
Deliver: code, tests, model_card, standard report, stage report. End: STOP.
```

---

## Step R6 — Tests, controls, cleanup
```
Reference: REMEDIATION_PLAN.md section R6; audit/REPORT_FULL.md sections D, E, H, I.
Goal: make the meaningful tests green and fix incorrect controls.
Tasks: the 175-failure table; auth fixture; stale tests; gate 9 fail-closed (patch + test); align AUDIT_REPORT.md with
real behavior; a git-history secret scan (gitleaks/available tool; print no value); a list of root scripts with import
evidence and an archive proposal (delete nothing).
Deliver: patches/, report. End: STOP.
```

---

## Step R7 — Queue, locks and exit (only with data)
```
Prerequisite: depth/queue data or own_order_log. If absent, STOP and list the data needed.
Reference: SPEC_BACKTEST.md sections 5 to 7; SPEC_IRAN_MARKET.md sections 3 and 4; PHASES_AND_PROMPTS.md stage 4.
Goal: queue_v1, days_to_exit, joint-lock stress, real fillable_rate.
Constraint: UNCALIBRATED until calibrated; entry on a locked side without queue data = unfillable.
Deliver: code, property tests (filled <= qty, no fill before t_submit), a calibration report. End: STOP.
```
