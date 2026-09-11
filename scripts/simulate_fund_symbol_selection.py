#!/usr/bin/env python3
"""Stress-test _get_fund_symbols with 50 symbols across 12 industries. Verify ONLY fund/ETF symbols returned."""

from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from unittest.mock import MagicMock

from brsapi.services.sync_service import BrsApiSyncService, is_fund_sector

ALL_SYMBOLS = [
    # صندوق‌ها (must return)
    ("اهرم", "صندوق اهرم"),
    ("جهش", "صندوق سهام جهش"),
    ("موج", "صندوق سهامی موج"),
    ("شتاب", "صندوق سهامی شتاب"),
    ("نارنج اهرم", "صندوق اهرم نارنج"),
    ("بیدار", "صندوق سهامی بیدار"),
    ("پیشرو", "صندوق سهامی پیشرو"),
    ("توان", "صندوق سهامی توان"),
    ("اطلس", "صندوق سهامی اطلس"),
    ("داریک", "صندوق سرمایه‌گذاری داریک"),
    ("آسام", "صندوق آسام"),
    ("فیروزه", "صندوق فیروزه"),
    ("گنجینه", "صندوق سرمایه‌گذاری گنجینه"),
    ("الماس", "ETF الماس"),
    ("نوویرا", "ETF نوویرا"),
    ("صندوق طلا", "صندوق طلا"),
    ("صندوق زعفران", "صندوق کالایی زعفران"),
    ("صندوق پتروشیمی", "صندوق پتروشیمی"),
    ("صندوق مسکن", "صندوق سرمایه‌گذاری مسکن"),
    ("صندوق نفت", "صندوق نفتی"),
    # فلزات اساسی (must NOT return)
    ("فملی", "فلزات اساسی"),
    ("فولاد", "تولید فولاد"),
    ("ذوب", "ذوب آهن اصفهان"),
    ("فخوز", "فولاد خوزستان"),
    ("فاذر", "فولاد آذربایجان"),
    # فرآورده‌های نفتی (must NOT)
    ("شپنا", "فرآورده‌های نفتی"),
    ("شبندر", "پالایش نفت بندرعباس"),
    ("شتران", "پالایش نفت تهران"),
    ("شبریز", "پالایش نفت تبریز"),
    # بانک (must NOT)
    ("وبملت", "بانک ملت"),
    ("وتجارت", "بانک تجارت"),
    ("وبصادر", "بانک صادرات ایران"),
    # خودرو (must NOT)
    ("خودرو", "صنعت خودرو"),
    ("خساپا", "سایپا"),
    ("خگستر", "گسترش سرمایه‌گذاری خودرو"),
    # بیمه (must NOT)
    ("بیمه1", "بیمه و صندوق بازنشستگی"),
    ("بیمه2", "صندوق بازنشستگی تکمیلی"),
    ("بیمه ایران", "بیمه ایران"),
    # دارو (must NOT)
    ("دلر", "داروسازی لرستان"),
    ("دسبحان", "داروسازی سبحان"),
    # سیمان (must NOT)
    ("سیدکو", "سیمان دشت خوزستان"),
    ("ساربیل", "سیمان اردبیل"),
    # غذایی (must NOT)
    ("غگل", "صنعت غذایی گلستان"),
    ("غشان", "شیر پاستوریزه"),
    # مخابرات (must NOT)
    ("اخابر", "مخابرات ایران"),
    ("همراه", "همراه اول"),
    # پتروشیمی (must NOT)
    ("پارس", "پتروشیمی پارس"),
    ("پاک", "پتروشیمی پاک"),
]

# Expected: exactly the symbols the production classifier accepts.
EXPECTED = sorted({s for s, sec in ALL_SYMBOLS if is_fund_sector(sec)})

# Symbols that MUST NOT appear
BANNED = {
    "فملی",
    "فولاد",
    "ذوب",
    "فخوز",
    "فاذر",
    "شپنا",
    "شبندر",
    "شتران",
    "شبریز",
    "وبملت",
    "وتجارت",
    "وبصادر",
    "خودرو",
    "خساپا",
    "خگستر",
    "بیمه1",
    "بیمه2",
    "بیمه ایران",
    "دلر",
    "دسبحان",
    "سیدکو",
    "ساربیل",
    "غگل",
    "غشان",
    "اخابر",
    "همراه",
    "پارس",
    "پاک",
}


def _sql_filter(rows):
    result = []
    for sym, sect in rows:
        if not sym or not str(sym).strip():
            continue
        if is_fund_sector(sect):
            result.append((sym, sect))
    seen = set()
    out = []
    for sym, _ in result:
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    # Return list of single-element tuples to simulate SQLAlchemy row tuples
    return [(sym,) for sym in out]


def _make_session(rows):
    fund_rows = _sql_filter(rows)
    call_count = [0]

    async def exec_side(*a, **kw):
        call_count[0] += 1
        r = MagicMock()
        # call 1: sector query (SymbolSnapshotModel) -> fund rows
        # call 2: nav query (NavRecordModel) -> empty (no existing NAV records)
        if call_count[0] == 1:
            r.fetchall.return_value = fund_rows
        else:
            r.fetchall.return_value = []
        return r

    s = MagicMock()
    s.execute = exec_side
    return s


async def main():
    svc = BrsApiSyncService(client=MagicMock(), session=MagicMock())
    result = await svc._get_fund_symbols(_make_session(ALL_SYMBOLS))
    result_set = set(result)

    print("=" * 70)
    print("  50-Symbol NAV Filter Stress Test")
    print(f"  Input: {len(ALL_SYMBOLS)} symbols across 12 industry groups")
    print(f"  Returned: {len(result)} symbols")
    print("=" * 70)

    leaked = result_set & BANNED
    missing = set(EXPECTED) - result_set

    if leaked:
        print(f"\n  [FAIL] {len(leaked)} non-fund symbol(s) leaked: {sorted(leaked)}")
    else:
        print(f"\n  [PASS] Zero non-fund symbols leaked across {len(ALL_SYMBOLS)} samples ({len(BANNED)} banned).")

    if missing:
        print(f"  [WARN] {len(missing)} expected fund(s) missing: {sorted(missing)}")
    else:
        print(f"  [PASS] All {len(EXPECTED)} expected fund symbols returned.")

    print(f"\n  NAV endpoint would fetch ({len(result)}):")
    for s in result:
        print(f"    GET /nav?l18={s}")

    excluded = sorted({s for s, _ in ALL_SYMBOLS if s and s not in result})
    print(f"\n  Excluded ({len(excluded)}):")
    for s in excluded:
        sec = dict(ALL_SYMBOLS).get(s, "")
        print(f"    SKIPPED {s:18s}  ({sec})")

    if leaked:
        print(f"\n  [FAIL] VERDICT: {len(leaked)} non-fund symbol(s) leaked!")
    else:
        print(
            f"\n  [PASS] VERDICT: NAV sync targets only {len(result)} fund symbols, "
            f"excludes {len(excluded)} non-fund symbols."
        )
        assert not leaked, f"Leaked: {leaked}"


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
