from __future__ import annotations


def test_recommendation_valid_action():
    from domain.recommendations.rules import ActionRule

    rule = ActionRule()
    assert rule.validate(action="buy") is True
    assert rule.validate(action="sell") is True
    assert rule.validate(action="hold") is True
    assert rule.validate(action="invalid") is False


def test_recommendation_confidence_range():
    from domain.recommendations.rules import ConfidenceRule

    rule = ConfidenceRule()
    assert rule.validate(confidence=0.75) is True
    assert rule.validate(confidence=1.5) is False
    assert rule.validate(confidence=-0.1) is False


def test_recommendation_risk_level():
    from domain.recommendations.rules import RiskLevelRule

    rule = RiskLevelRule()
    assert rule.validate(risk_level="low") is True
    assert rule.validate(risk_level="moderate") is True
    assert rule.validate(risk_level="high") is True
    assert rule.validate(risk_level="extreme") is False


def test_recommendation_horizon():
    from domain.recommendations.rules import HorizonRule

    rule = HorizonRule()
    assert rule.validate(horizon="short_term") is True
    assert rule.validate(horizon="medium_term") is True
    assert rule.validate(horizon="long_term") is True
    assert rule.validate(horizon="unknown") is False


def test_recommendation_target_price():
    from domain.recommendations.rules import TargetPriceRule

    rule = TargetPriceRule()
    assert rule.validate(target_price=18000, current_price=15000) is True
    assert rule.validate(target_price=0, current_price=15000) is False
