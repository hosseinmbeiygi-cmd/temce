# RULES_COLLECTION_GUIDE — Building the historical rules table (ARCHITECTURE section 22)

> Without this table, per `CLAUDE.md`, every backtest result is "unreliable". This work is the owner's; Claude Code only builds the structure and tests.
> No value is provided in this pack; secondary sources (news, broker tutorials) are inconsistent and sometimes undated (`ARCHITECTURE` section 21).

## Steps
1. **List the announcements** from the start of the backtest window: daily price limit, base volume, fees, sell tax, hours, settlement, order size cap, halts and unusual closures. Source: official announcement of the exchange / securities organization / depository, or your own broker.
2. **Each row** in `rules_template.csv`: value, scope (market/board/symbol), `effective_from`/`effective_to`, `source_ref` (announcement number/date or file), `confidence` (A = official document reviewed … D = unverified), `verified_by`.
3. **Double entry** for critical items (limits, base volume, costs, settlement), or one entry plus an independent review.
4. **Explicit exceptions** (base market, funds, special symbols, halts, market-maker symbols): separate rows, never assumptions.
5. **Reconcile with data:** the real max/min daily change of each symbol must be consistent with the limit registered for that day; inconsistency = a table error or an unknown exception (test in step R3).
6. **Epoch:** every major rule change creates a new `regime_epoch` (ADR-003 in `ADR_DRAFTS.md`).

## Verification checklist (SPEC_IRAN_MARKET section 16)
- Current status of "obligated selling" (allowed symbols, price range, cost, margin, settlement, liquidity);
- complete list of regulatory changes with dates; free float, major holders, market makers and their obligations;
- DST history and the weekly working days; creation/redemption path of each fund type;
- list of option/futures symbols and specifications; automated-order restrictions and your broker's rate limits;
- historical coverage of depth/queue and real/legal investor data.

## Reminders
- "Example"/placeholder is forbidden; an empty row is better than a guessed row.
- Every row at confidence C/D must raise a warning in reports.
