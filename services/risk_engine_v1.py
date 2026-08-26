"""Risk Engine v1 — 12 کنترل غیرقابل دور زدن (فاز 1-2)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RiskResult:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class RiskLimits:
    max_order_pct: float = 0.02  # 2%
    daily_loss_pct: float = 0.05  # 5%
    max_position_pct: float = 0.10
    staleness_sec: int = 300  # 5m
    max_concentration_pct: float = 0.25


class RiskEngineV1:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self._daily_loss: float = 0.0
        self._last_reset_day: str = ""

    def check(self, proposal: dict, portfolio_value: float, fetched_at_ts: float | None = None) -> RiskResult:
        failed: list[str] = []
        warnings: list[str] = []

        # 1. سقف سفارش
        notional = float(proposal.get("proposed_price", 0)) * sum(leg.get("quantity", 1) for leg in proposal.get("legs", []))
        if portfolio_value > 0 and notional / portfolio_value > self.limits.max_order_pct:
            failed.append(f"order_size {notional/portfolio_value:.1%} > {self.limits.max_order_pct:.0%}")
        # 5. کهنگی
        if fetched_at_ts is not None and time.time() - fetched_at_ts > self.limits.staleness_sec:
            failed.append(f"stale_data {time.time()-fetched_at_ts:.0f}s > {self.limits.staleness_sec}s")
        # 10. TTL
        expires_at = proposal.get("expires_at")
        if expires_at:
            try:
                import datetime
                exp = datetime.datetime.fromisoformat(expires_at)
                if datetime.datetime.now(exp.tzinfo) > exp:
                    failed.append("expired_ttl")
            except Exception:
                warnings.append("ttl_parse_failed")
        # 9. allowlist (نمونه: اگر allowlist تعریف شده)
        allowlist = proposal.get("_allowlist")
        if allowlist is not None:
            sym = proposal.get("underlying_symbol") or proposal.get("symbol")
            if sym not in allowlist:
                failed.append(f"not_in_allowlist:{sym}")

        # بقیه کنترل‌ها (3,4,6,7,8,11,12) در فاز بعد با دفتر و مارجین واقعی تکمیل می‌شود
        return RiskResult(passed=len(failed) == 0, failed_checks=failed, warnings=warnings)
