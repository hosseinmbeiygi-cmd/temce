"""
Package intraday ticks for ALL funds (not just top 50) into compact files:

  data/all_funds_intraday/
    summary.csv     — one row per fund: symbol, name, last_trade_date,
                      ticks, volume, value, price range
    ticks.csv.gz    — every tick (symbol, trade_date, time, price, volume, canceled)
    funds/          — per-fund csv.gz (only funds with ticks)

Selection: symbols whose latest snapshot sector is
'صندوق سرمایه‌گذاری قابل معامله'. Ticks come from
brsapi_intraday_trades for each symbol's own last trade_date.
"""

import asyncio
import csv
import gzip
from pathlib import Path

from sqlalchemy import func, select

from brsapi.models.tsetmc import (
    IntradayTradeModel,
    SymbolSnapshotModel,
)
from core import database

OUT_DIR = Path("data") / "all_funds_intraday"
FUND_DIR = OUT_DIR / "funds"
BATCH = 25


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FUND_DIR.mkdir(parents=True, exist_ok=True)
    await database.init_database()

    async with database.async_session_factory() as s:
        # 1) All fund symbols (latest snapshot per symbol).
        subq = (
            select(
                SymbolSnapshotModel.symbol,
                func.max(SymbolSnapshotModel.id).label("mid"),
            )
            .where(SymbolSnapshotModel.sector == "صندوق سرمایه‌گذاری قابل معامله")
            .group_by(SymbolSnapshotModel.symbol)
            .subquery()
        )
        snap_rows = (
            await s.execute(
                select(SymbolSnapshotModel.symbol, SymbolSnapshotModel.name)
                .join(subq, SymbolSnapshotModel.id == subq.c.mid)
                .order_by(SymbolSnapshotModel.symbol)
            )
        ).all()
        names = dict(snap_rows)
        symbols = [r[0] for r in snap_rows]
        print(f"fund symbols: {len(symbols)}")

        # 2) Per-symbol last trade_date + tick stats.
        last_q = (
            await s.execute(
                select(
                    IntradayTradeModel.symbol,
                    func.max(IntradayTradeModel.trade_date),
                )
                .where(IntradayTradeModel.symbol.in_(symbols))
                .group_by(IntradayTradeModel.symbol)
            )
        ).all()
        last_date = {sym: str(d) for sym, d in last_q if d}
        active = [sym for sym in symbols if sym in last_date]
        print(f"funds with ticks: {len(active)}")

        # 3) Summary per (symbol, last_date).
        stats_sql = select(
            IntradayTradeModel.symbol,
            func.count(IntradayTradeModel.id),
            func.min(IntradayTradeModel.time),
            func.max(IntradayTradeModel.time),
            func.min(IntradayTradeModel.price),
            func.max(IntradayTradeModel.price),
            func.sum(IntradayTradeModel.volume),
            func.sum(IntradayTradeModel.price * IntradayTradeModel.volume),
        ).group_by(IntradayTradeModel.symbol)

        # 4) Stream ticks per symbol for its own last date.
        ticks_path = OUT_DIR / "ticks.csv.gz"
        summary_path = OUT_DIR / "summary.csv"
        total_ticks = 0
        with (
            gzip.open(ticks_path, "wt", encoding="utf-8", newline="") as gz,
            summary_path.open("w", encoding="utf-8", newline="") as sh,
        ):
            tw = csv.writer(gz)
            tw.writerow(["symbol", "trade_date", "time", "price", "volume", "canceled"])
            sw = csv.writer(sh)
            sw.writerow(
                [
                    "symbol",
                    "name",
                    "last_trade_date",
                    "ticks",
                    "first_time",
                    "last_time",
                    "price_min",
                    "price_max",
                    "volume",
                    "value",
                ]
            )
            for sym in active:
                d = last_date[sym]
                # stats
                st = (
                    await s.execute(
                        stats_sql.where(
                            IntradayTradeModel.symbol == sym,
                            IntradayTradeModel.trade_date == d,
                        )
                    )
                ).all()
                if not st:
                    continue
                _, n, t0, t1, pmin, pmax, vol, val = st[0]
                sw.writerow(
                    [
                        sym,
                        names.get(sym, ""),
                        d,
                        int(n or 0),
                        t0,
                        t1,
                        pmin,
                        pmax,
                        int(vol or 0),
                        float(val or 0),
                    ]
                )
                # ticks → combined file + per-fund file
                rows = (
                    await s.execute(
                        select(
                            IntradayTradeModel.time,
                            IntradayTradeModel.price,
                            IntradayTradeModel.volume,
                            IntradayTradeModel.canceled,
                        )
                        .where(
                            IntradayTradeModel.symbol == sym,
                            IntradayTradeModel.trade_date == d,
                        )
                        .order_by(IntradayTradeModel.time.asc())
                    )
                ).all()
                with gzip.open(FUND_DIR / f"{sym}.csv.gz", "wt", encoding="utf-8", newline="") as fgz:
                    fw = csv.writer(fgz)
                    fw.writerow(["time", "price", "volume", "canceled"])
                    for t, p, v, c in rows:
                        fw.writerow([t, p, v, bool(c) if c is not None else False])
                        tw.writerow([sym, d, t, p, v, bool(c) if c is not None else False])
                total_ticks += len(rows)
                if len(active) >= 10 and active.index(sym) % 50 == 0:
                    print(f"  {sym} ({active.index(sym)}/{len(active)}) ticks={len(rows):,}")

    print(f"\nwrote {summary_path} ({summary_path.stat().st_size / 1024:.1f} KB)")
    print(f"wrote {ticks_path} ({ticks_path.stat().st_size / 1024 / 1024:.1f} MB, {total_ticks:,} ticks)")
    print(f"wrote {len(active)} per-fund files in {FUND_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
