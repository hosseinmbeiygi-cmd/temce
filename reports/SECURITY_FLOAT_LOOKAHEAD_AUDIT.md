# Security / Float / Lookahead Audit — Findings & Patches (2026-10-03)

> NOTE: `FINAL_SECURITY_AUDIT_REPORT.md` does not exist in this repo
> (`security_report.html` is 0 bytes; `docs/phase3/3-7_SecurityAudit.md`
> only states the "0 High open" criterion). The findings below come from
> a fresh 602-file static audit run for this task (see `qa/sec_audit.py`).

## Tables update (user request 1) — DONE
- DB was at 0065, now at **0105 (head)**. Fixed 3 blocking migrations:
  - `0099`: try/except around DDL poisoned the txn → rewritten with
    inspector-based existence checks (columns + tables).
  - `0102`: unbounded self-join DELETE over 3.4M `quotes` rows stalled the
    live DB → guarded (0 dup groups verified, DELETE skipped), unique
    constraint `uq_quotes_symbol_date_timeframe` now enforced.
  - `0103`: `trade_ticks` / `daily_ohlcv` tables do not exist in this DB →
    guarded with `to_regclass` skip (schema drift, see INFO-1).
- `alembic check` still shows model-vs-DB drift (comments/nullables/index
  renames) — informational, no missing tables.

## Findings

| # | Severity | Location | Issue | Disposition |
|---|----------|----------|-------|-------------|
| 1 | HIGH | `src/gold_desk/backtest.py:54` | `np.convolve(mode="same")` is CENTERED: SMA30 at day *i* averaged ~16 future closes → lookahead bias inflating bubble hit-rates | **PATCHED**: trailing SMA via cumsum; numerically proven (`qa/verify_sma.py`: old leaks, new immune) |
| 2 | MEDIUM | `0099` + models: `signals.entry/stop_loss/take_profit`, `paper_trades.quantity`, `paper_equity_history.*` are `Float` | IEEE-754 rounding on money paths | Documented, NOT patched (needs Decimal schema migration + backfill; scheduled P1) |
| 3 | MEDIUM | `jobs/signal_eval_daily.py:54` | Bare `except: pass` hid notify failures in daily job | **PATCHED**: logs warning with signal id |
| 4 | LOW | 12× `text(f"...")` (auto_retrain, calibrator, market_service…) | F-string SQL | All interpolate allowlist-mapped identifiers only — NOT exploitable, no patch |
| 5 | LOW | `src/gold_desk/backtest.py:107` | `sum()` over float returns | **PATCHED**: `math.fsum` |
| 6 | INFO-1 | `0103` skip log | `trade_ticks`, `daily_ohlcv` absent in prod DB | Schema drift: confirm tables are intentionally retired or restore them |
| 7 | INFO-2 | `core/enums/provider.py:29` | `API_KEY = "api_key"` placeholder | Field-name constant, not a credential — no action |

## Verification
- `py_compile`: all touched files OK.
- `tests/unit/services/test_alert_service.py + tests/gold_desk`: **196 passed**.
- Migration chain 0065→0105 applied stepwise against the live DB.

## Readiness verdict: NO-GO (improved 32 → 48/100)
- Tables current (+8), lookahead fixed (+4), alert P0 batching + indexes (+4).
- Remaining P0 blockers: (a) live 127-view UI crawl with screenshots,
  (b) Decimal migration for money columns (finding #2),
  (c) live concurrency/idempotency proof under parallel workers,
  (d) resolve INFO-1 table drift.
- Cleared for staging/canary; not for production cutover.

## INFO-1 resolved (2026-10-03): trade_ticks/daily_ohlcv have zero references in models+code � retired tables, 0103 skips are correct. market_snapshots (still referenced) received source_timestamp.
