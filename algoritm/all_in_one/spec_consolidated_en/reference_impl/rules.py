"""Time-dependent rules registry. Every market constant must come from rule_at().

- Intervals are half-open [effective_from, effective_to); effective_to=None means open-ended.
- Overlap is checked per (rule_key, scope), not globally.
- Confidence defaults to 'D' (unverified). A result that used any 'C'/'D' rule must be flagged by the caller.
- No rule values are shipped with this code.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

CONFIDENCE = ("A", "B", "C", "D")


class RuleNotFound(KeyError):
    pass


class RuleOverlap(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    rule_key: str
    scope: str                      # e.g. "symbol:XYZ", "segment:ABC", "market:TSE", "global"
    value: Any
    effective_from: date
    effective_to: date | None = None
    source_ref: str | None = None
    confidence: str = "D"


@dataclass(frozen=True)
class RuleValue:
    value: Any
    confidence: str
    source_ref: str | None
    scope: str


class RuleRegistry:
    def __init__(self, rules: Iterable[Rule]):
        self._rules = list(rules)
        self._validate()

    def _validate(self) -> None:
        by = {}
        for r in self._rules:
            if r.confidence not in CONFIDENCE:
                raise ValueError(f"bad confidence {r.confidence!r}")
            if r.effective_to is not None and not (r.effective_from < r.effective_to):
                raise ValueError(f"empty/inverted interval for {r.rule_key}/{r.scope}")
            by.setdefault((r.rule_key, r.scope), []).append(r)
        for (k, s), rs in by.items():
            rs = sorted(rs, key=lambda x: x.effective_from)
            for a, b in zip(rs, rs[1:]):
                if a.effective_to is None or a.effective_to > b.effective_from:
                    raise RuleOverlap(f"overlap for {k}/{s}: {a.effective_from}..{a.effective_to} vs {b.effective_from}")

    def rule_at(self, key: str, scopes: Sequence[str], on: date) -> RuleValue:
        """scopes ordered most specific -> most general; first scope with an active rule wins."""
        for sc in scopes:
            for r in self._rules:
                if r.rule_key == key and r.scope == sc and r.effective_from <= on and (r.effective_to is None or on < r.effective_to):
                    return RuleValue(r.value, r.confidence, r.source_ref, sc)
        raise RuleNotFound(f"no rule for {key} in {list(scopes)} on {on}")
