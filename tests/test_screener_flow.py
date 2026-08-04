"""Test screener data flow end-to-end."""
import asyncio
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv()

from brsapi.services.query_service import BrsApiQueryService
from core.database import get_session


async def test():
    async for session in get_session():
        svc = BrsApiQueryService(session=session)

        # Test enriched snapshots (used by screener endpoint)
        print("=== get_enriched_snapshots(20) ===")
        try:
            snaps = await svc.get_enriched_snapshots(limit=20)
            print(f"  Got {len(snaps)} snapshots")
            if snaps:
                s = snaps[0]
                print(
                    f"  Sample: symbol={s.get('symbol')}, name={s.get('name')}, "
                    f"sector={s.get('sector')}, market={s.get('market')}, "
                    f"volume={s.get('trade_volume')}, value={s.get('trade_value')}"
                )
                print(f"  Keys: {list(s.keys())[:20]}...")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Test fallback snapshots
        print("\n=== get_latest_snapshots(20) ===")
        try:
            snaps2 = await svc.get_latest_snapshots(limit=20)
            print(f"  Got {len(snaps2)} snapshots")
            if snaps2:
                s2 = snaps2[0]
                print(
                    f"  Sample: symbol={s2.get('symbol')}, name={s2.get('name')}, "
                    f"sector={s2.get('sector')}, market={s2.get('market')}"
                )
                print(f"  Keys: {list(s2.keys())[:20]}...")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Test ScreenerService
        print("\n=== ScreenerService.screen() ===")
        from services.screener_service import ScreenerService

        svc2 = ScreenerService(session=session, history_limit=60)

        # Simulate what the endpoint does using the shared helper so the
        # conversion logic is not duplicated between tests and production code.
        from services.market_watch_helper import fetch_market_watch
        instruments, watch = await fetch_market_watch(svc, limit=20)

        try:
            results, pag = await svc2.screen(
                instruments=instruments,
                market_watch=watch,
                limit=20,
            )
            total_count = pag.get('total', 0) if pag else 0
            print(f"  Screened {len(results)} symbols, total = {total_count}")
            for r in results[:5]:
                print(
                    f"  {r.symbol}: smc={r.smc_score:.4f}, phase={r.phase}, "
                    f"reason={r.reason}, hist_len in details?"
                )
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()

        break


asyncio.run(test())
