"""
Live SSE tick monitor for one or more funds.

Connects to ``GET /api/v1/funds/intraday/stream`` and prints new ticks
as they arrive. Useful for watching a fund during market hours.

Examples:
  python scripts/cli_fund_intraday_stream.py عیار
  python scripts/cli_fund_intraday_stream.py عیار یاقوت طلا --poll 2
  python scripts/cli_fund_intraday_stream.py عیار --max 50 --api http://localhost:8000/api/v1
"""

import argparse
import json
import sys
import time
from collections import Counter
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _stream(url: str, headers: dict[str, str]):
    req = Request(url, headers=headers)
    with urlopen(req, timeout=60) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :]
            try:
                yield json.loads(payload)
            except json.JSONDecodeError:
                continue


def main() -> None:
    ap = argparse.ArgumentParser(description="Stream live intraday ticks via SSE")
    ap.add_argument("symbols", nargs="+", help="fund symbols (e.g. عیار یاقوت)")
    ap.add_argument("--api", default="http://127.0.0.1:8000/api/v1", help="API base URL (default: %(default)s)")
    ap.add_argument("--poll", type=float, default=5.0, help="server poll seconds (default %(default)s)")
    ap.add_argument("--max", type=int, default=200, help="max events before exiting (default %(default)s)")
    ap.add_argument("--csv", help="write ticks to this CSV path")
    args = ap.parse_args()

    params = urlencode(
        {
            "symbols": ",".join(args.symbols),
            "poll_seconds": args.poll,
            "max_events": args.max,
        }
    )
    url = f"{args.api}/funds/intraday/stream?{params}"
    print(f"connecting: {url}", file=sys.stderr)

    csv_fh = None
    csv_writer = None
    if args.csv:
        import csv

        csv_fh = open(args.csv, "w", encoding="utf-8", newline="")
        csv_writer = csv.DictWriter(csv_fh, fieldnames=["symbol", "trade_date", "time", "price", "volume", "canceled"])
        csv_writer.writeheader()
        print(f"writing csv: {args.csv}", file=sys.stderr)

    counters = Counter()
    start = time.monotonic()
    try:
        for msg in _stream(url, {"Accept": "text/event-stream"}):
            t = msg.get("type")
            if t == "heartbeat":
                print(".", end="", file=sys.stderr, flush=True)
                continue
            if t == "error":
                print(f"\nserver error: {msg}", file=sys.stderr)
                break
            if t != "ticks":
                continue
            for ev in msg.get("events") or []:
                counters[ev["symbol"]] += 1
                print(
                    f"{ev['symbol']:8} {ev.get('time', '--:--:--'):8} "
                    f"price={ev.get('price') or 0:>12,.0f}  "
                    f"vol={ev.get('volume') or 0:>10,}  "
                    f"date={ev.get('trade_date')}"
                )
                if csv_writer:
                    csv_writer.writerow(
                        {
                            "symbol": ev["symbol"],
                            "trade_date": ev.get("trade_date"),
                            "time": ev.get("time"),
                            "price": ev.get("price"),
                            "volume": ev.get("volume"),
                            "canceled": ev.get("canceled"),
                        }
                    )
            if csv_fh:
                csv_fh.flush()
            if sum(counters.values()) >= args.max:
                print(f"\nreached max events ({args.max}), stopping", file=sys.stderr)
                break
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
    except URLError as e:
        print(f"\nconnection error: {e}", file=sys.stderr)
    finally:
        if csv_fh:
            csv_fh.close()
        elapsed = time.monotonic() - start
        total = sum(counters.values())
        print(f"\nelapsed={elapsed:.1f}s  total events={total}  per-symbol={dict(counters)}", file=sys.stderr)


if __name__ == "__main__":
    main()
