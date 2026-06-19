from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapacityResult:
    """Result of a capacity analysis."""
    max_capital: float = 0.0
    adv_used: float = 0.0
    participation_rate: float = 0.0
    expected_impact_bps: float = 0.0
    slippage_bps: float = 0.0
    sharpe_decay: float = 0.0
    turnover: float = 0.0
    capacity_tier: str = ""
    limiting_factor: str = ""
    details: dict[str, float] = field(default_factory=dict)


@dataclass
class CapacityEngine:
    """Analyze how much capital a strategy can absorb before alpha decays.

    Calculates the maximum capital a strategy can manage given:
    - Average Daily Volume (ADV) of the traded instruments
    - Strategy turnover rate
    - Maximum acceptable market impact
    - Liquidity depth profile

    Usage:
        engine = CapacityEngine()
        result = engine.estimate(
            adv=5_000_000_000,      # 5B IRR daily volume
            turnover=0.2,            # 20% daily turnover
            max_impact_bps=10,       # max 10 bps impact
            participation=0.05,      # 5% of daily volume
        )
        print(f"Max capital: {result.max_capital:,.0f}")
        print(f"Tier: {result.capacity_tier}")
    """

    # Conservative: 1% participation
    # Moderate: 5% participation
    # Aggressive: 10% participation

    def estimate(
        self,
        adv: float,
        turnover: float = 0.2,
        max_impact_bps: float = 10.0,
        participation: float = 0.05,
        impact_coefficient: float = 0.1,
        impact_alpha: float = 0.6,
    ) -> CapacityResult:
        """Estimate strategy capital capacity.

        Args:
            adv: Average Daily Volume in currency (e.g., IRR)
            turnover: Daily portfolio turnover rate (0.0 - 1.0)
            max_impact_bps: Maximum acceptable market impact in bps
            participation: Maximum fraction of daily volume to trade
            impact_coefficient: Market impact model coefficient (eta)
            impact_alpha: Market impact model exponent (alpha)

        Returns:
            CapacityResult with detailed breakdown
        """
        if adv <= 0 or turnover <= 0:
            return CapacityResult()

        # Daily traded volume by strategy
        daily_trade_volume = adv * participation
        participation_rate = participation * 100  # as percentage

        # Maximum capital from turnover constraint
        max_capital_turnover = daily_trade_volume / max(turnover, 0.01)

        # Maximum capital from impact constraint
        # impact = eta * (Q/ADV)^alpha
        # solve for Q: Q = ADV * (impact/eta)^(1/alpha)
        max_impact_ratio = (max_impact_bps / 10000) / impact_coefficient
        if max_impact_ratio > 0:
            max_q_ratio = max_impact_ratio ** (1.0 / max(impact_alpha, 0.01))
            max_trade_volume = adv * max_q_ratio
            max_capital_impact = max_trade_volume / max(turnover, 0.01)
        else:
            max_capital_impact = float("inf")

        # Determine limiting factor
        max_capital = min(max_capital_turnover, max_capital_impact)
        if max_capital_turnover <= max_capital_impact:
            limiting_factor = "participation_rate"
        else:
            limiting_factor = "market_impact"

        # Expected impact at max capital
        effective_q = max_capital * turnover
        expected_impact = impact_coefficient * (effective_q / max(adv, 1)) ** impact_alpha
        expected_impact_bps = expected_impact * 10000

        # Capacity tier
        if max_capital < 10_000_000:
            tier = "retail"
        elif max_capital < 100_000_000:
            tier = "small_institutional"
        elif max_capital < 1_000_000_000:
            tier = "medium_institutional"
        elif max_capital < 10_000_000_000:
            tier = "large_institutional"
        else:
            tier = "fund"

        # Sharpe decay estimate (simplified)
        # Higher impact → lower realized Sharpe
        sharpe_decay = expected_impact_bps / max(max_impact_bps, 1)

        return CapacityResult(
            max_capital=max_capital,
            adv_used=adv,
            participation_rate=participation_rate,
            expected_impact_bps=expected_impact_bps,
            slippage_bps=expected_impact_bps * 0.5,  # rough estimate
            sharpe_decay=sharpe_decay,
            turnover=turnover,
            capacity_tier=tier,
            limiting_factor=limiting_factor,
            details={
                "adv": adv,
                "turnover": turnover,
                "participation_pct": participation_rate,
                "max_impact_bps": max_impact_bps,
                "daily_trade_volume": daily_trade_volume,
                "max_capital_turnover": max_capital_turnover,
                "max_capital_impact": max_capital_impact,
                "impact_coefficient": impact_coefficient,
                "impact_alpha": impact_alpha,
            },
        )

    def estimate_multi_instrument(
        self,
        instruments: list[dict[str, float]],
        turnover: float = 0.2,
        max_impact_bps: float = 10.0,
        participation: float = 0.05,
    ) -> CapacityResult:
        """Estimate capacity across multiple instruments.

        Args:
            instruments: list of dicts with keys 'adv' and optionally 'weight'
            turnover: portfolio turnover
            max_impact_bps: max acceptable impact
            participation: max participation rate

        Returns:
            Combined CapacityResult
        """
        if not instruments:
            return CapacityResult()

        total_weight = sum(inst.get("weight", 1.0) for inst in instruments)
        weighted_adv = sum(inst["adv"] * inst.get("weight", 1.0) for inst in instruments) / max(total_weight, 1)

        # For multi-instrument, impact is spread across names
        n_instruments = len(instruments)
        effective_participation = participation * min(n_instruments * 0.5, 1.0)  # diversification benefit

        return self.estimate(
            adv=weighted_adv,
            turnover=turnover,
            max_impact_bps=max_impact_bps,
            participation=effective_participation,
        )
