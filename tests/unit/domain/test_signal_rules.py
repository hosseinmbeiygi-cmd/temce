from __future__ import annotations

from datetime import UTC


def test_signal_type_valid():
    from domain.signals.rules import SignalTypeRule

    rule = SignalTypeRule()
    assert rule.validate(signal_type="bullish") is True
    assert rule.validate(signal_type="bearish") is True
    assert rule.validate(signal_type="neutral") is True
    assert rule.validate(signal_type="invalid") is False


def test_signal_strength_range():
    from domain.signals.rules import StrengthRule

    rule = StrengthRule()
    assert rule.validate(strength=0.75) is True
    assert rule.validate(strength=1.5) is False
    assert rule.validate(strength=-0.1) is False


def test_signal_direction():
    from domain.signals.rules import DirectionRule

    rule = DirectionRule()
    assert rule.validate(direction="up") is True
    assert rule.validate(direction="down") is True
    assert rule.validate(direction="sideways") is True
    assert rule.validate(direction="invalid") is False


def test_signal_source_required():
    from domain.signals.rules import SourceRequiredRule

    rule = SourceRequiredRule()
    assert rule.validate(source="technical_analysis") is True
    assert rule.validate(source="") is False


def test_signal_expiry():
    from domain.signals.rules import ExpiryRule

    rule = ExpiryRule(max_validity_hours=48)
    from datetime import datetime, timedelta

    valid = datetime.now(UTC) + timedelta(hours=24)
    expired = datetime.now(UTC) - timedelta(hours=72)
    assert rule.validate(expires_at=valid.isoformat()) is True
    assert rule.validate(expires_at=expired.isoformat()) is False

