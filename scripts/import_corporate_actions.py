#!/usr/bin/env python
"""Import corporate-action events into ``corporate_action_events``.

Event source (label + audit trail): **CODAL** filings.

  * ``brsapi_codal_announcements`` — «آگهی ثبت افزایش سرمایه» (2025-10 → now)
  * ``codal_reports_backup``       — «ثبت افزایش سرمایه» (2009 → 2026-07)

Ex-date + ratio source: **TSETMC's own price rebasing**, which is exact.

On an ex-date TSETMC rebases ``price_yesterday`` to the adjusted base and
reports that day's change against the rebased base (so the adjustment is
hidden from ``price_close_change_pct``). On every other trading day of a
well-behaved symbol ``price_yesterday`` equals the previous close exactly.
Verified on this DB:

    ومهان   2026-09-12  8250 → py 5500   f = 1/1.5
    سیدکو   2026-09-01 45510 → py 11380  f = 1/4
    شساخت   2026-09-02 21780 → py  4200  f = 1/5.19

so ``f = price_yesterday(ex) / price_close(ex−1)`` is TSETMC's **exact**
one-day factor, and ``ratio = 1/f − 1`` is the exact capital-increase ratio
(the same convention ``services/corporate_action_service.py`` inverts).

Why detection is guarded instead of a global threshold: in this dataset
``price_yesterday`` is only trustworthy per symbol. Across 2 231 symbols with
≥100 rows, 370 have ``price_yesterday == prev_close`` on 100 % of rows, 838 on
90-100 %, but ~750 on <30 % (those carry junk rows — e.g. ``price_close = 1``
against ``price_yesterday = 41 330``). A global ``|f−1| > ε`` filter therefore
scores ~1.25 M "events" instead of a few thousand. So a symbol is only
eligible when its own series is well-behaved (``--min-clean-rate``), and a
capital increase is only emitted when a CODAL filing corroborates the
ex-date (``--window-before``/``--window-after``). Uncorroborated days are
skipped by default: they cannot be told apart from data artefacts.

Usage::

    python scripts/import_corporate_actions.py --dry-run      # preview only
    python scripts/import_corporate_actions.py                # write events
    python scripts/import_corporate_actions.py --symbol وبانک
    python scripts/import_corporate_actions.py --include-dividends

Idempotent: upserts on ``(symbol_id, ex_date, action_type)``.

Known limitation: ``corporate_action_events.symbol_id`` has an FK to
``symbols(id)``, and ``symbols`` holds only 511 curated tickers (511 of the
2 371 tickers in the price history), so events can only be written for those.
``--report-unregistered`` prints how many detected events fall outside the
registry; ``--register-missing`` upserts the missing tickers first (see
``--register-missing`` help — it changes the registry).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg

from core.config import settings
from core.logging import get_logger

logger = get_logger("import_corporate_actions")

# A day whose price_yesterday/prev_close differs by less than this is a normal
# session. 0.5 % clears tick rounding and the 1-rial comparison tolerance.
DEFAULT_MIN_FACTOR_DEV = 0.005
# A symbol is only eligible when this share of its usable rows has
# price_yesterday == prev_close (±1 rial). Guards against junk price series.
DEFAULT_MIN_CLEAN_RATE = 0.98
# Minimum usable rows before a symbol's clean rate means anything.
DEFAULT_MIN_ROWS = 100
# Symbols per detection query. Small enough that the per-batch sort stays in
# ``work_mem`` (no ``pgsql_tmp`` spill — the whole-view variant needs GBs).
DEFAULT_BATCH_SIZE = 25
# How far a CODAL filing may sit from the ex-date to count as its source.
# Registration typically follows the ex-date by 2-10 weeks.
DEFAULT_WINDOW_BEFORE_DAYS = 120
DEFAULT_WINDOW_AFTER_DAYS = 240

# $1 = min usable rows, $2 = min clean rate, $3 = min factor deviation
# $4 = symbol batch (text[])
#
# Detection is batched by symbol on purpose. The obvious single-pass form
# (window over the whole view) makes Postgres sort all 5.45 M rows and spill it
# to ``base/pgsql_tmp`` — which fails outright on a full disk and is slow even
# when it fits. One batch of a few dozen symbols sorts a few tens of thousands
# of rows in memory, and the ``symbol = ANY(...)`` predicate is served by
# ``idx_hist_symbol_date`` so the view is never scanned in full.
_DETECT_SQL = """
WITH base AS (
    SELECT symbol, trade_date, price_close, price_yesterday,
           lag(price_close) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev_close
    FROM vw_daily_history_adjusted
    WHERE trade_date IS NOT NULL AND symbol IS NOT NULL
      AND symbol = ANY($4::text[])
), valid AS (
    SELECT * FROM base
    WHERE prev_close > 10 AND price_close > 10 AND price_yesterday > 0
), per AS (
    SELECT symbol,
           count(*) AS n,
           count(*) FILTER (WHERE abs(price_yesterday - prev_close) <= 1)::float
               / count(*) AS clean_rate
    FROM valid
    GROUP BY symbol
)
SELECT v.symbol, v.trade_date, v.prev_close, v.price_close, v.price_yesterday,
       v.price_yesterday / v.prev_close       AS f,
       per.n                                  AS n_rows,
       per.clean_rate                         AS clean_rate
