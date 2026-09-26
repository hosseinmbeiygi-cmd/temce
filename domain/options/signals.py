"""Signal scoring, position sizing and a composable rule DSL.

Spec reference: ``تکمیل-بخش-موتور-استراتژی.md`` §7.3-7.5.

- ``SignalGenerator`` — composite score routing to SELL_PREMIUM /
  BUY_DIRECTIONAL / NEUTRAL_WAIT.  ML output is one weighted feature,
  never the decision itself (regulatory decision-support constraint).
- ``PositionSizer`` — fixed-fractional or capped-Kelly sizing.  Naked
  shorts must size from a stress-test max loss, not strike distance.
- ``RuleEngine`` — recursive ``all_of`` / ``any_of`` evaluation with
  ``scale_out`` exit ladders, matching the doc's JSON schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Signal generator (§7.3) ──────────────────────────────────────────────


@dataclass
class SignalWeights:
    iv_rank: float = 0.30
    skew: float = 0.20
    trend: float = 0.25
    term_structure: float = 0.15
    dte: float = 0.10


DEFAULT_WEIGHTS = {
    "iv_rank": 0.30,
    "skew": 0.20,
    "trend": 0.25,
    "term_structure": 0.15,
    "ml": 0.10,  # extra feature; renormalized against the doc weights
}


class SignalGenerator:
    """Composite signal score (doc §7.3).

    ``market_state`` keys: ``iv_rank`` (0-100), ``skew``, ``trend_strength``
    (-1..1), ``term_structure_slope``, ``days_to_expiry`` and optionally
    ``ml_probability`` (0-1) coming from the forecasting engine.
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or dict(DEFAULT_WEIGHTS)

    def score(self, market_state: dict[str, Any]) -> dict[str, Any]:
        iv_rank = float(market_state.get("iv_rank", 50.0))
        skew = float(market_state.get("skew", 0.0))
        trend = float(market_state.get("trend_strength", 0.0))
        term_slope = float(market_state.get("term_structure_slope", 0.0))
        dte = int(market_state.get("days_to_expiry", 30))

        score = 0.0
        score += self.weights.get("iv_rank", 0.0) * (iv_rank / 100.0)
        score += self.weights.get("skew", 0.0) * _tanh(skew)
        score += self.weights.get("trend", 0.0) * trend
        score += self.weights.get("term_structure", 0.0) * _tanh(term_slope)

        ml_probability = market_state.get("ml_probability")
        if ml_probability is not None and "ml" in self.weights:
            score += self.weights["ml"] * (float(ml_probability) - 0.5)

        # Time factor: sweet spot 15-45 DTE (doc uses 20-45 for entries).
        dte_factor = 1.0 if 15 <= dte <= 45 else 0.5
        score *= dte_factor
        score = max(0.0, min(score, 1.0))

        if iv_rank > 70:
            suggestion = "SELL_PREMIUM"  # e.g. Iron Condor / Short Strangle
        elif iv_rank < 30 and abs(trend) > 0.5:
            suggestion = "BUY_DIRECTIONAL"  # e.g. Long Call/Put or Debit Spread
        else:
            suggestion = "NEUTRAL_WAIT"

        return {
            "score": round(score, 3),
            "suggestion": suggestion,
            "dte_factor": dte_factor,
            "disclaimer": "پیشنهاد تحلیلی است؛ تصمیم و اجرا با کاربر است",
        }


def _tanh(x: float) -> float:
    import math

    return math.tanh(x)


# ── Position sizing (§7.4) ────────────────────────────────────────────────


class SizingMethod:
    FIXED_FRACTIONAL = "fractional_fixed"
    KELLY = "kelly"


class PositionSizer:
    """Fixed-fractional and capped-Kelly sizing (doc §7.4).

    For naked shorts, pass ``max_loss_per_contract`` derived from a
    ±20 % stress test — not strike distance — per the doc's Iran note.
    """

    def __init__(
        self,
        method: str = SizingMethod.FIXED_FRACTIONAL,
        risk_per_trade_pct: float = 1.0,
        kelly_cap_pct: float = 25.0,
    ):
        self.method = method
        self.risk_per_trade_pct = risk_per_trade_pct
        self.kelly_cap_pct = kelly_cap_pct

    def size(
        self,
        capital: float,
        max_loss_per_contract: float,
        win_rate: float | None = None,
        win_loss_ratio: float | None = None,
    ) -> dict[str, Any]:
        if max_loss_per_contract <= 0:
            return {"contracts": 0, "risk_budget": 0.0, "method": self.method, "kelly_fraction": None}

        if self.method == SizingMethod.FIXED_FRACTIONAL:
            risk_budget = capital * (self.risk_per_trade_pct / 100.0)
            contracts = max(int(risk_budget / max_loss_per_contract), 0)
            return {
                "contracts": contracts,
                "risk_budget": risk_budget,
                "method": self.method,
                "kelly_fraction": None,
            }

        if self.method == SizingMethod.KELLY:
            if win_rate is None or win_loss_ratio is None:
                raise ValueError("Kelly نیازمند win_rate و win_loss_ratio است")
            if win_loss_ratio <= 0:
                raise ValueError("win_loss_ratio باید مثبت باشد")
            kelly_fraction = win_rate - (1 - win_rate) / win_loss_ratio
            kelly_fraction = max(min(kelly_fraction, self.kelly_cap_pct / 100.0), 0.0)
            risk_budget = capital * kelly_fraction
            contracts = max(int(risk_budget / max_loss_per_contract), 0)
            return {
                "contracts": contracts,
                "risk_budget": risk_budget,
                "method": self.method,
                "kelly_fraction": round(kelly_fraction, 4),
            }

        raise ValueError(f"روش نامعتبر: {self.method}")


