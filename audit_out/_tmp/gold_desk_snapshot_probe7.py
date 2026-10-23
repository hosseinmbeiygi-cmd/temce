"""Probe 7 (SELECT-only) — اجرای واقعی مسیر GoldDesk snapshot + امتیاز.

هیچ نوشتنی روی DB انجام نمی‌شود؛ فقط خواندن و محاسبه.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from core import database  # noqa: E402


async def main() -> None:
    from brsapi.models import NavRecordModel  # noqa: E402

    print("=" * 72)
    print("A) NavRecordModel — وجود ستون nav که nav_checker می‌خواند")
    print("=" * 72)
    print("   hasattr(NavRecordModel, 'nav') =", hasattr(NavRecordModel, "nav"))
    print("   hasattr(NavRecordModel, 'nav_issue') =", hasattr(NavRecordModel, "nav_issue"))
    try:
        NavRecordModel.nav  # noqa: B018
        print("   attribute access: OK")
    except Exception as exc:
        print(f"   attribute access: {type(exc).__name__}: {exc}")

    await database.init_database()
    f = database.async_session_factory
    if f is None:
        print("no db factory")
        return

    from gold_desk.constants import FUND_SYMBOLS, SCORE_WEIGHTS, SCORE_GREEN_MIN, SCORE_YELLOW_MIN  # noqa: E402
    from gold_desk import nav_checker, scorer  # noqa: E402

    async with f() as s:
        print("=" * 72)
        print("B) nav_checker.get_all_funds_status برای ۱۰ صندوق طلا (DB زنده، فقط SELECT)")
        print("=" * 72)
        try:
            sts = await nav_checker.get_all_funds_status(s, FUND_SYMBOLS)
            print(f"   returned: {len(sts)} funds (از {len(FUND_SYMBOLS)} نماد درخواستی)")
            for st in sts[:5]:
                print("   ", st)
        except Exception as exc:
            print("   ERROR:", type(exc).__name__, str(exc)[:200])

        print("=" * 72)
        print("C) ceil امتیاز با ورودی‌های بهینه (bubble=0، RSI/NAV ناموجود)")
        print("=" * 72)
        best = scorer.compute_score(
            bubble_pct=0.0,
            nav_bubble_pct=None,
            bpr=10.0,
            net_inflow=1e12,
            xau_rsi=None,
            aed_gap_pct=0.0,
            nav_7d_pct=None,
        )
        print(f"   weights: {SCORE_WEIGHTS} (sum={sum(SCORE_WEIGHTS.values())})")
        print(f"   components: { {k: (v.value, v.max_value, v.reason) for k, v in best.components.items()} }")
        print(f"   total={best.total}  decision={best.decision}  (GREEN>={SCORE_GREEN_MIN}، YELLOW>={SCORE_YELLOW_MIN})")

        best2 = scorer.compute_score(
            bubble_pct=-1.0,
            nav_bubble_pct=0.0,
            bpr=10.0,
            net_inflow=1e12,
            xau_rsi=40.0,
            aed_gap_pct=0.0,
            nav_7d_pct=5.0,
        )
        print(f"   [سناریوی فرضی با داده کامل] total={best2.total} decision={best2.decision}")

        print("=" * 72)
        print("D) build_snapshot واقعی (فقط SELECT)")
        print("=" * 72)
        from gold_desk.snapshot_service import build_snapshot  # noqa: E402

        try:
            snap = await build_snapshot(s)
            print(f"   snapshot_at={snap.snapshot_at}  source={snap.references.source}  quality={snap.quality_flag}")
            print(f"   refs: xau={snap.references.xau_usd} usd={snap.references.usd_irt} aed={snap.references.aed_irt} "
                  f"gap={snap.references.aed_gap_pct:.3f}%")
            print(f"   gold blocks={len(snap.gold)} coins={len(snap.coins)} funds={len(snap.funds)}")
            for k, v in list(snap.coins.items())[:3]:
                print(f"     coin {k}: market={v.market_price} fair={v.fair_value} bubble={v.bubble_pct}")
            for k, v in list(snap.gold.items())[:3]:
                print(f"     gold {k}: market={v.market_price} fair={v.fair_value} bubble={v.bubble_pct}")
            sc = snap.score
            print(f"   score total={sc.total} decision={sc.decision} hard_stop={sc.hard_stop_active}")
            print(f"     bubble={sc.components.bubble} ({sc.components.bubble_reason})")
            print(f"     nav={sc.components.nav} ({sc.components.nav_reason})")
            print(f"     tsetmc={sc.components.tsetmc} ({sc.components.tsetmc_reason})")
            print(f"     technical={sc.components.technical} ({sc.components.technical_reason})")
            print(f"     parity={sc.components.parity} ({sc.components.parity_reason})")
            print(f"     fund_flow={sc.components.fund_flow} ({sc.components.fund_flow_reason})")
        except Exception as exc:
            print(f"   build_snapshot raised {type(exc).__name__}: {str(exc)[:300]}")


asyncio.run(main())
