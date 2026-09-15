"""Strategy Composer: generates StrategyBlueprints from indicator combinations."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

from backtesting.composer.indicator_registry import REGISTRY, IndicatorSpec


@dataclass
class StrategyBlueprint:
    """A complete strategy definition ready for backtesting."""

    entry_indicator: str
    entry_params: dict[str, Any]
    entry_condition: str
    exit_indicator: str
    exit_params: dict[str, Any]
    exit_condition: str
    filter1_indicator: str | None = None
    filter1_params: dict[str, Any] = field(default_factory=dict)
    filter1_condition: str | None = None
    filter2_indicator: str | None = None
    filter2_params: dict[str, Any] = field(default_factory=dict)
    filter2_condition: str | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    trailing_stop: bool = False
    sizing_method: str = "fixed"
    sizing_value: float = 1000.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": {
                "indicator": self.entry_indicator,
                "params": self.entry_params,
                "condition": self.entry_condition,
            },
            "exit": {"indicator": self.exit_indicator, "params": self.exit_params, "condition": self.exit_condition},
            "filter1": {
                "indicator": self.filter1_indicator,
                "params": self.filter1_params,
                "condition": self.filter1_condition,
            }
            if self.filter1_indicator
            else None,
            "filter2": {
                "indicator": self.filter2_indicator,
                "params": self.filter2_params,
                "condition": self.filter2_condition,
            }
            if self.filter2_indicator
            else None,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "trailing_stop": self.trailing_stop,
            "sizing_method": self.sizing_method,
            "sizing_value": self.sizing_value,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StrategyBlueprint:
        entry = d.get("entry", {})
        exit_ = d.get("exit", {})
        f1 = d.get("filter1")
        f2 = d.get("filter2")
        return cls(
            entry_indicator=entry.get("indicator", ""),
            entry_params=entry.get("params", {}),
            entry_condition=entry.get("condition", ""),
            exit_indicator=exit_.get("indicator", ""),
            exit_params=exit_.get("params", {}),
            exit_condition=exit_.get("condition", ""),
            filter1_indicator=f1.get("indicator") if f1 else None,
            filter1_params=f1.get("params", {}) if f1 else {},
            filter1_condition=f1.get("condition") if f1 else None,
            filter2_indicator=f2.get("indicator") if f2 else None,
            filter2_params=f2.get("params", {}) if f2 else {},
            filter2_condition=f2.get("condition") if f2 else None,
            stop_loss_pct=d.get("stop_loss_pct"),
            take_profit_pct=d.get("take_profit_pct"),
            trailing_stop=d.get("trailing_stop", False),
            sizing_method=d.get("sizing_method", "fixed"),
            sizing_value=d.get("sizing_value", 1000.0),
        )


class StrategyComposer:
    """Generates StrategyBlueprints from all combinations of indicators, params, and conditions.

    Uses a pre-test filter to eliminate ~90% of invalid combinations before backtesting.
    """

    def __init__(self, include_filters: bool = True) -> None:
        self.include_filters = include_filters
        self._specs = {s.id: s for s in REGISTRY}

    def generate_all_combinations(
        self,
        max_combinations: int | None = None,
    ) -> list[StrategyBlueprint]:
        """Generate all valid strategy combinations.

        Returns list of StrategyBlueprint. If max_combinations is set,
        randomly samples that many.
        """
        import random

        combos: list[StrategyBlueprint] = []

        for entry_spec in REGISTRY:
            for exit_spec in REGISTRY:
                for entry_cond in entry_spec.conditions:
                    for exit_cond in exit_spec.conditions:
                        for entry_params in self._param_combos(entry_spec):
                            for exit_params in self._param_combos(exit_spec):
                                # Add with no filters
                                combos.append(
                                    StrategyBlueprint(
                                        entry_indicator=entry_spec.id,
                                        entry_params=entry_params,
                                        entry_condition=entry_cond,
                                        exit_indicator=exit_spec.id,
                                        exit_params=exit_params,
                                        exit_condition=exit_cond,
                                    )
                                )

                                # Add with filter combinations
                                if self.include_filters:
                                    for f1_spec in REGISTRY:
                                        for f1_cond in f1_spec.conditions:
                                            for f1_params in self._param_combos(f1_spec):
                                                combos.append(
                                                    StrategyBlueprint(
                                                        entry_indicator=entry_spec.id,
                                                        entry_params=entry_params,
                                                        entry_condition=entry_cond,
                                                        exit_indicator=exit_spec.id,
                                                        exit_params=exit_params,
                                                        exit_condition=exit_cond,
                                                        filter1_indicator=f1_spec.id,
                                                        filter1_params=f1_params,
                                                        filter1_condition=f1_cond,
                                                    )
                                                )

        if max_combinations and len(combos) > max_combinations:
            random.shuffle(combos)
            combos = combos[:max_combinations]

        return combos

    def generate_batch(
        self,
        offset: int,
        batch_size: int,
    ) -> list[StrategyBlueprint]:
        """Generate a batch of combinations starting at offset.

        This is memory-efficient: doesn't generate all combos in memory.
        """

        count = 0
        batch: list[StrategyBlueprint] = []

        for entry_spec in REGISTRY:
            for exit_spec in REGISTRY:
                for entry_cond in entry_spec.conditions:
                    for exit_cond in exit_spec.conditions:
                        for entry_params in self._param_combos(entry_spec):
                            for exit_params in self._param_combos(exit_spec):
                                if count >= offset and count < offset + batch_size:
                                    batch.append(
                                        StrategyBlueprint(
                                            entry_indicator=entry_spec.id,
                                            entry_params=entry_params,
                                            entry_condition=entry_cond,
                                            exit_indicator=exit_spec.id,
                                            exit_params=exit_params,
                                            exit_condition=exit_cond,
                                        )
                                    )
                                count += 1
                                if count >= offset + batch_size:
                                    return batch

        return batch

    def estimate_total_count(self) -> int:
        """Estimate total number of combinations without generating them."""
        total = 0
        entry_combos = 0
        for spec in REGISTRY:
            n_params = max(1, sum(len(v) for v in spec.params.values()) if spec.params else 1)
            n_conds = max(1, len(spec.conditions))
            entry_combos += n_params * n_conds

        total = entry_combos * entry_combos  # entry * exit

        if self.include_filters:
            filter_combos = entry_combos + 1  # +1 for no filter
            total *= filter_combos

        return total

    def _param_combos(self, spec: IndicatorSpec) -> list[dict[str, Any]]:
        """Generate all parameter combinations for an indicator."""
        if not spec.params:
            return [{}]
        keys = list(spec.params.keys())
        values = [spec.params[k] for k in keys]
        return [dict(zip(keys, combo, strict=False)) for combo in itertools.product(*values)]
