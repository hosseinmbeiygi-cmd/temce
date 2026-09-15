"""
Convert data/top50_funds_intraday.json (340 MB) into compact outputs:

  data/top50_funds_intraday/
    summary.csv        — 50 rows: symbol, name, last_trade_date,
                         ticks, first_time, last_time, price_min, price_max,
                         volume, value, market_value, trade_volume
    ticks.csv.gz       — every tick (symbol, time, price, volume, canceled, row)
                         streamed; ~10x smaller than JSON
    funds/{symbol}.csv.gz — per-fund tick file (only for funds with ticks)

Total: ~30-50 MB instead of 340 MB, and CSV is way faster to load than JSON.
"""

import csv
import gzip
import json
from pathlib import Path

SRC = Path("data") / "top50_funds_intraday.json"
OUT_DIR = Path("data") / "top50_funds_intraday"
FUND_DIR = OUT_DIR / "funds"

OUT_DIR.mkdir(parents=True, exist_ok=True)
FUND_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY_FIELDS = [
    "symbol",
    "name",
    "sector",
    "market_value",
    "trade_volume",
    "last_trade_date",
    "ticks",
    "first_time",
    "last_time",
    "price_min",
    "price_max",
    "volume",
    "value",
]
TICK_FIELDS = ["symbol", "time", "price", "volume", "canceled", "row"]


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    funds = data["funds"]

    # ── summary.csv ──────────────────────────────────────────────
    summary_path = OUT_DIR / "summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for f in funds:
            s = f["summary"]
            w.writerow(
                {
                    "symbol": f["symbol"],
                    "name": f.get("name") or "",
                    "sector": f.get("sector") or "",
                    "market_value": f.get("market_value") or 0,
                    "trade_volume": f.get("trade_volume") or 0,
                    "last_trade_date": f.get("last_trade_date") or "",
                    "ticks": s.get("ticks") or 0,
                    "first_time": s.get("first_time") or "",
                    "last_time": s.get("last_time") or "",
                    "price_min": s.get("price_min") or "",
                    "price_max": s.get("price_max") or "",
                    "volume": s.get("volume") or 0,
                    "value": s.get("value") or 0.0,
                }
            )
    print(f"wrote {summary_path} ({summary_path.stat().st_size / 1024:.1f} KB)")

    # ── ticks.csv.gz (all ticks, single stream) ──────────────────
    ticks_path = OUT_DIR / "ticks.csv.gz"
    total = 0
    with gzip.open(ticks_path, "wt", encoding="utf-8", newline="") as gz:
        w = csv.DictWriter(gz, fieldnames=TICK_FIELDS)
        w.writeheader()
        for f in funds:
            sym = f["symbol"]
            for t in f["ticks"]:
                row = {k: t.get(k, "") for k in TICK_FIELDS}
                row["symbol"] = sym  # parent fund supplies the symbol
                w.writerow(row)
                total += 1
    print(f"wrote {ticks_path} ({ticks_path.stat().st_size / 1024 / 1024:.1f} MB, {total:,} ticks)")

    # ── per-fund tick files ─────────────────────────────────────
    written = 0
    for f in funds:
        if not f["ticks"]:
            continue
        path = FUND_DIR / f"{f['symbol']}.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as gz:
            w = csv.DictWriter(gz, fieldnames=TICK_FIELDS[1:])  # omit symbol
            w.writeheader()
            for t in f["ticks"]:
                w.writerow({k: t.get(k, "") for k in TICK_FIELDS[1:]})
        written += 1
    print(f"wrote {written} per-fund csv.gz files in {FUND_DIR}")


if __name__ == "__main__":
    main()
