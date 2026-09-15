from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from .market_data import MarketTick, QualityFlag


@dataclass
class ValidationReport:
    accepted: list[MarketTick] = field(default_factory=list)
    rejected: int = 0
    suspicious: int = 0
    errors: list[str] = field(default_factory=list)


class MarketDataValidator:
    """Validates canonical ticks and flags, rather than silently losing, outliers."""

    def __init__(
        self,
        *,
        max_jump_pct: Decimal = Decimal("0.20"),
        max_age: timedelta = timedelta(minutes=20),
        max_spread_pct: Decimal = Decimal("0.10"),
    ) -> None:
        self.max_jump_pct = max_jump_pct
        self.max_age = max_age
        self.max_spread_pct = max_spread_pct

    def validate(
        self,
        ticks: Iterable[MarketTick],
        *,
        last_prices: dict[tuple[str, str], Decimal] | None = None,
        now: datetime | None = None,
    ) -> ValidationReport:
        report = ValidationReport()
        previous = last_prices or {}
        current_time = (now or datetime.now(UTC)).astimezone(UTC)

        for tick in ticks:
            reasons: list[str] = []
            if tick.price <= 0:
                report.rejected += 1
                report.errors.append(f"{tick.source}/{tick.instrument}: non-positive price")
                continue

            age = current_time - tick.observed_at
            if age > self.max_age:
                reasons.append(f"stale:{int(age.total_seconds())}s")

            previous_price = previous.get((tick.source, tick.instrument))
            if previous_price and previous_price > 0:
                jump = abs(tick.price - previous_price) / previous_price
                if jump > self.max_jump_pct:
                    reasons.append(f"jump:{jump:.4f}")

            if tick.bid is not None and tick.ask is not None:
                if tick.ask < tick.bid:
                    reasons.append("crossed_book")
                elif tick.bid > 0:
                    spread = (tick.ask - tick.bid) / tick.bid
                    if spread > self.max_spread_pct:
                        reasons.append(f"wide_spread:{spread:.4f}")

            quality = QualityFlag.CLEAN
            if reasons:
                quality = QualityFlag.STALE if any(r.startswith("stale:") for r in reasons) else QualityFlag.SUSPICIOUS
                report.suspicious += 1

            report.accepted.append(tick.model_copy(update={"quality": quality, "quality_reasons": reasons}))
            previous[(tick.source, tick.instrument)] = tick.price

        return report
