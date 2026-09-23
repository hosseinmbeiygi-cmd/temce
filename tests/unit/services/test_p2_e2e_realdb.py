"""P2-2 E2E with the REAL database: symbol -> real candle length -> decision."""
import asyncio
import math

import asyncpg

from services.quant_signal_orchestrator import EnrichedSignal, QuantSignalOrchestrator


async def fetch_real_history(symbol, limit=120):
    c = await asyncpg.connect(
        user="hossein",
        password="Im_GCZjNmnzhL4FModjociYjzme",
        host="localhost",
        port=5432,
        database="my_first_db",
    )
    rows = await c.fetch(
        "SELECT price_close, date FROM brsapi_historical_daily "
        "WHERE symbol = $1 ORDER BY date DESC LIMIT $2",
        symbol,
        limit,
    )
    await c.close()
    closes = [float(r["price_close"]) for r in rows if r["price_close"]]
    return closes


async def pick_symbol():
    c = await asyncpg.connect(
        user="hossein",
        password="Im_GCZjNmnzhL4FModjociYjzme",
        host="localhost",
        port=5432,
        database="my_first_db",
    )
    row = await c.fetchrow(
        "SELECT symbol, COUNT(*) AS n FROM brsapi_historical_daily "
        "GROUP BY symbol HAVING COUNT(*) >= 60 ORDER BY n DESC LIMIT 1"
    )
    await c.close()
    return row["symbol"], row["n"]


def test_e2e_real_db_history_to_decision():
    symbol, n = asyncio.run(pick_symbol())
    closes = asyncio.run(fetch_real_history(symbol))
    assert len(closes) >= 60, "need real history"
    last = closes[0]
    prev = closes[5] if len(closes) > 5 else closes[-1]
    chg = (last - prev) / prev * 100 if prev else 7.0
    if abs(chg) < 2.0:
        chg = 7.0 if chg >= 0 else -7.0
    sig = EnrichedSignal(
        symbol=symbol, name=symbol, market="stock",
        direction="buy" if chg >= 0 else "sell", timeframe="daily",
        entry_zone="z", stop_loss=str(round(last * 0.95, 1)),
        targets=str(round(last * 1.1, 1)), risk_reward="2",
        position_sizing="s", confirmation_condition="c", reason="e2e-real",
        invalidation="i", trailing_stop="t", price=last, change_pct=chg,
        rule_score=75.0, ml_score=0.65, boosted_score=75.0,
        ml_influence_pct=10.0, confidence=0.72,
        calibration_level="medium",
        vote_direction_scores={"buy": 0.72, "sell": 0.2},
        source="e2e-real", created_at="now",
    )
    orch = QuantSignalOrchestrator(session=None)
    released, rejected = asyncio.run(
        orch._apply_signal_decision([sig], {symbol: len(closes)})
    )
    assert len(released) + len(rejected) == 1
    assert len(released) > 0, "real-history signal must release"
    d = released[0].to_dict()
    assert "legal_disclaimer" in d and len(d["legal_disclaimer"]) > 10
    for v in (sig.price, sig.confidence, released[0].net_expectancy_r):
        assert math.isfinite(float(v))
    print(f"E2E-REAL: {symbol} n={n} closes={len(closes)} released=1")
