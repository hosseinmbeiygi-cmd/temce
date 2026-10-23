#!/usr/bin/env python3
"""Resolve what "tomorrow's session" actually means for a given exchange.

"Tomorrow" is ambiguous in a way that quietly breaks news analysis: on a Friday it
is Monday, during a lunch break it is a few hours away, and a market that has been
closed all day has had no chance to price anything in. This resolves the next
session deterministically instead of relying on timezone arithmetic done in prose.

Exchange holidays are deliberately NOT built in — they change every year and a
stale hardcoded table is worse than an honest gap. Weekends are handled; holidays
are flagged for verification.

Standard library only.

    python3 session_clock.py --market IN
    python3 session_clock.py --market US --at 2026-07-31T18:00:00Z
    python3 session_clock.py --list
"""

import argparse
import json
import sys
from datetime import datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    print("error: this script needs Python 3.9+ (zoneinfo).", file=sys.stderr)
    sys.exit(2)


# session times are local to the exchange's timezone
MARKETS = {
    "US": {
        "name": "US (NYSE / NASDAQ)",
        "tz": "America/New_York",
        "sessions": [("09:30", "16:00")],
        "note": "Pre-market from 04:00 and after-hours to 20:00 trade thinly; headline "
                "reactions often show up there before the regular session.",
    },
    "IN": {
        "name": "India (NSE / BSE)",
        "tz": "Asia/Kolkata",
        "sessions": [("09:15", "15:30")],
        "note": "Pre-open auction runs 09:00-09:15. Daily price bands (circuit limits) "
                "apply to many mid and small caps — a limit-up move cannot be bought into.",
    },
    "UK": {
        "name": "UK (London Stock Exchange)",
        "tz": "Europe/London",
        "sessions": [("08:00", "16:30")],
        "note": "Opening auction from 07:50, closing auction from 16:30.",
    },
    "JP": {
        "name": "Japan (Tokyo Stock Exchange)",
        "tz": "Asia/Tokyo",
        "sessions": [("09:00", "11:30"), ("12:30", "15:30")],
        "note": "Two sessions with a midday break. The afternoon close moved from 15:00 "
                "to 15:30 on 5 Nov 2024, with a closing auction from 15:25.",
    },
    "HK": {
        "name": "Hong Kong (HKEX)",
        "tz": "Asia/Hong_Kong",
        "sessions": [("09:30", "12:00"), ("13:00", "16:00")],
        "note": "Two sessions with a midday break.",
    },
    "DE": {
        "name": "Germany (Xetra)",
        "tz": "Europe/Berlin",
        "sessions": [("09:00", "17:30")],
        "note": "Frankfurt floor trading runs longer than Xetra.",
    },
    "AU": {
        "name": "Australia (ASX)",
        "tz": "Australia/Sydney",
        "sessions": [("10:00", "16:00")],
        "note": "Opens well ahead of Europe — often the first market to price Asian news.",
    },
    "CA": {
        "name": "Canada (TSX)",
        "tz": "America/Toronto",
        "sessions": [("09:30", "16:00")],
        "note": "Shares US market hours.",
    },
    "SG": {
        "name": "Singapore (SGX)",
        "tz": "Asia/Singapore",
        "sessions": [("09:00", "12:00"), ("13:00", "17:00")],
        "note": "Two sessions with a midday break.",
    },
}


def parse_hhmm(value):
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def parse_at(value):
    """Parse an ISO-8601 instant. Naive input is treated as UTC."""
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def session_bounds(market, day):
    """Concrete (start, end) datetimes for each session on a given local date."""
    tz = ZoneInfo(market["tz"])
    bounds = []
    for start, end in market["sessions"]:
        bounds.append((
            datetime.combine(day, parse_hhmm(start), tzinfo=tz),
            datetime.combine(day, parse_hhmm(end), tzinfo=tz),
        ))
    return bounds


def is_weekend(day):
    return day.weekday() >= 5


