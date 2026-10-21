"""Unit tests — قوانین هشدار مبتنی بر معیارهای ریسک پرتفوی.

پوشش:
  * تمرکز، انحراف ری‌بالانس و افت سرمایه از ``portfolio_metrics`` خوانده می‌شوند
  * نبود معیار ⇒ هیچ هشدار کاذبی صادر نمی‌شود
  * جهت عملگر پیام برای قوانین پرتفوی درست است
  * قوانین پیش‌فرض شامل هر سه نوع پرتفوی است
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.gold_desk import alert_engine as ae
from src.gold_desk.models import AlertRuleModel


class _RulesResult:
    def __init__(self, rules) -> None:
        self._rules = rules

    def scalars(self):
        return self

    def all(self):
        return self._rules


class _Session:
    def __init__(self, rules) -> None:
        self._rules = rules
        self.added: list = []
        self.commits = 0

    async def execute(self, *args, **kwargs):
        return _RulesResult(self._rules)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _rule(rule_type: str, threshold: float, name: str = "rule") -> AlertRuleModel:
    return AlertRuleModel(
        name=name,
        rule_type=rule_type,
        symbol=None,
        threshold=threshold,
        channel="inapp",
        enabled=True,
        cooldown_minutes=60,
        last_fired_at=None,
    )


def _snap() -> SimpleNamespace:
    return SimpleNamespace(
        coins={},
        gold={},
        funds=[],
        score=SimpleNamespace(total=40),
        references=SimpleNamespace(aed_gap_pct=0.0),
    )


@pytest.mark.asyncio
async def test_concentration_rule_fires_above_threshold() -> None:
    session = _Session([_rule("portfolio_concentration_above", 60.0, "تمرکز")])
    events = await ae.evaluate_rules(
        session, _snap(), portfolio_metrics={"portfolio_concentration_pct": 75.4}
    )
    assert len(events) == 1
    assert events[0].trigger_value == pytest.approx(75.4)
    assert ">" in events[0].message
    assert session.commits == 1


@pytest.mark.asyncio
async def test_concentration_rule_silent_below_threshold() -> None:
    session = _Session([_rule("portfolio_concentration_above", 60.0)])
    events = await ae.evaluate_rules(
        session, _snap(), portfolio_metrics={"portfolio_concentration_pct": 45.0}
    )
    assert events == []
    assert session.commits == 0


@pytest.mark.asyncio
async def test_missing_metric_never_fires_false_alert() -> None:
    """معیار در دسترس نیست ⇒ ارزیابی نمی‌شود (نه اینکه صفر فرض شود)."""
    rules = [
        _rule("portfolio_concentration_above", 60.0),
        _rule("portfolio_drift_above", 10.0),
        _rule("portfolio_drawdown_above", 15.0),
    ]
    session = _Session(rules)
    assert await ae.evaluate_rules(session, _snap(), portfolio_metrics=None) == []
    assert await ae.evaluate_rules(session, _snap(), portfolio_metrics={}) == []
    assert session.commits == 0


@pytest.mark.asyncio
async def test_drift_and_drawdown_rules_fire() -> None:
    rules = [
        _rule("portfolio_drift_above", 10.0, "ری‌بالانس"),
        _rule("portfolio_drawdown_above", 15.0, "افت"),
    ]
    session = _Session(rules)
    events = await ae.evaluate_rules(
        session,
        _snap(),
        portfolio_metrics={"portfolio_drift_pct": 22.5, "portfolio_drawdown_pct": 18.0},
    )
    assert {e.rule_name for e in events} == {"ری‌بالانس", "افت"}


def test_portfolio_rule_types_are_declared() -> None:
    assert "portfolio_concentration_above" in ae.PORTFOLIO_RULE_TYPES
    for rule_type in ae.PORTFOLIO_RULE_TYPES:
        assert ae._operator_for(rule_type, 10.0) == ">"
        assert ae._PORTFOLIO_METRIC_KEYS[rule_type].startswith("portfolio_")


def test_default_rules_include_portfolio_risk_rules() -> None:
    types = {r["rule_type"] for r in ae.DEFAULT_RULES}
    assert {
        "portfolio_concentration_above",
        "portfolio_drift_above",
        "portfolio_drawdown_above",
    } <= types
    # همهٔ قوانین پیش‌فرض باید threshold مثبت داشته باشند
    assert all(r["threshold"] > 0 for r in ae.DEFAULT_RULES)
