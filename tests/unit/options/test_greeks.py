"""Tests for the Greeks data container.

Trivial dataclass but locked down: a field-removal or default change
would silently break consumers (greeks_from_tree, pricing.py).
"""

from __future__ import annotations

from dataclasses import fields

from domain.options.greeks import Greeks


def test_default_values_are_zero() -> None:
    g = Greeks()
    for f in fields(Greeks):
        assert getattr(g, f.name) == 0.0, f"{f.name} should default to 0.0"


def test_all_greek_fields_present() -> None:
    expected = {"delta", "gamma", "theta", "vega", "rho", "speed", "charm", "vanna", "vomma"}
    actual = {f.name for f in fields(Greeks)}
    assert actual == expected, f"Greek field set drifted: missing={expected - actual}, extra={actual - expected}"


def test_assignment_roundtrip() -> None:
    g = Greeks(delta=0.5, gamma=0.1, theta=-0.05, vega=0.2)
    assert g.delta == 0.5
    assert g.gamma == 0.1
    assert g.theta == -0.05
    assert g.vega == 0.2
    # Untouched fields remain 0
    assert g.rho == 0.0
    assert g.vomma == 0.0
