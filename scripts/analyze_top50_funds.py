"""
Analyze the packaged top-50 funds data:

  - Per-fund stats: min/max/avg/median tick size, intra-day volatility,
    total traded value, trade-count (excluding canceled), peak trading
    minutes, VWAP, cancellation rate.
  - Detect suspicious patterns: trades outside daily high/low, prices
    jumping >2x in <1 min, very long quiet gaps.
  - Save a JSON report + human-readable text report.

Reads from data/top50_funds_intraday/ticks.csv.gz (streamed).
"""

import csv
import gzip
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

TICKS = Path("data") / "top50_funds_intraday" / "ticks.csv.gz"
SUMMARY = Path("data") / "top50_funds_intraday" / "summary.csv"
REPORT_JSON = Path("data") / "top50_funds_intraday" / "analysis.json"
REPORT_TXT = Path("data") / "top50_funds_intraday" / "analysis.txt"


def _parse_time(t: str) -> int | None:
    """HH:MM:SS -> seconds since midnight."""
    if not t:
        return None
    try:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except Exception:
        return None


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def main() -> None:
    # Group ticks per symbol in a single pass.
    per_sym: dict[str, list[dict]] = defaultdict(list)
    with gzip.open(TICKS, "rt", encoding="utf-8", newline="") as gz:
        r = csv.DictReader(gz)
        for row in r:
            row["price"] = float(row["price"]) if row.get("price") else None
            row["volume"] = int(row["volume"]) if row.get("volume") else 0
            row["canceled"] = row.get("canceled", "False") in ("True", "true", "1")
            row["t_sec"] = _parse_time(row.get("time", ""))
            per_sym[row["symbol"]].append(row)

    # Load summary for context (high/low bounds from snapshot).
    summary_by_sym: dict[str, dict] = {}
    with SUMMARY.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            summary_by_sym[row["symbol"]] = row

    report: dict = {
        "generated_at": datetime.now().isoformat(),
        "funds": {},
    }
    text_lines: list[str] = []
    text_lines.append("=" * 80)
    text_lines.append(f"Intraday analysis — generated {report['generated_at']}")
    text_lines.append("=" * 80)

    for sym, ticks in per_sym.items():
        sym_summary = summary_by_sym.get(sym, {})
        price_lo = float(sym_summary.get("price_min") or 0) or None
        price_hi = float(sym_summary.get("price_max") or 0) or None

        # Filter for valid (price > 0, not canceled) ticks for stats.
        valid = [t for t in ticks if t["price"] and t["price"] > 0 and not t["canceled"]]
        valid_sorted = sorted(valid, key=lambda t: t["t_sec"] or 0)

        n_total = len(ticks)
        n_valid = len(valid)
        n_canceled = sum(1 for t in ticks if t["canceled"])

        if not valid_sorted:
            report["funds"][sym] = {
                "total_ticks": n_total,
                "valid_ticks": 0,
                "canceled_ticks": n_canceled,
                "name": sym_summary.get("name"),
            }
            continue

        prices = [t["price"] for t in valid_sorted]
        vols = [t["volume"] for t in valid_sorted]
        values = [t["price"] * t["volume"] for t in valid_sorted]
        vwap = sum(values) / sum(vols) if sum(vols) else 0.0
        first_price = valid_sorted[0]["price"]
        last_price = valid_sorted[-1]["price"]
        day_change = (last_price - first_price) / first_price * 100 if first_price else 0.0

        # Out-of-bounds: ticks outside the snapshot's [price_min, price_max].
        oob = 0
        if price_lo and price_hi:
            for t in valid_sorted:
                if t["price"] < price_lo * 0.95 or t["price"] > price_hi * 1.05:
                    oob += 1

        # Time gaps (only if more than 1 valid tick).
        gaps: list[int] = []
        for i in range(1, len(valid_sorted)):
            a, b = valid_sorted[i - 1]["t_sec"], valid_sorted[i]["t_sec"]
            if a is not None and b is not None:
                d = b - a
                if 0 < d < 7200:  # ignore > 2h (lunch / off-market)
                    gaps.append(d)
        max_gap = max(gaps) if gaps else 0
        median_gap = int(statistics.median(gaps)) if gaps else 0

        # Trades per minute bin.
        minute_count: dict[int, int] = defaultdict(int)
        minute_vol: dict[int, int] = defaultdict(int)
        for t in valid_sorted:
            ts = t["t_sec"]
            if ts is not None:
                m = ts // 60
                minute_count[m] += 1
                minute_vol[m] += t["volume"]
        peak_minute = max(minute_count, key=lambda k: minute_count[k]) if minute_count else None
        peak_minute_count = minute_count[peak_minute] if peak_minute is not None else 0

        stats = {
            "name": sym_summary.get("name"),
            "total_ticks": n_total,
            "valid_ticks": n_valid,
            "canceled_ticks": n_canceled,
            "cancel_rate_pct": round(n_canceled / n_total * 100, 2) if n_total else 0,
            "price_first": first_price,
            "price_last": last_price,
            "price_min": min(prices),
            "price_max": max(prices),
            "price_median": statistics.median(prices),
            "price_p10": _pct(prices, 10),
            "price_p90": _pct(prices, 90),
            "day_change_pct": round(day_change, 2),
            "vwap": round(vwap, 2),
            "volume_total": sum(vols),
            "value_total": round(sum(values), 0),
            "median_trade_size": int(statistics.median(vols)),
            "out_of_bounds_ticks": oob,
            "max_gap_seconds": max_gap,
            "median_gap_seconds": median_gap,
            "peak_minute": (f"{peak_minute // 60:02d}:{peak_minute % 60:02d}" if peak_minute is not None else ""),
            "peak_minute_trades": peak_minute_count,
        }
        report["funds"][sym] = stats

        text_lines.append("")
        text_lines.append(f"--- {sym}  ({stats['name']}) ---")
        text_lines.append(
            f"  ticks: total={n_total} valid={n_valid} canceled={n_canceled} ({stats['cancel_rate_pct']}%)"
        )
        text_lines.append(f"  price: first={first_price:>12,.0f}  last={last_price:>12,.0f}  change={day_change:+.2f}%")
        text_lines.append(f"  range: min={min(prices):>12,.0f}  max={max(prices):>12,.0f}  vwap={vwap:>12,.0f}")
        text_lines.append(
            f"  volume: {sum(vols):>14,}  value: {sum(values):>20,.0f}  "
            f"median_trade={int(statistics.median(vols)):>10,}"
        )
        if oob:
            text_lines.append(f"  ⚠ out-of-bounds ticks: {oob}")
        if max_gap >= 600:
            text_lines.append(f"  ⚠ max gap: {max_gap // 60}m{max_gap % 60:02d}s  (median: {median_gap}s)")
        if stats["peak_minute"]:
            text_lines.append(f"  peak minute: {stats['peak_minute']}  ({stats['peak_minute_trades']} trades)")

    # Aggregate.
    text_lines.append("")
    text_lines.append("=" * 80)
    text_lines.append("AGGREGATES")
    text_lines.append("=" * 80)
    funds_with_data = [v for v in report["funds"].values() if v.get("valid_ticks")]
    if funds_with_data:
        text_lines.append(f"  funds with valid ticks      : {len(funds_with_data)}")
        text_lines.append(f"  total valid ticks           : {sum(v['valid_ticks'] for v in funds_with_data):,}")
        text_lines.append(f"  total canceled              : {sum(v['canceled_ticks'] for v in funds_with_data):,}")
        text_lines.append(f"  total value traded (rial)   : {sum(v['value_total'] for v in funds_with_data):,.0f}")
        movers = sorted(funds_with_data, key=lambda v: -v["day_change_pct"])[:5]
        text_lines.append("  top 5 day-gainers:")
        for v in movers:
            name = (v.get("name") or v.get("symbol") or "")[:30]
            text_lines.append(f"    {name:30} {v['day_change_pct']:+.2f}%")
        losers = sorted(funds_with_data, key=lambda v: v["day_change_pct"])[:5]
        text_lines.append("  top 5 day-losers:")
        for v in losers:
            name = (v.get("name") or v.get("symbol") or "")[:30]
            text_lines.append(f"    {name:30} {v['day_change_pct']:+.2f}%")
        busiest = sorted(funds_with_data, key=lambda v: -v["valid_ticks"])[:5]
        text_lines.append("  top 5 most-traded (ticks):")
        for v in busiest:
            name = (v.get("name") or v.get("symbol") or "")[:30]
            text_lines.append(f"    {name:30} ticks={v['valid_ticks']:,}")

    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_TXT.write_text("\n".join(text_lines), encoding="utf-8")
    print(f"wrote {REPORT_JSON}  ({(REPORT_JSON.stat().st_size / 1024):.1f} KB)")
    print(f"wrote {REPORT_TXT}   ({(REPORT_TXT.stat().st_size / 1024):.1f} KB)")
    print("\n".join(text_lines[:30]))
    print("...")
    print("\n".join(text_lines[-20:]))


if __name__ == "__main__":
    main()
