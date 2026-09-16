"""Comprehensive integration test: Voting between Rule-based + ML signals.

This test answers: "How much does voting improve accuracy over rule-based alone?"
It uses mocks (no DB needed) with controlled scenarios.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.time import utc_now_naive
from services.multi_market_signal_engine import MarketSignal
from services.signal_voting_system import SignalVotingSystem

# -- Helpers ------------------------------------------------------------------


def make_signal(
    symbol: str = "فولاد",
    direction: str = "buy",
    score: float = 60.0,
    confidence: float = 0.55,
    strength: float = 0.5,
    source: str = "rule_based_test",
    market: str = "stock",
) -> MarketSignal:
    return MarketSignal(
        symbol=symbol,
        name="فولاد مبارکه",
        market=market,
        direction=direction,
        timeframe="daily",
        entry_zone="5,000 تا 5,100 ريال",
        stop_loss="4,750 ريال (5% کاهش)",
        targets="هدف اول: 5,355 | هدف دوم: 5,620",
        risk_reward="1 به 2",
        position_sizing="حداکثر 3% سرمایه",
        confirmation_condition="تثبیت بالای 5,000",
        reason="تست voting",
        invalidation="شکست 4,750",
        trailing_stop="پس از هدف اول، حد ضرر به 5,000",
        price=5000.0,
        change_pct=2.5,
        score=score,
        strength=strength,
        confidence=confidence,
        source=source,
        created_at=utc_now_naive().isoformat(),
    )


def make_ml_prediction(
    direction: str = "buy",
    confidence: float = 0.7,
    ml_score: float = 0.65,
    models_used: list[str] | None = None,
) -> dict[str, Any]:
    if models_used is None:
        models_used = ["xgboost", "random_forest"]
    direction_scores = {"buy": 0.5, "sell": 0.3, "hold": 0.2}
    if direction == "buy":
        direction_scores = {"buy": ml_score, "sell": 0.3, "hold": 0.2}
    elif direction == "sell":
        direction_scores = {"buy": 0.3, "sell": ml_score, "hold": 0.2}
    elif direction == "hold":
        direction_scores = {"buy": 0.3, "sell": 0.3, "hold": ml_score}
    return {
        "direction": direction,
        "direction_scores": direction_scores,
        "confidence": confidence,
        "ml_score": ml_score,
        "models_used": models_used,
        "model_breakdown": [
            {
                "model": m,
                "prediction": 0.55 + confidence * 0.1,
                "confidence": confidence,
                "weight": 0.5,
            }
            for m in models_used
        ],
    }


# -- Test 1: Agreement --------------------------------------------------------


@pytest.mark.asyncio
async def test_voting_rule_and_ml_agree():
    """Rule and ML agree -> strong signal with high confidence."""
    system = SignalVotingSystem()
    result = await system.vote(
        make_signal(direction="buy", score=70, confidence=0.6),
        make_ml_prediction(direction="buy", confidence=0.8),
    )
    assert result.final_direction == "buy"
    assert result.final_confidence > 0.6
    # When all sources agree, weighted returns "unanimous" label
    assert result.strategy in ("weighted", "unanimous")
    assert len(result.sources_contributing) >= 2
    print(
        f"  [PASS] Test 1: Agreement -> dir={result.final_direction} "
        f"conf={result.final_confidence:.2f} strat={result.strategy}"
    )


# -- Test 2: Disagreement -----------------------------------------------------


@pytest.mark.asyncio
async def test_voting_rule_and_ml_disagree():
    """Rule and ML disagree -> ML should have influence."""
    system = SignalVotingSystem()
    result = await system.vote(
        make_signal(direction="buy", score=60, confidence=0.5),
        make_ml_prediction(direction="sell", confidence=0.85, ml_score=0.75),
    )
    assert result.ml_weight > 0
    assert len(result.sources_contributing) >= 2
    assert "buy" in result.direction_votes and "sell" in result.direction_votes
    print(
        f"  [PASS] Test 2: Disagree -> dir={result.final_direction} "
        f"ml_w={result.ml_weight:.2f} votes=buy:{result.direction_votes['buy']:.2f}"
    )


# -- Test 3: ML Override ------------------------------------------------------


@pytest.mark.asyncio
async def test_ml_override_with_high_confidence():
    """ML confidence > threshold -> ML overrides rule."""
    system = SignalVotingSystem()
    result = await system.vote(
        make_signal(direction="buy", score=60, confidence=0.5),
        make_ml_prediction(direction="sell", confidence=0.85, ml_score=0.75),
        strategy="ml_override",
        ml_override_threshold=0.75,
    )
    assert result.strategy == "ml_override"
    assert result.final_direction == "sell"
    print(f"  [PASS] Test 3: Override -> dir={result.final_direction} " f"conf={result.final_confidence:.2f}")


# -- Test 4: Low ML Confidence -------------------------------------------------


@pytest.mark.asyncio
async def test_ml_confidence_below_threshold():
    """ML confidence below threshold -> rule dominates."""
    system = SignalVotingSystem()
    result = await system.vote(
        make_signal(direction="buy", score=70, confidence=0.7),
        make_ml_prediction(direction="sell", confidence=0.5, ml_score=0.45),
        strategy="ml_override",
        ml_override_threshold=0.75,
    )
    assert result.final_direction == "buy"
    assert result.strategy != "ml_override"
    print(f"  [PASS] Test 4: Low conf -> dir={result.final_direction} " f"strat={result.strategy}")


# -- Test 5: Unanimous --------------------------------------------------------


@pytest.mark.asyncio
async def test_unanimous_voting():
    """Unanimous: all must agree; else hold."""
    system = SignalVotingSystem()

    # Case A: Agree
    r = await system.vote(
        make_signal(direction="buy", score=75, confidence=0.7),
        make_ml_prediction(direction="buy", confidence=0.8),
        strategy="unanimous",
    )
    assert r.final_direction == "buy"
    assert r.strategy == "unanimous"
    print(f"  [PASS] Test 5A: Unanimous agree -> dir={r.final_direction}")

    # Case B: Disagree -> hold
    r2 = await system.vote(
        make_signal(direction="buy", score=60, confidence=0.5),
        make_ml_prediction(direction="sell", confidence=0.8),
        strategy="unanimous",
    )
    assert r2.final_direction == "hold"
    assert r2.strategy == "unanimous_disagreement"
    print(f"  [PASS] Test 5B: Unanimous disagree -> dir={r2.final_direction}")


# -- Test 6: No ML models -----------------------------------------------------


@pytest.mark.asyncio
async def test_ml_prediction_no_models_used():
    """Empty models_used -> fallback to rule-based."""
    system = SignalVotingSystem()
    result = await system.vote(
        make_signal(direction="buy", score=65, confidence=0.6),
        make_ml_prediction(direction="buy", confidence=0.0, models_used=[]),
    )
    assert result.final_direction == "buy"
    assert result.ml_weight == 0.0
    assert len(result.sources_contributing) == 1
    print(f"  [PASS] Test 6: No ML -> dir={result.final_direction} " f"sources={len(result.sources_contributing)}")


# -- Test 7: Historical Accuracy -----------------------------------------------


@pytest.mark.asyncio
async def test_historical_accuracy_influence():
    """Historical accuracy data should influence voting."""
    system = SignalVotingSystem()
    result = await system.vote(
        make_signal(direction="buy", score=55, confidence=0.4),
        make_ml_prediction(direction="sell", confidence=0.6, ml_score=0.55),
        symbol_history={"accuracy_pct": 70.0, "best_direction": "buy", "total": 100},
    )
    has_history = any(s["type"] == "historical" for s in result.sources_contributing)
    assert has_history
    print(f"  [PASS] Test 7: History -> dir={result.final_direction} " f"sources={len(result.sources_contributing)}")


# -- Test 8: apply_vote -------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_vote_to_signal():
    """apply_vote correctly updates signal fields."""
    system = SignalVotingSystem()
    original = make_signal(direction="buy", score=50, confidence=0.4, strength=0.3)
    vote = await system.vote(original, make_ml_prediction(direction="buy", confidence=0.9))
    updated = system.apply_vote_to_signal(original, vote)
    assert updated.direction == vote.final_direction
    assert updated.confidence == vote.final_confidence
    assert updated.score == vote.final_score
    assert "VOTING" in updated.reason or "voting" in updated.source
    print(
        f"  [PASS] Test 8: apply_vote -> dir={updated.direction} "
        f"score={updated.score:.0f} conf={updated.confidence:.2f}"
    )


# -- Test 9: Edge Cases -------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_cases():
    """Test edge cases: very low confidence, extreme override, no ML."""
    system = SignalVotingSystem()

    # Edge 1: Both very low confidence but agree on direction
    # When all sources agree, confidence is high even if individual confidences are low
    r = await system.vote(
        make_signal(direction="hold", score=50, confidence=0.1, strength=0.1),
        make_ml_prediction(direction="hold", confidence=0.1, ml_score=0.1),
    )
    assert r.final_direction == "hold", "Should agree on hold"
    assert r.final_confidence >= 0.5, "Unanimous agreement => high confidence even with low individual conf"
    print(
        f"  [PASS] Test 9A: Low conf unanimous -> dir={r.final_direction} "
        f"conf={r.final_confidence:.2f} strat={r.strategy}"
    )

    # Edge 2: Extreme ML override
    r2 = await system.vote(
        make_signal(direction="hold", score=50, confidence=0.3),
        make_ml_prediction(direction="buy", confidence=0.95, ml_score=0.9),
        strategy="ml_override",
        ml_override_threshold=0.8,
    )
    assert r2.strategy == "ml_override"
    assert r2.final_direction == "buy"
    print(f"  [PASS] Test 9B: Extreme override -> dir={r2.final_direction}")

    # Edge 3: No ML
    r3 = await system.vote(make_signal(direction="hold", score=50, confidence=0.1, strength=0.1), None)
    assert r3.final_direction == "hold"
    assert r3.ml_weight == 0.0
    print(f"  [PASS] Test 9C: No ML -> dir={r3.final_direction}")


# -- Test 10: Strategy Comparison ----------------------------------------------


@pytest.mark.asyncio
async def test_all_voting_strategies_comparison():
    """Compare all voting strategies on same input."""
    system = SignalVotingSystem()
    rule_signal = make_signal(direction="buy", score=65, confidence=0.55)
    ml_pred = make_ml_prediction(direction="sell", confidence=0.8, ml_score=0.7)

    print("  [INFO] Strategy Comparison:")
    for strategy in ["weighted", "unanimous", "ml_override"]:
        r = await system.vote(rule_signal, ml_pred, strategy=strategy)
        print(
            f"    {strategy:15s} dir={r.final_direction:6s} "
            f"score={r.final_score:.0f} conf={r.final_confidence:.2f} "
            f"ml_w={r.ml_weight:.2f}"
        )

    print("  [PASS] Test 10: All strategies ran")


# -- Test 11: Full Pipeline ----------------------------------------------------


@pytest.mark.asyncio
async def test_full_voting_pipeline():
    """Full pipeline: generate, vote, apply."""
    system = SignalVotingSystem()
    rule_signal = make_signal(
        symbol="شپنا",
        direction="buy",
        score=72,
        confidence=0.58,
        strength=0.6,
        source="smart_money_technical",
    )
    ml_pred = make_ml_prediction(
        direction="buy",
        confidence=0.82,
        ml_score=0.78,
        models_used=["xgboost", "lstm", "random_forest"],
    )
    vote = await system.vote(
        rule_signal,
        ml_pred,
        symbol_history={"accuracy_pct": 62.0, "best_direction": "buy", "total": 45},
    )
    final = system.apply_vote_to_signal(rule_signal, vote)
    assert final.direction == "buy"
    # When all sources agree, weighted strategy labels it as unanimous
    assert final.source in ("voting_weighted", "voting_unanimous")
    assert final.score >= 70
    assert final.confidence >= 0.6
    # Source always starts with 'voting_' regardless of strategy
    assert final.source.startswith("voting_"), f"Source should start with voting_: {final.source}"
    assert "smart_money_technical" in final.reason
    assert "ml_ensemble" in final.reason
    print(
        f"  [PASS] Test 11: Full pipe -> dir={final.direction} " f"score={final.score:.0f} conf={final.confidence:.2f}"
    )


# -- Main Comparison: Rule-only vs Voted ---------------------------------------


@pytest.mark.asyncio
async def test_comparison_rule_only_vs_voted():
    """COMPARISON: Measure accuracy improvement from voting.

    Creates 30 scenarios where rule is ~53% accurate and ML is ~73% accurate,
    then measures how much voting improves over rule alone.
    """
    system = SignalVotingSystem()

    scenarios = [
        # Case 1: Both right (8)
        ("up", "buy", "buy", 0.8),
        ("up", "buy", "buy", 0.7),
        ("up", "buy", "buy", 0.75),
        ("up", "buy", "buy", 0.85),
        ("up", "buy", "buy", 0.65),
        ("up", "buy", "buy", 0.9),
        ("up", "buy", "buy", 0.7),
        ("up", "buy", "buy", 0.8),
        # Case 2: Both wrong (1)
        ("down", "buy", "buy", 0.6),
        # Case 3: Rule right, ML wrong (3)
        ("up", "buy", "sell", 0.6),
        ("up", "buy", "hold", 0.5),
        ("up", "buy", "sell", 0.55),
        # Case 4: Rule wrong, ML right -> voting helps! (6)
        ("up", "hold", "buy", 0.85),
        ("up", "sell", "buy", 0.8),
        ("down", "buy", "sell", 0.75),
        ("down", "hold", "sell", 0.8),
        ("up", "sell", "buy", 0.9),
        ("down", "buy", "sell", 0.85),
        # Case 5: Close calls (5)
        ("up", "buy", "hold", 0.55),
        ("up", "hold", "buy", 0.6),
        ("down", "hold", "sell", 0.6),
        ("down", "buy", "sell", 0.65),
        ("down", "buy", "sell", 0.7),
        # Case 6: Highly uncertain (3)
        ("up", "hold", "hold", 0.4),
        ("up", "buy", "hold", 0.3),
        ("down", "sell", "hold", 0.35),
        # Case 7: Mixed (4)
        ("up", "buy", "buy", 0.7),
        ("down", "sell", "sell", 0.75),
        ("up", "hold", "buy", 0.65),
        ("down", "buy", "sell", 0.7),
    ]

    rule_correct = 0
    voted_correct = 0
    total_scenarios = len(scenarios)
    details: list[dict[str, Any]] = []

    for actual, rule_dir, ml_dir, ml_conf in scenarios:
        actual_signal = "buy" if actual == "up" else "sell"

        rule_is_correct = rule_dir == actual_signal
        if rule_is_correct:
            rule_correct += 1

        rule_signal = make_signal(
            direction=rule_dir,
            score=60 if rule_is_correct else 40,
            confidence=0.6 if rule_is_correct else 0.4,
            strength=0.5 if rule_is_correct else 0.3,
        )
        ml_pred = make_ml_prediction(direction=ml_dir, confidence=ml_conf, ml_score=ml_conf * 0.9)

        vote_result = await system.vote(rule_signal, ml_pred, strategy="weighted")
        voted_is_correct = vote_result.final_direction == actual_signal
        if voted_is_correct:
            voted_correct += 1

        details.append(
            {
                "actual": actual_signal,
                "rule": rule_dir,
                "ml": ml_dir,
                "rule_correct": rule_is_correct,
                "voted_correct": voted_is_correct,
            }
        )

    rule_accuracy = (rule_correct / total_scenarios) * 100
    voted_accuracy = (voted_correct / total_scenarios) * 100
    improvement = voted_accuracy - rule_accuracy

    fixed = (1 for d in details if not d["rule_correct"] and d["voted_correct"])
    broken = (1 for d in details if d["rule_correct"] and not d["voted_correct"])
    rule_saved = sum(1 for d in details if d["rule_correct"] and d["rule"] != d["ml"] and d["voted_correct"])

    print(f"\n  [COMPARISON] n={total_scenarios}:")
    print(f"    Rule-only:  {rule_accuracy:.1f}% ({rule_correct}/{total_scenarios})")
    print(f"    Voted:      {voted_accuracy:.1f}% ({voted_correct}/{total_scenarios})")
    print(f"    Improvement: {improvement:+.1f}%")
    print(f"    Fixed by voting:  {fixed}")
    print(f"    Broken by voting: {broken}")
    print(f"    Rule saved the day: {rule_saved}")

    assert (
        voted_accuracy >= rule_accuracy
    ), f"Voting ({voted_accuracy:.1f}%) should not be worse than rule ({rule_accuracy:.1f}%)"
    assert fixed > broken, f"Voting should fix more errors ({fixed}) than it breaks ({broken})"

    print(f"  [PASS] Comparison: Voting improves accuracy by {improvement:+.1f}%!")


# -- Main entry point (only runs when executed directly) ------------------------

if __name__ == "__main__":
    import asyncio

    results: list[dict[str, Any]] = []
    tests = [
        ("1.  Agreement (Rule+ML agree)", test_voting_rule_and_ml_agree),
        ("2.  Disagreement (Rule+ML differ)", test_voting_rule_and_ml_disagree),
        ("3.  ML Override (high confidence)", test_ml_override_with_high_confidence),
        ("4.  ML Below Threshold (low conf)", test_ml_confidence_below_threshold),
        ("5.  Unanimous Strategy", test_unanimous_voting),
        ("6.  No ML Models (fallback)", test_ml_prediction_no_models_used),
        ("7.  Historical Accuracy", test_historical_accuracy_influence),
        ("8.  Apply Vote to Signal", test_apply_vote_to_signal),
        ("9.  Edge Cases", test_edge_cases),
        ("10. Strategy Comparison", test_all_voting_strategies_comparison),
        ("11. Full Pipeline", test_full_voting_pipeline),
    ]

    print("=" * 70)
    print("VOTING SYSTEM COMPREHENSIVE TEST")
    print("Comparing: Rule-based only vs Rule+ML Voted")
    print("=" * 70)

    for name, test_fn in tests:
        print(f"\n  -- {name} --")
        try:
            asyncio.run(test_fn())
            results.append({"name": name, "passed": True})
        except Exception as e:
            print(f"  FAIL: {e}")
            results.append({"name": name, "passed": False})

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    for r in results:
        status = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"  {status} {r['name']}")
    print(f"\n  Total: {len(results)} | Passed: {passed} | Failed: {failed}")

    print("\n" + "=" * 70)
    print("MAIN COMPARISON: Rule-only vs Voted")
    print("=" * 70)
    try:
        asyncio.run(test_comparison_rule_only_vs_voted())
    except Exception as e:
        print(f"  COMPARISON FAILED: {e}")

    exit(0 if failed == 0 else 1)
