# 00_README_HANDOFF — Handoff guide for Claude Code

> This pack turns the Stage 0 audit (backtest and ML of the `temce` repo) into a staged remediation program.
> Your own reference documents (`ARCHITECTURE.md`, `SPEC_*.md`, `CLAUDE.md`, `PHASES_AND_PROMPTS.md`) take precedence. On conflict: `CLAUDE.md` > `SPEC_*` > `ARCHITECTURE.md` > this pack.
> **Language note:** the project's own spec files are written in Persian; read them as they are. This English pack only contains instructions. Stage reports may be written in English; narrative product reports stay Persian per `CLAUDE.md`.

## 1. Where files go in the repo root

```
temce/
  CLAUDE.md                      # your file; append the content of CLAUDE_ADDENDUM.md
  ARCHITECTURE.md  SPEC_*.md  PHASES_AND_PROMPTS.md      # your files
  ARCHITECTURE_BT_ML.md          # from this pack (detailed backtest + ML architecture)
  SPEC_DATA_SCHEMAS.md           # from this pack (draft; verify against real samples before relying on it)
  AUDIT_STAGE0.md                # from this pack (audit summary)
  REMEDIATION_PLAN.md            # from this pack
  CLAUDE_CODE_PROMPTS.md         # from this pack (one prompt per step)
  BASELINES.md  ADR_DRAFTS.md    # from this pack
  acceptance.yaml                # empty template; ONLY the owner fills it
  rules/rules_template.csv       # time-dependent rules table template (empty values)
  rules/RULES_COLLECTION_GUIDE.md
  audit/REPORT_FULL.md  audit/findings_new.csv    # raw audit evidence (reference, not instructions; Persian)
```

## 2. Current status

- Stage 0 (audit) is done. Verdict: **unreliable** (measurement is broken; the ML path yields zero signals; data and controls are defective).
- **Gate to enter remediation** (per `PHASES_AND_PROMPTS.md` stage 0): the owner approves the keep / rewrite / suspend table in `AUDIT_STAGE0.md` and answers the open questions.

## 3. Decisions only the owner can make (before starting)

1. **Reference engine for reports:** proposal in `ADR_DRAFTS.md` (ADR-001). Approve or reject.
2. **Trade-date column (`trade_date`)** and the meaning of `gregorian_date`: ADR-002.
3. **`acceptance.yaml`:** the owner writes the numbers before the first model run. Claude Code may not change it.
4. **Official sources for market rules:** announcements for price limits, base volume, fees, taxes, hours, settlement, closures. Without them every result stays "unreliable" (`rules/RULES_COLLECTION_GUIDE.md`).
5. **Reference rates:** FX reference, risk-free rate, inflation index and its publication lag (`acceptance.yaml`, section `reference_rates`).
6. **`SPEC_STRATEGIES.md`:** it was not among the uploaded files. If you have it, put it in the repo root; otherwise `BASELINES.md` temporarily covers the baseline needs.

## 4. How to run with Claude Code

- Give each step from `CLAUDE_CODE_PROMPTS.md` in a **fresh session**. At the end of a step Claude Code stops; read its report, approve, then start the next step.
- Reading order at the start of each session: `CLAUDE.md` > `AUDIT_STAGE0.md` > the relevant section of `REMEDIATION_PLAN.md` > the relevant SPEC > the previous step's report.
- Changes to existing files go only as **patches (diffs) in `patches/`**; applying them requires the owner's approval (per `CLAUDE.md`). New code goes in `src/` and `tests/`.
- **Claude Code must re-verify every audit finding before acting on it.** The audit was run by a different model, and the person who wrote this pack has not seen the code itself.

## 5. Safety

- Claude Code must not read `.env*` (including `.env.bak.*`, `.env.production`); block it in the tool's permission settings.
- Database: read-only user or an isolated copy; any migration is only a proposed SQL file, never executed.
- Before starting: full DB backup and `git tag pre-remediation`.
- The audit saw 6 sensitive keys on disk (names only; not tracked in git). A git-history secret scan has not been done yet.

## 6. What this pack does not promise

- Profitability of any strategy.
- Numerical correctness of any market rule (all rule values in this pack are empty).
- Whether the ML signal has an edge; this is still **unknown**, not refuted.
