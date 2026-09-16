"""
Fetch complete intraday (in-day) tick data for the top 50 funds.

Selection criterion: market_value from the latest brsapi_symbol_snapshots
row (descending). We pick funds whose sector is a fund OR the symbol is
in the known ETF list, then sort by market_value and take the top 50.

Source: brsapi_intraday_trades for the most recent trade_date that has
ticks for any of those top funds (data may lag calendar today by
weekends/holidays).
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import text

from brsapi.constants import BRSAPI_ETF_SYMBOLS
from core import database
from core.time import now_utc

OUT = Path("data") / "top50_funds_intraday.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

TOP_N = 50
BATCH = 10  # IN clause size to avoid huge parameter sets


async def main() -> None:
    await database.init_database()
    factory = database.async_session_factory
    out: dict = {
        "generated_at": now_utc().isoformat(),
        "selection": "market_value",
        "criterion_top_n": TOP_N,
        "funds": [],
    }

    async with factory() as s:
        # We do NOT use a single global trade_date — each fund's last trading
        # day is queried independently (BrsApi may have stale days or missing
        # ones for a single symbol). The summary will report per-fund dates.

        # 1) Top 50 funds by market_value from latest snapshot per symbol.
        rank_sql = text("""
            WITH latest AS (
                SELECT DISTINCT ON (symbol) symbol, name, sector, market_value, trade_volume
                FROM brsapi_symbol_snapshots
                WHERE market_value > 0
                ORDER BY symbol, fetched_at DESC
            )
            SELECT symbol, name, sector, market_value, trade_volume
            FROM latest
            WHERE sector = :fund_sector
               OR symbol = ANY(:etf_syms)
            ORDER BY market_value DESC
            LIMIT :top_n
        """)
        rows = (
            await s.execute(
                rank_sql,
                {
                    "fund_sector": "صندوق سرمایه‌گذاری قابل معامله",
                    "etf_syms": list(BRSAPI_ETF_SYMBOLS),
                    "top_n": TOP_N,
                },
            )
        ).all()
        if not rows:
            print("no fund snapshots found")
            return

        symbols = [r[0] for r in rows]
        print(f"selected {len(symbols)} funds; head={symbols[:5]}")

        # 2) Per-symbol last trade_date (each fund may have its own latest day).
        last_date_sql = text("""
            SELECT symbol, MAX(trade_date) AS last_date
            FROM brsapi_intraday_trades
            WHERE symbol = ANY(:syms)
            GROUP BY symbol
        """)
        last_dates: dict[str, str | None] = dict.fromkeys(symbols)
        for sym, d in (await s.execute(last_date_sql, {"syms": symbols})).all():
            last_dates[sym] = str(d) if d else None

        # 3) Per-symbol intraday summary (ticks/ohlc/volume/value).
        summary_sql = text("""
            SELECT symbol, COUNT(*) AS n,
                   MIN(time) AS first_time, MAX(time) AS last_time,
                   MIN(price) AS price_min, MAX(price) AS price_max,
                   SUM(volume) AS vol_sum,
                   SUM(price * volume) AS val_sum
            FROM brsapi_intraday_trades
            WHERE symbol = ANY(:syms)
            GROUP BY symbol
        """)
        meta = {
            sym: {
                "ticks": 0,
                "first_time": None,
                "last_time": None,
                "price_min": None,
                "price_max": None,
                "volume": 0,
                "value": 0.0,
            }
            for sym in symbols
        }
        for sym, n, t0, t1, pmin, pmax, vsum, valsum in (await s.execute(summary_sql, {"syms": symbols})).all():
            meta[sym].update(
                ticks=n,
                first_time=t0,
                last_time=t1,
                price_min=pmin,
                price_max=pmax,
                volume=int(vsum or 0),
                value=float(valsum or 0.0),
            )

        # 4) Pull full ticks (chronological) for the 50 funds in batches.
        ticks_sql = text("""
            SELECT symbol, time, price, volume, canceled, row
            FROM brsapi_intraday_trades
            WHERE symbol = ANY(:syms)
            ORDER BY symbol, time ASC
        """)

        per_sym: dict[str, list] = {sym: [] for sym in symbols}
        for i in range(0, len(symbols), BATCH):
            batch = symbols[i : i + BATCH]
            result = await s.execute(ticks_sql, {"syms": batch})
            for sym, t, p, v, c, r in result.all():
                per_sym[sym].append(
                    {
                        "time": t,
                        "price": float(p) if p is not None else None,
                        "volume": int(v) if v is not None else 0,
                        "canceled": bool(c) if c is not None else False,
                        "row": int(r) if r is not None else None,
                    }
                )

        # 5) Assemble output
        for sym, name, sector, mv, tv in rows:
            m = meta[sym]
            entry = {
                "symbol": sym,
                "name": name,
                "sector": sector,
                "market_value": float(mv or 0),
                "trade_volume": int(tv or 0),
                "last_trade_date": last_dates[sym],
                "summary": m,
                "ticks": per_sym[sym],
            }
            out["funds"].append(entry)

    out["summary"] = {
        "fund_count": len(out["funds"]),
        "total_ticks": sum(len(f["ticks"]) for f in out["funds"]),
        "with_ticks": sum(1 for f in out["funds"] if f["summary"]["ticks"] > 0),
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    print(f"summary: {out['summary']}")


if __name__ == "__main__":
    asyncio.run(main())
