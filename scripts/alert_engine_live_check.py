"""Run the alert engine against the real database for a set of instruments and print the
outcome. Everything happens inside one transaction that is ROLLED BACK, so no monitor,
analysis or notification is left behind. This is the "actual data" acceptance evidence.

Usage:  python scripts/alert_engine_live_check.py [symbol ...] [--json out.json] [--assume-closed]

``--assume-closed`` evaluates freshness as if the session were closed (last-session data is
then acceptable). It is a labelled what-if for exercising the analysis outside market hours.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

DEFAULT = ["فولاد", "آگاس", "موج", "عیار", "کیان", "امینح", "ضموج834", "نمادناموجود"]
USER = "usr_alert_engine_livecheck"


async def main(symbols: list[str], out_path: str | None, assume_closed: bool = False) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from core.config import settings
    from services.alert_engine.engine import AlertEngine, EngineError

    db = create_async_engine(settings.database_url_async)
    results = []
    async with db.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        engine = AlertEngine(session, market_open_fn=(lambda: False) if assume_closed else None)
        print(f"mode: {'WHAT-IF market assumed closed' if assume_closed else 'actual market-hours clock'}")
        for symbol in symbols:
            try:
                res = await engine.activate(USER, symbol)
            except EngineError as exc:
                print(f"\n■ {symbol}: REFUSED — {exc}")
                results.append({"symbol": symbol, "refused": str(exc)})
                continue
            mon = res["monitor"]
            rep = mon["report"]
            rec, cov, m = rep["recommendation"], rep["coverage"], rep.get("market") or {}
            ident = rep["identity"]
            print(f"\n■ {symbol} → {ident['category']} ({ident['category_label']}) | ins_id={ident['ins_id']} isin={ident['isin']}")
            print(f"  basis: {ident['basis']}")
            print(f"  monitoring_state={mon['monitoring_state']}  decision={rec['state']} ({rec['state_label']})  regime={rec['regime']}")
            for r in rec["reasons"]:
                print(f"  reason: {r}")
            print("  coverage: " + ", ".join(f"{k}={v['status']}" for k, v in cov.items()))
            if m:
                q = m["queue"]
                print(f"  price={m['price_last']} spread={m['spread']['state']}/{m['spread']['pct']} queue={q['state']} "
                      f"limits=[{m['low_limit']},{m['high_limit']}] vol%={m['daily_volatility_pct']} r5={m['return_5d_pct']} r20={m['return_20d_pct']}")
            opt = rep["options"]
            print(f"  options: state={opt['state']} summary={json.dumps(opt.get('summary'), ensure_ascii=False, default=str)[:260]}")
            if rep.get("nav"):
                n = rep["nav"]
                print(f"  nav: official={n['official_nav_redemption']} date={n['official_date']} status={n['status']} premium={n['premium_pct']}")
            if rec.get("sizing"):
                s = rec["sizing"]
                print(f"  sizing: units={s['units']} binding={s.get('binding')} constraints={s.get('constraints')} reason={s.get('reason')}")
            for w in rec["activation_conditions"][:4]:
                print(f"  awaits: {w}")
            results.append({"symbol": symbol, "report": rep, "monitoring_state": mon["monitoring_state"]})

        dup = await engine.activate(USER, "موج") if "موج" in symbols else None
        if dup:
            print(f"\n■ duplicate add of موج → created={dup['created']} (same monitor id: {dup['monitor']['id'] is not None})")
        notes = await engine.list_notifications(USER)
        print(f"\n■ notifications stored: {len(notes)}")
        for n in notes[:12]:
            print(f"  [{n['severity']}] {n['title']} | telegram={n['telegram']['state']}")
        pf = await engine.portfolio_overview(USER)
        print(f"\n■ portfolio: capital={pf['allocated_capital_toman']:,.0f} cash={pf['cash_toman']:,.0f} equity={pf['equity_toman']:,.0f} "
              f"budgets={ {k: round(v) for k, v in pf['budgets_toman'].items()} } blocked={pf['blocked_new_entries']}")
        await session.close()
        await trans.rollback()
    await db.dispose()
    if out_path:
        Path(out_path).write_text(json.dumps(results, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
        print(f"\nfull reports written to {out_path}")
    print("\n(transaction rolled back — nothing persisted)")


if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        i = args.index("--json")
        out = args[i + 1]
        del args[i:i + 2]
    closed = "--assume-closed" in args
    if closed:
        args.remove("--assume-closed")
    deadline = 420.0
    if "--deadline" in args:
        i = args.index("--deadline")
        deadline = float(args[i + 1])
        del args[i:i + 2]

    async def bounded() -> None:
        # internal deadline: cancellation closes the connection, which rolls the transaction back
        await asyncio.wait_for(main(args or DEFAULT, out, closed), deadline)

    asyncio.run(bounded())