# ── Rule engine DSL (§7.5) ────────────────────────────────────────────────


class RuleEngine:
    """Recursive all_of/any_of rule evaluation with scale-out exits.

    Schema (doc §7.5)::

        {
          "entry": {
            "all_of": [
              {"iv_rank": {"gt": 70}},
              {"days_to_expiry": {"between": [20, 45]}},
            ]
          },
          "exit": {
            "any_of": [
              {"profit_target_pct": 50},
              {"stop_loss_pct": 100},
            ],
            "scale_out": [
              {"at_profit_pct": 30, "close_fraction": 0.5},
              {"at_profit_pct": 50, "close_fraction": 1.0},
            ]
          }
        }
    """

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec or {}

    # -- entry ------------------------------------------------------------

    def should_enter(self, facts: dict[str, Any]) -> bool:
        entry = self.spec.get("entry")
        if not entry:
            return True
        return self._eval_group(entry, facts)

    # -- exit --------------------------------------------------------------

    def exit_actions(self, facts: dict[str, Any]) -> dict[str, Any]:
        exit_spec = self.spec.get("exit") or {}
        triggered = self._eval_group(exit_spec, facts) if exit_spec else False

        actions: dict[str, Any] = {
            "exit_triggered": triggered,
            "close_fraction": 1.0 if triggered else 0.0,
            "scale_out": None,
            "reasons": self._matched_reasons(exit_spec, facts) if triggered else [],
        }

        scale_out = self._scale_out(exit_spec.get("scale_out"), facts.get("profit_pct", 0.0))
        if scale_out is not None:
            actions["scale_out"] = scale_out
            actions["close_fraction"] = max(actions["close_fraction"], scale_out["close_fraction"])
        return actions

    def _scale_out(self, ladder: list[dict[str, Any]] | None, profit_pct: float) -> dict[str, Any] | None:
        if not ladder:
            return None
        hit = None
        for rung in sorted(ladder, key=lambda r: r.get("at_profit_pct", 0)):
            if profit_pct >= rung.get("at_profit_pct", 0):
                hit = rung
        if hit is None:
            return None
        return {
            "at_profit_pct": hit.get("at_profit_pct"),
            "close_fraction": hit.get("close_fraction", 1.0),
        }

    # -- condition evaluation ------------------------------------------------

    _OPERATORS = {
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "between": lambda a, b: b[0] <= a <= b[1],
        "in": lambda a, b: a in b,
    }

    def _eval_group(self, group: dict[str, Any], facts: dict[str, Any]) -> bool:
        if "all_of" in group:
            return all(self._eval_group(item, facts) for item in group["all_of"])
        if "any_of" in group:
            return any(self._eval_group(item, facts) for item in group["any_of"])
        if "none_of" in group:
            return not any(self._eval_group(item, facts) for item in group["none_of"])
        return self._eval_condition(group, facts)

    def _eval_condition(self, condition: dict[str, Any], facts: dict[str, Any]) -> bool:
        for key, spec in condition.items():
            value = self._fact(facts, key)
            if value is None:
                return False
            if isinstance(spec, dict):
                for op, operand in spec.items():
                    fn = self._OPERATORS.get(op)
                    if fn is None:
                        raise ValueError(f"عملگر نامعتبر: {op}")
                    if not fn(value, operand):
                        return False
            elif isinstance(spec, bool):
                if bool(value) is not spec:
                    return False
            else:
                if value != spec:
                    return False
        return True

    def _fact(self, facts: dict[str, Any], key: str) -> Any:
        if key in facts:
            return facts[key]
        # Support dotted paths for nested facts.
        node: Any = facts
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    def _matched_reasons(self, group: dict[str, Any], facts: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        for branch in ("any_of", "all_of"):
            for item in group.get(branch, []) or []:
                try:
                    if self._eval_group(item, facts):
                        reasons.append(", ".join(item.keys()))
                except Exception:
                    continue
        for key in ("profit_target_pct", "stop_loss_pct"):
            if key in group and self._eval_condition({key: group[key]}, facts):
                reasons.append(key)
        return reasons