def resolve(market, now_utc):
    tz = ZoneInfo(market["tz"])
    local = now_utc.astimezone(tz)
    today = local.date()

    status = "closed"
    detail = ""

    if is_weekend(today):
        detail = "weekend"
    else:
        for index, (start, end) in enumerate(session_bounds(market, today)):
            if start <= local < end:
                status = "open"
                detail = f"session {index + 1} of {len(market['sessions'])}"
                break
            if local < start:
                detail = "before the open" if index == 0 else "midday break"
                break
        else:
            detail = "after the close"

    # next session start strictly after now
    next_start = None
    next_end = None
    for offset in range(0, 8):
        day = today + timedelta(days=offset)
        if is_weekend(day):
            continue
        for start, end in session_bounds(market, day):
            if start > local:
                next_start, next_end = start, end
                break
        if next_start:
            break

    days_out = (next_start.date() - today).days if next_start else None

    return {
        "market": market["name"],
        "timezone": market["tz"],
        "now_utc": now_utc.isoformat(),
        "now_local": local.isoformat(),
        "status": status,
        "status_detail": detail,
        "next_session_date": next_start.date().isoformat() if next_start else None,
        "next_session_open_local": next_start.isoformat() if next_start else None,
        "next_session_close_local": next_end.isoformat() if next_end else None,
        "next_session_open_utc": next_start.astimezone(timezone.utc).isoformat() if next_start else None,
        "calendar_days_ahead": days_out,
        "note": market["note"],
    }


def render(result):
    lines = []
    lines.append(f"Market:   {result['market']}")
    lines.append(f"Timezone: {result['timezone']}")
    lines.append(f"Local:    {result['now_local']}")
    lines.append("")

    state = result["status"].upper()
    lines.append(f"Status:   {state} ({result['status_detail']})")
    lines.append("")

    if result["next_session_date"]:
        lines.append("Next session (this is what \"tomorrow\" means here)")
        lines.append(f"  date:  {result['next_session_date']}")
        lines.append(f"  opens: {result['next_session_open_local']}")
        lines.append(f"  closes:{result['next_session_close_local']}")
        lines.append(f"  opens (UTC): {result['next_session_open_utc']}")

        gap = result["calendar_days_ahead"]
        if gap and gap > 1:
            lines.append("")
            lines.append(f"  ** {gap} calendar days away — a weekend sits in between. There is more")
            lines.append("     time for the news to be absorbed, and for it to be superseded.")
    else:
        lines.append("Next session: could not resolve")

    lines.append("")
    lines.append(f"Note: {result['note']}")
    lines.append("")
    lines.append("Exchange holidays are NOT accounted for. Verify against the exchange calendar")
    lines.append("before treating the next-session date as final.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Resolve the next trading session for an exchange.",
    )
    parser.add_argument("--market", "-m", help="market code, e.g. US, IN, UK, JP")
    parser.add_argument("--at", help="ISO-8601 instant to evaluate at (default: now, UTC)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--list", action="store_true", help="list supported markets")
    args = parser.parse_args()

    if args.list or not args.market:
        if not args.list:
            print("error: --market is required\n", file=sys.stderr)
        print("Supported markets:")
        for code, market in MARKETS.items():
            hours = ", ".join(f"{s}-{e}" for s, e in market["sessions"])
            print(f"  {code:3}  {market['name']:34}  {hours}  ({market['tz']})")
        print("\nFor a market not listed, look up its hours and timezone and reason explicitly;")
        print("do not assume it follows US hours.")
        return 0 if args.list else 2

    code = args.market.upper()
    if code not in MARKETS:
        print(f"error: unknown market {code!r}. Use --list to see supported codes.", file=sys.stderr)
        return 2

    try:
        now_utc = parse_at(args.at) if args.at else datetime.now(timezone.utc)
    except ValueError:
        print(f"error: could not parse --at {args.at!r} as ISO-8601.", file=sys.stderr)
        return 2

    try:
        result = resolve(MARKETS[code], now_utc)
    except Exception as exc:  # zoneinfo data missing on some minimal systems
        print(f"error: {exc}", file=sys.stderr)
        print("If this is a timezone database problem, install tzdata.", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
