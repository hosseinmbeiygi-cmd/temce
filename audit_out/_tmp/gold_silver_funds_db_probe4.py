"""DB probe 4 (SELECT-only) — داده واقعی مسیر /funds و پیش‌نیازهای GoldDesk snapshot."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402
from core import database  # noqa: E402


def is_silver(n: str) -> bool:
    import re

    return bool(re.search(r"نقره|سیلور|silver|xag|ag999|ag925", n, re.I))


async def main() -> None:
    await database.init_database()
    f = database.async_session_factory
    if f is None:
        print("no db factory")
        return
    async with f() as s:
        print("=" * 72)
        print("A) مسیر واقعی /funds (apps/api/endpoints/funds.py::_load_merged_funds)")
        print("=" * 72)
        from apps.api.endpoints.funds import _load_merged_funds  # noqa: E402

        merged = await _load_merged_funds(s)
        print(f"   merged funds: {len(merged)}")
        by_market: dict[str, int] = {}
        for v in merged.values():
            by_market[v.get("market") or "?"] = by_market.get(v.get("market") or "?", 0) + 1
        print(f"   by market: {by_market}")

        ime = [v for v in merged.values() if v.get("market") == "ime"]
        print(f"   market=ime (چیزی که صفحه نقره می‌خواند): {len(ime)}")

        silver = [v for v in merged.values() if is_silver(f"{v.get('name')} {v.get('symbol')}")]
        print(f"   silver-matching funds در کل merged: {len(silver)}")
        for v in silver[:10]:
            print(
                f"     symbol={v.get('symbol')!r} market={v.get('market')!r} "
                f"fund_type={v.get('fund_type')!r} nav={v.get('nav')} price_last={v.get('price_last')}"
            )

        silver_ime = [v for v in ime if is_silver(f"{v.get('name')} {v.get('symbol')}")]
        silver_pass = [
            v
            for v in silver
            if (v.get("nav") or 0) > 0 or (v.get("price_last") or 0) > 0
        ]
        print(f"   silver در market=ime: {len(silver_ime)}")
        print(f"   silver با nav/price>0 (شرط فیلتر صفحه): {len(silver_pass)}")

        gold_ime = [
            v
            for v in ime
            if any(k in f"{v.get('name')} {v.get('symbol')}" for k in ("طلا", "زر"))
        ]
        print(f"   طلا/زر در market=ime: {len(gold_ime)}")
        with_price = [v for v in gold_ime if (v.get("price_last") or 0) > 0]
        with_nav = [v for v in gold_ime if (v.get("nav") or 0) > 0]
        print(f"   از این‌ها price_last>0: {len(with_price)}   nav>0: {len(with_nav)}")
        for v in gold_ime[:6]:
            print(
                f"     symbol={v.get('symbol')!r} nav={v.get('nav')} price_last={v.get('price_last')} "
                f"bubble? nav/price={v.get('nav')}/{v.get('price_last')}"
            )

        print("=" * 72)
        print("B) منابع قیمت GoldDesk snapshot")
        print("=" * 72)
        from brsapi.services.query_service import BrsApiQueryService  # noqa: E402

        print("   hasattr(BrsApiQueryService, 'get_fund_prices') =", hasattr(BrsApiQueryService, "get_fund_prices"))
        svc = BrsApiQueryService(session=s)
        gold_rows = await svc.get_gold_coin_prices()
        print(f"   get_gold_coin_prices(): {len(gold_rows)} rows; symbols={[r.get('symbol') for r in gold_rows][:12]}")
        fx_rows = await svc.get_currency_prices()
        print(f"   get_currency_prices(): {len(fx_rows)} rows; symbols={[r.get('symbol') for r in fx_rows][:20]}")
        comm = await svc.get_commodity_prices(category="precious_metal")
        print(f"   get_commodity_prices(precious_metal): {len(comm)} rows; symbols={[r.get('symbol') for r in comm][:12]}")

        print("=" * 72)
        print("C) جداول زیربنایی")
        print("=" * 72)
        for t, cond in (
            ("brsapi_commodity_prices", "1=1"),
            ("brsapi_currency_prices", "1=1"),
            ("brsapi_ime_funds", "1=1"),
        ):
            try:
                rows = (
                    await s.execute(text(f"SELECT COUNT(*) FROM {t} WHERE {cond}"))
                ).scalar()
                print(f"   {t:<26} rows={rows}")
            except Exception as exc:
                print(f"   {t:<26} ERROR {type(exc).__name__}: {str(exc)[:80]}")
                await s.rollback()

        for q in (
            "SELECT symbol, category, price FROM brsapi_commodity_prices ORDER BY symbol LIMIT 20",
            "SELECT symbol FROM brsapi_currency_prices ORDER BY symbol LIMIT 25",
            "SELECT symbol, name, price_last, nav FROM brsapi_ime_funds WHERE name ILIKE '%عیار%' OR name ILIKE '%طلا%' LIMIT 8",
        ):
            try:
                rows = (await s.execute(text(q))).all()
                print("   ", [tuple(r) for r in rows])
            except Exception as exc:
                print("   ERROR", type(exc).__name__, str(exc)[:100])
                await s.rollback()


asyncio.run(main())