FROM valid v
JOIN per USING (symbol)
WHERE per.n >= $1
  AND per.clean_rate >= $2
  -- a capital increase always rebases DOWN (f < 1); f > 1 is never one
  AND v.price_yesterday / v.prev_close < 1 - $3
ORDER BY v.symbol, v.trade_date
"""

_SYMBOLS = """
SELECT DISTINCT symbol
FROM brsapi_historical_daily
WHERE symbol IS NOT NULL
ORDER BY symbol
"""

_CODAL_CAPITAL = """
SELECT symbol, gregorian_date, summary AS title, attachment_url AS ref
FROM codal_reports_backup
WHERE summary LIKE '%ثبت افزایش سرمایه%'
  AND symbol IS NOT NULL AND gregorian_date IS NOT NULL
UNION ALL
SELECT symbol, gregorian_date, title, COALESCE(link_pdf, link) AS ref
FROM brsapi_codal_announcements
WHERE title ILIKE '%آگهی ثبت افزایش سرمایه%'
  AND symbol IS NOT NULL AND gregorian_date IS NOT NULL
"""

_SYMBOL_IDS = "SELECT symbol, id FROM symbols WHERE symbol = ANY($1::text[])"

# Auto-registration: name/isin from the newest brsapi snapshot for the ticker,
# id derived deterministically from the ticker (symbols.id is a hand-seeded
# BIGINT with no sequence, so a stable derivation is required).
_MISSING_SYMBOLS = """
SELECT DISTINCT ON (b.symbol) b.symbol, b.name, b.isin
FROM brsapi_symbol_snapshots b
WHERE b.symbol = ANY($1::text[])
ORDER BY b.symbol, b.gregorian_date DESC NULLS LAST, b.id DESC
"""

_INSERT_SYMBOL = """
INSERT INTO symbols (id, symbol, name, isin, market_type, asset_class, is_active,
                     created_at, updated_at)
VALUES ($1, $2, $3, $4, 'stock', 'equity', true, now(), now())
ON CONFLICT (symbol) DO NOTHING
"""

_UPSERT = """
INSERT INTO corporate_action_events
    (symbol_id, ex_date, action_type, ratio, dps, source, codal_ref, notes)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (symbol_id, ex_date, action_type) DO UPDATE
SET ratio = EXCLUDED.ratio,
    dps = EXCLUDED.dps,
    source = EXCLUDED.source,
    codal_ref = EXCLUDED.codal_ref,
    notes = EXCLUDED.notes
