import asyncio
import sys

sys.path.insert(0, ".")

async def debug():
    from services.quant_signal_orchestrator import QuantSignalOrchestrator

    orchestrator = QuantSignalOrchestrator()

    # Step 1: Generate raw signals
    from services.multi_market_signal_engine import MultiMarketSignalEngine
    engine = MultiMarketSignalEngine()
    raw_signals, reports = await engine.generate_all(market_filter="all", limit=5)

    print(f"Raw signals: {len(raw_signals)}")
    for r in reports:
        print(f"  {r.market}: {r.signal_count} signals")

    if not raw_signals:
        print("No signals generated!")
        return

    # Show first raw signal details
    sig = raw_signals[0]
    print(f"\nFirst signal: {sig.symbol} ({sig.market})")
    print(f"  direction={sig.direction} price={sig.price}")
    print(f"  risk_reward='{sig.risk_reward}' stop_loss='{sig.stop_loss}' targets='{sig.targets}'")
    print(f"  score={sig.score} strength={sig.strength}")

    # Step 2: Build an EnrichedSignal manually
    from services.quant_signal_orchestrator import EnrichedSignal
    EnrichedSignal(
        symbol=sig.symbol, name=sig.name, market=sig.market,
        direction=sig.direction, timeframe=sig.timeframe,
        entry_zone=sig.entry_zone, stop_loss=sig.stop_loss,
        targets=sig.targets, risk_reward=sig.risk_reward,
        position_sizing=sig.position_sizing,
        confirmation_condition=sig.confirmation_condition,
        reason=sig.reason, invalidation=sig.invalidation,
        trailing_stop=sig.trailing_stop, price=sig.price,
        change_pct=sig.change_pct, rule_score=sig.score,
        ml_score=0.0, boosted_score=sig.score,
        ml_influence_pct=0.0, confidence=0.5,
        calibration_level="medium",
        vote_direction_scores={"buy": 0.5, "sell": 0.3, "hold": 0.2},
        source="debug",
    )

    # Step 3: Parse values
    rr = orchestrator._parse_risk_reward(sig.risk_reward)
    sl = orchestrator._parse_stop_loss_pct(sig.stop_loss, sig.price)
    tp = orchestrator._parse_target_pct(sig.targets, sig.price)
    print(f"\nParsed: risk_reward={rr} stop_loss_pct={sl} target_pct={tp}")

    # Step 4: Run through decision engine
    from services.signal_decision_engine import SignalCandidate, SignalDecisionEngine, SignalPolicy
    policy = SignalPolicy(json_path="config/signal_policy.yaml")
    decision_engine = SignalDecisionEngine(policy=policy)

    candidate = SignalCandidate(
        signal_id=sig.symbol + "_" + sig.market + "_" + sig.timeframe,
        symbol=sig.symbol, name=sig.name, market=sig.market,
        direction=sig.direction, timeframe=sig.timeframe,
        raw_score=sig.score / 100.0, ml_score=0.0,
        calibrated_probability=0.5, boosted_score=sig.score,
        active_models=0, agreeing_models=0,
        risk_reward=rr, stop_loss_pct=sl, target_pct=tp,
        price=sig.price, signal_type="rule",
        best_class_probability=0.5, second_class_probability=0.3,
        source="debug",
        data_quality_score=1.0, volatility_regime=0.5,
        liquidity_score=0.7, fill_probability=0.7,
        feature_drift=0.0, portfolio_risk_approved=True,
        open_risk_pct=0.0, correlated_exposure_pct=0.0,
    )

    decision = await decision_engine.evaluate(candidate)
    grade = decision_engine.signal_grade(decision)

    print(f"\nDecision: {decision.verdict.value} (grade={grade})")
    print(f"  calibrated_probability={decision.calibrated_probability}")
    print(f"  effective_threshold={decision.effective_threshold}")
    print(f"  net_expectancy_r={decision.net_expectancy_r}")

    for g in decision.gate_results:
        print(f"  Gate '{g.gate_name}': {g.verdict.value} score={g.score:.3f} | {g.reason}")

asyncio.run(debug())
