import asyncio
import sys

sys.path.insert(0, ".")

async def debug():
    from core.database import init_database
    await init_database()

    from services.multi_market_signal_engine import MultiMarketSignalEngine
    engine = MultiMarketSignalEngine()
    raw_signals, reports = await engine.generate_all(market_filter="stock", signal_filter="buy", limit=5)

    print(f"Stock buy signals: {len(raw_signals)}")
    for s in raw_signals[:5]:
        print(f"  {s.symbol}: dir={s.direction} score={s.score} rr='{s.risk_reward}' sl='{s.stop_loss}' targets='{s.targets}' price={s.price}")

    from services.quant_signal_orchestrator import QuantSignalOrchestrator
    orch = QuantSignalOrchestrator()
    rr = orch._parse_risk_reward(raw_signals[0].risk_reward)
    sl = orch._parse_stop_loss_pct(raw_signals[0].stop_loss, raw_signals[0].price)
    tp = orch._parse_target_pct(raw_signals[0].targets, raw_signals[0].price)
    print(f"\nParsed: risk_reward={rr} stop_loss_pct={sl} target_pct={tp}")

asyncio.run(debug())
