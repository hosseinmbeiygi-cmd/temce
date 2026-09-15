"""
CLI: query intraday ticks for one or more funds straight from the DB.

Examples:
  python -m scripts.cli_fund_intraday عیار
  python -m scripts.cli_fund_intraday عیار یاقوت --limit 20
  python -m scripts.cli_fund_intraday عیار --date 1405-05-18 --include-canceled
  python -m scripts.cli_fund_intraday عیار --csv out.csv
  python -m scripts.cli_fund_intraday عیار --stats    # only OHLCV, no ticks
"""

import argparse
import asyncio
import csv
from pathlib import Path

from sqlalchemy import select

from brsapi.models.tsetmc import IntradayTradeModel
from core import database


async def fetch(s, sym: str, date: str | None, limit: int, include_canceled: bool) -> dict:
    """Return (date, ticks, summary) for one symbol. Auto-pick last date if None."""
    last_date_q = (
        await s.execute(
            select(IntradayTradeModel.trade_date)
            .where(IntradayTradeModel.symbol == sym)
            .order_by(IntradayTradeModel.trade_date.desc())
            .limit(1)
        )
    ).scalar()
    target = date or str(last_date_q) if last_date_q else None
    if not target:
        return {"trade_date": None, "ticks": [], "summary": None}

    stmt = (
        select(IntradayTradeModel)
        .where(
            IntradayTradeModel.symbol == sym,
            IntradayTradeModel.trade_date == target,
        )
        .order_by(IntradayTradeModel.time.asc())
        .limit(limit)
    )
    if not include_canceled:
        stmt = stmt.where((IntradayTradeModel.canceled.is_(False)) | (IntradayTradeModel.canceled.is_(None)))
    rows = (await s.execute(stmt)).scalars().all()
    ticks = [
        {
            "time": r.time,
            "price": float(r.price) if r.price else None,
            "volume": int(r.volume) if r.volume else 0,
            "canceled": bool(r.canceled) if r.canceled is not None else False,
        }
        for r in rows
    ]
    prices = [t["price"] for t in ticks if t["price"]]
    vols = [t["volume"] for t in ticks]
    summary = None
    if prices:
        summary = {
            "count": len(ticks),
            "first_price": prices[0],
            "last_price": prices[-1],
            "price_min": min(prices),
            "price_max": max(prices),
            "volume": sum(vols),
            "value": sum(p * v for p, v in zip(prices, vols, strict=False)),
            "first_time": ticks[0]["time"],
            "last_time": ticks[-1]["time"],
        }
    return {"trade_date": target, "ticks": ticks, "summary": summary}


def _hr_print(sym: str, payload: dict, stats_only: bool) -> None:
    s = payload.get("summary")
    n = len(payload.get("ticks") or [])
    print(f"\n=== {sym}  date={payload.get('trade_date')}  ticks={n} ===")
    if not s:
        print("  no data")
        return
    print(
        f"  range=[{s['price_min']:,.0f} .. {s['price_max']:,.0f}]  "
        f"first={s['first_price']:,.0f}  last={s['last_price']:,.0f}  "
        f"change={(s['last_price'] - s['first_price']) / s['first_price'] * 100:+.2f}%"
    )
    print(
        f"  volume={s['volume']:,}  value={s['value']:,.0f}  first_time={s['first_time']}  last_time={s['last_time']}"
    )
    if stats_only:
        return
    for t in payload["ticks"][:50]:
        flag = " X" if t["canceled"] else "  "
        print(f"  {flag} {t['time']:>8}  price={t['price']:>14,.0f}  vol={t['volume']:>10,}")


def _csv_out(syms_data: list[tuple[str, dict]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "trade_date", "time", "price", "volume", "canceled"])
        w.writeheader()
        for sym, p in syms_data:
            for t in p.get("ticks", []):
                w.writerow({"symbol": sym, "trade_date": p.get("trade_date"), **t})
    print(f"wrote {path} ({path.stat().st_size / 1024:.1f} KB)")


async def amain(args: argparse.Namespace) -> None:
    await database.init_database()
    out_data: list[tuple[str, dict]] = []
    async with database.async_session_factory() as s:
        for sym in args.symbols:
            payload = await fetch(s, sym, args.date, args.limit, args.include_canceled)
            out_data.append((sym, payload))
            if not args.csv:
                _hr_print(sym, payload, args.stats)
    if args.csv:
        _csv_out(out_data, Path(args.csv))


def main() -> None:
    ap = argparse.ArgumentParser(description="Query intraday ticks for funds from the DB")
    ap.add_argument("symbols", nargs="+", help="fund symbols (e.g. عیار یاقوت)")
    ap.add_argument("--date", help="Jalali date YYYY-MM-DD (default: last available)")
    ap.add_argument("--limit", type=int, default=200, help="max ticks per symbol (default 200)")
    ap.add_argument("--include-canceled", action="store_true", help="include canceled ticks")
    ap.add_argument("--stats", action="store_true", help="only summary, no ticks")
    ap.add_argument("--csv", help="write ticks to this CSV path")
    args = ap.parse_args()
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