"""


@dataclass(slots=True)
class Adjustment:
    symbol: str
    ex_date: date
    prev_close: float
    close: float
    f: float  # exact one-day factor = price_yesterday / prev_close


def synthetic_symbol_id(symbol: str) -> int:
    """Stable BIGINT id for an auto-registered ticker.

    ``symbols.id`` is a hand-seeded BIGINT with no sequence and no derivable
    pattern, so a new row needs an id this script can reproduce. The value is
    deterministic in ``symbol``, positive, and bounded to ``[10**18, 10**18 +
    10**15)`` — a band no seeded id uses (seeded ids are ≤ 17 digits and <
    10**17), which keeps auto-registered tickers identifiable in the registry.
    """
    digest = hashlib.blake2b(symbol.encode("utf-8"), digest_size=8).digest()
    return 10**18 + int.from_bytes(digest, "big") % 10**15


def pick_filing(
    filings: list[tuple[date, str, str | None]],
    used: set[int],
    ex_date: date,
    before_days: int = DEFAULT_WINDOW_BEFORE_DAYS,
    after_days: int = DEFAULT_WINDOW_AFTER_DAYS,
) -> int | None:
    """Index of the CODAL filing that best explains ``ex_date``, else None."""
    best: int | None = None
    best_key: tuple[int, int] | None = None
    for i, (filed_on, _title, _ref) in enumerate(filings):
        if i in used:
            continue
        delta = (filed_on - ex_date).days
        if not (-before_days <= delta <= after_days):
            continue
        # prefer a filing that follows the ex-date (the normal CODAL
        # registration order), then the closest one.
        key = (0 if delta >= 0 else 1, abs(delta))
        if best_key is None or key < best_key:
            best_key, best = key, i
    return best


async def run(args: argparse.Namespace) -> None:
    dsn = str(settings.database_url).replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        symbols = (
            [args.symbol]
            if args.symbol
            else [r["symbol"] for r in await conn.fetch(_SYMBOLS, timeout=900)]
        )
        logger.info("scanning %d symbols in batches of %d", len(symbols), args.batch_size)

        adjustments: list[Adjustment] = []
        eligible: set[str] = set()
        thin: tuple[str, int, float] | None = None
        for start in range(0, len(symbols), args.batch_size):
            batch = symbols[start : start + args.batch_size]
            for r in await conn.fetch(
                _DETECT_SQL,
                args.min_rows,
                args.min_clean_rate,
                args.min_factor_dev,
                batch,
                timeout=900,
            ):
                adjustments.append(
                    Adjustment(
                        r["symbol"],
                        r["trade_date"],
                        float(r["prev_close"]),
                        float(r["price_close"]),
                        float(r["f"]),
                    )
                )
                eligible.add(r["symbol"])
                if thin is None or r["clean_rate"] < thin[2]:
                    thin = (r["symbol"], r["n_rows"], float(r["clean_rate"]))
            done = min(start + args.batch_size, len(symbols))
            if done % (args.batch_size * 10) < args.batch_size or done == len(symbols):
                logger.info(
                    "  %d/%d symbols — %d rebasing days so far",
                    done,
                    len(symbols),
                    len(adjustments),
                )
        logger.info(
            "detected %d rebasing days across %d eligible symbols",
            len(adjustments),
            len(eligible),
        )
        if thin:
            logger.info(
                "thinnest eligible symbol: %s (%d rows, clean_rate %.4f)", *thin
            )

        filings: dict[str, list[tuple[date, str, str | None]]] = {}
        for r in await conn.fetch(_CODAL_CAPITAL, timeout=600):
            filings.setdefault(r["symbol"], []).append(
                (r["gregorian_date"], r["title"] or "", r["ref"])
            )
        for records in filings.values():
            records.sort(key=lambda t: t[0])
        logger.info("CODAL capital-increase filings for %d symbols", len(filings))

        # ── classification (pure; needs no symbol_id) ──────────────────────
        used: dict[str, set[int]] = {}
        candidates: list[tuple[Adjustment, int, str, str | None]] = []
        matched_pairs: set[tuple[str, date]] = set()
        skipped_no_filing = 0
        skipped_ratio = 0
        for adj in adjustments:
            sym_filings = filings.get(adj.symbol, [])
            idx = pick_filing(
                sym_filings,
                used.setdefault(adj.symbol, set()),
                adj.ex_date,
                args.window_before,
                args.window_after,
            )
            if idx is None:
                skipped_no_filing += 1
                continue
            if 1.0 / adj.f - 1.0 <= 0:
                skipped_ratio += 1
                continue
            used[adj.symbol].add(idx)
            matched_pairs.add((adj.symbol, adj.ex_date))
            _filed_on, title, ref = sym_filings[idx]
            candidates.append((adj, idx, title, ref))

        matched_symbols = {c[0].symbol for c in candidates}
        logger.info(
            "capital increases corroborated by a CODAL filing: %d events / %d symbols "
            "(skipped %d without a filing, %d with a non-positive ratio)",
            len(candidates),
            len(matched_symbols),
            skipped_no_filing,
            skipped_ratio,
        )

        # ── symbol_id resolution (the FK target) ───────────────────────────
        needed = set(matched_symbols)
        if args.include_dividends:
            needed |= eligible
        ids = {
            r["symbol"]: int(r["id"])
            for r in await conn.fetch(_SYMBOL_IDS, sorted(needed), timeout=120)
        }
        missing = sorted(needed - ids.keys())
        if missing:
            logger.warning(
                "%d of %d symbols that would carry events are absent from ``symbols`` "
                "and cannot store them (FK). e.g. %s",
                len(missing),
                len(needed),
                ", ".join(missing[:10]),
            )
            if args.register_missing:
                await _register_symbols(conn, missing)
                ids.update({
                    r["symbol"]: int(r["id"])
                    for r in await conn.fetch(_SYMBOL_IDS, missing, timeout=120)
                })
                still_missing = sorted(set(missing) - ids.keys())
                logger.info(
                    "registered %d symbols; %d still missing",
                    len(missing) - len(still_missing),
                    len(still_missing),
                )
            elif args.report_unregistered:
                logger.info(
                    "re-run with --register-missing to add them to ``symbols`` "
                    "and import their events"
                )

        # ── build the rows ────────────────────────────────────────────────
        to_write: list[tuple] = []
        for adj, _idx, title, ref in candidates:
            sid = ids.get(adj.symbol)
            if sid is None:
                continue
            ratio = 1.0 / adj.f - 1.0
            to_write.append(
                (
                    sid,
                    adj.ex_date,
                    "capital_increase",
                    round(ratio, 8),
                    0.0,
                    "codal",
                    ref,
                    f"CODAL {title[:160]} | TSETMC re-based prev close "
                    f"{adj.prev_close:g}→{adj.f * adj.prev_close:g} "
                    f"(f={adj.f:.6f}, ratio={ratio:.6f})",
                )
            )

        if args.include_dividends:
            to_write.extend(_dividend_rows(adjustments, matched_pairs, ids))

        stats = {
            "capital_increase": sum(1 for r in to_write if r[2] == "capital_increase"),
            "dividend": sum(1 for r in to_write if r[2] == "dividend"),
        }
        print(
            f"eligible symbols={len(eligible)} rebasing days={len(adjustments)} "
            f"corroborated={len(candidates)} -> events={len(to_write)} "
            f"(capital_increase={stats['capital_increase']} "
            f"dividend={stats['dividend']} "
            f"unmatched={skipped_no_filing} symbols_without_filing={len(eligible) - len(matched_symbols)})"
        )

        if args.dry_run or not to_write:
            print("dry-run: nothing written")
            return

        for i in range(0, len(to_write), 500):
            await conn.executemany(_UPSERT, to_write[i : i + 500], timeout=300)
        total = await conn.fetchval("SELECT count(*) FROM corporate_action_events")
        print(f"written; corporate_action_events now holds {total} row(s)")
    finally:
        await conn.close()


async def _register_symbols(conn: asyncpg.Connection, symbols: list[str]) -> None:
    """Upsert missing tickers into ``symbols`` so their events can be stored."""
    meta = {
        r["symbol"]: (r["name"], r["isin"])
        for r in await conn.fetch(_MISSING_SYMBOLS, symbols, timeout=300)
    }
    payload = [
        (
            synthetic_symbol_id(sym),
            sym,
            (meta.get(sym, (None, None))[0] or sym)[:200],
            meta.get(sym, (None, None))[1],
        )
        for sym in symbols
    ]
    await conn.executemany(_INSERT_SYMBOL, payload, timeout=300)


def _dividend_rows(
    adjustments: list[Adjustment],
    matched_pairs: set[tuple[str, date]],
    ids: dict[str, int],
) -> list[tuple]:
    """Opt-in: emit ``dividend`` events for rebasing days with no CODAL filing.

    ``dps`` is expressed on the ex-date close basis so that the service's
    ``(close − dps)/close`` reproduces the observed factor ``f`` exactly.
    These rows are *not* corroborated by a filing — they are the residual
    after filing matching, so they can also be data artefacts. Days already
    claimed by a matched filing are skipped.
    """
    out: list[tuple] = []
    for adj in adjustments:
        if (adj.symbol, adj.ex_date) in matched_pairs:
            continue
        sid = ids.get(adj.symbol)
        if sid is None:
            continue
        dps = round(adj.close * (1.0 - adj.f), 2)
        if dps <= 0 or dps >= adj.close:
            continue
        out.append(
            (
                sid,
                adj.ex_date,
                "dividend",
                0.0,
                dps,
                "tsetmc",
                None,
                f"TSETMC re-based prev close {adj.prev_close:g}→"
                f"{adj.f * adj.prev_close:g} (f={adj.f:.6f}); "
                f"dps on the ex-date close basis (uncorroborated)",
            )
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--symbol", help="only this symbol")
    p.add_argument("--dry-run", action="store_true", help="report what would be written")
    p.add_argument(
        "--min-factor-dev",
        type=float,
        default=DEFAULT_MIN_FACTOR_DEV,
        help=f"ignore smaller rebasing than this (default {DEFAULT_MIN_FACTOR_DEV})",
    )
    p.add_argument(
        "--min-clean-rate",
        type=float,
        default=DEFAULT_MIN_CLEAN_RATE,
        help="share of a symbol's usable rows that must have "
        f"price_yesterday == prev close (default {DEFAULT_MIN_CLEAN_RATE})",
    )
    p.add_argument(
        "--min-rows",
        type=int,
        default=DEFAULT_MIN_ROWS,
        help=f"minimum usable rows per symbol (default {DEFAULT_MIN_ROWS})",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="symbols per detection query (keeps the sort in memory; "
        f"default {DEFAULT_BATCH_SIZE})",
    )
    p.add_argument("--window-before", type=int, default=DEFAULT_WINDOW_BEFORE_DAYS,
                   help=f"days a CODAL filing may precede the ex-date (default {DEFAULT_WINDOW_BEFORE_DAYS})")
    p.add_argument("--window-after", type=int, default=DEFAULT_WINDOW_AFTER_DAYS,
                   help=f"days a CODAL filing may follow the ex-date (default {DEFAULT_WINDOW_AFTER_DAYS})")
    p.add_argument(
        "--include-dividends",
        action="store_true",
        help="also emit uncorroborated ``dividend`` events for remaining rebasing days",
    )
    p.add_argument(
        "--register-missing",
        action="store_true",
        help="insert matched symbols that are absent from ``symbols`` (writes to the "
        "registry; id derived deterministically from the ticker)",
    )
    p.add_argument(
        "--report-unregistered",
        action="store_true",
        help="log symbols that cannot carry events because they are not in ``symbols``",
    )
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
