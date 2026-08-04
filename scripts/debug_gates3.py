import asyncio
import sys

sys.path.insert(0, ".")

async def debug():
    from core.database import init_database
    await init_database()

    from sqlalchemy import text

    from core.database import async_session_factory

    async with async_session_factory() as session:
        # Get a few stocks
        r = await session.execute(text("""
            SELECT symbol, price_last, trade_volume
            FROM brsapi_symbol_snapshots
            WHERE symbol IS NOT NULL AND trade_volume > 0 AND price_last > 0
            ORDER BY trade_value DESC LIMIT 3
        """))
        stocks = r.fetchall()
        print(f"Found {len(stocks)} stocks")

        if not stocks:
            return

        for stock in stocks:
            sym = stock[0]
            price = stock[1]
            print(f"\n=== {sym} (price={price}) ===")

            # Fetch history
            r2 = await session.execute(text("""
                SELECT price_close, trade_volume FROM brsapi_historical_daily
                WHERE symbol = :sym AND price_close > 0
                ORDER BY date DESC LIMIT 50
            """), {"sym": sym})
            hist = r2.fetchall()
            print(f"  History rows: {len(hist)}")

            if len(hist) < 5:
                print("  SKIP: not enough history")
                continue

            closes = [h[0] for h in reversed(hist)]

            # Compute RSI
            from services.multi_market_signal_engine import _compute_rsi
            rsi = _compute_rsi(closes, 14)
            print(f"  RSI: {rsi}")

            # Build candidate
            rr = 1.5
            sl_pct = 0.05
            tp_pct = rr * sl_pct

            from services.signal_decision_engine import SignalCandidate, SignalDecisionEngine, SignalPolicy
            policy = SignalPolicy(json_path="config/signal_policy.yaml")
            engine2 = SignalDecisionEngine(policy=policy)

            candidate = SignalCandidate(
                signal_id=f"{sym}_stock_daily", symbol=sym, name=sym,
                market="stock", direction="buy", timeframe="daily",
                raw_score=0.65, ml_score=0.0,
                calibrated_probability=0.5, boosted_score=65.0,
                active_models=0, agreeing_models=0,
                risk_reward=rr, stop_loss_pct=sl_pct, target_pct=tp_pct,
                price=price, signal_type="rule",
                best_class_probability=0.5, second_class_probability=0.3,
                source="debug",
                data_quality_score=1.0, volatility_regime=0.5,
                liquidity_score=0.7, fill_probability=0.7,
                feature_drift=0.0, portfolio_risk_approved=True,
                open_risk_pct=0.0, correlated_exposure_pct=0.0,
            )

            decision = await engine2.evaluate(candidate)
            grade = engine2.signal_grade(decision)

            print(f"  Decision: {decision.verdict.value} (grade={grade})")
            print(f"  effective_threshold={decision.effective_threshold}")

            for g in decision.gate_results:
                marker = "BLOCKED" if g.verdict.value == "block" else ("WARN" if g.verdict.value == "warn" else "ok")
                print(f"    [{marker}] {g.gate_name}: {g.verdict.value} score={g.score:.3f}")
                if g.verdict.value != "pass":
                    print(f"      {g.reason}")

asyncio.run(debug())
