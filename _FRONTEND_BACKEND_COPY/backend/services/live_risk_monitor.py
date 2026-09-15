from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RiskThresholds:
    stop_loss_pct: float = 5.0
    max_drawdown_pct: float = 10.0
    max_position_concentration_pct: float = 25.0
    daily_loss_limit_pct: float = 3.0


@dataclass
class RiskCheckResult:
    rule: str
    triggered: bool
    details: dict[str, Any] = field(default_factory=dict)


class LiveRiskMonitorService:
    """Periodically checks portfolio positions against risk rules.

    Designed to run every 5 minutes during market hours (08:30-15:30 Asia/Tehran).
    Uses AlertService and TelegramSender for notifications.
    """

    def __init__(
        self,
        session: Any = None,
        thresholds: RiskThresholds | None = None,
    ) -> None:
        self._session = session
        self._thresholds = thresholds or RiskThresholds()

    @property
    def thresholds(self) -> RiskThresholds:
        return self._thresholds

    @thresholds.setter
    def thresholds(self, value: RiskThresholds) -> None:
        self._thresholds = value

    async def check_all(self, portfolio_id: str | None = None) -> list[RiskCheckResult]:
        """Evaluate all risk rules and return results.

        If portfolio_id is provided, checks that specific portfolio.
        Otherwise checks all portfolios.
        """
        results: list[RiskCheckResult] = []

        try:
            from core.database import get_session
            from models.portfolio import PortfolioModel
            from repositories.portfolio_repository import PortfolioRepository

            async for session in get_session():
                repo = PortfolioRepository(session)
                from sqlalchemy import select

                if portfolio_id:
                    stmt = select(PortfolioModel).where(PortfolioModel.id == portfolio_id)
                    res = await session.execute(stmt)
                    portfolios = [res.scalar_one()]
                else:
                    stmt = select(PortfolioModel)
                    res = await session.execute(stmt)
                    portfolios = list(res.scalars().all())

                for portfolio in portfolios:
                    if not portfolio.id:
                        continue
                    positions_res = await repo.get_positions(portfolio.id)
                    if not positions_res.success or not positions_res.value:
                        continue

                    positions = positions_res.value
                    initial_capital = portfolio.initial_capital or 0.0
                    current_value = portfolio.current_value or 0.0

                    # Stop-loss check
                    stop_results = self._check_stop_loss(positions)
                    results.extend(stop_results)

                    # Drawdown check
                    dd_results = self._check_drawdown(portfolio.name, initial_capital, current_value)
                    results.extend(dd_results)

                    # Concentration check
                    conc_results = self._check_concentration(portfolio.name, positions)
                    results.extend(conc_results)

                    # Daily loss limit (uses unrealized_pnl total vs initial capital)
                    daily_results = self._check_daily_loss(portfolio.name, initial_capital, positions)
                    results.extend(daily_results)

                break  # single iteration over get_session

        except Exception as e:
            logger.error("Risk check failed: %s", e)
            results.append(
                RiskCheckResult(
                    rule="error",
                    triggered=True,
                    details={"error": str(e)},
                )
            )

        # Send notifications for triggered rules
        triggered = [r for r in results if r.triggered]
        if triggered:
            await self._send_alerts(triggered)

        return results

    def _check_stop_loss(self, positions: list[dict[str, Any]]) -> list[RiskCheckResult]:
        results: list[RiskCheckResult] = []
        for pos in positions:
            symbol = pos.get("symbol", "Unknown")
            avg_cost = pos.get("avg_cost") or 0.0
            current_price = pos.get("current_price") or 0.0
            if avg_cost <= 0:
                continue
            loss_pct = ((current_price - avg_cost) / avg_cost) * 100
            triggered = loss_pct < -self._thresholds.stop_loss_pct
            results.append(
                RiskCheckResult(
                    rule="stop_loss",
                    triggered=triggered,
                    details={
                        "symbol": symbol,
                        "avg_cost": avg_cost,
                        "current_price": current_price,
                        "loss_pct": round(loss_pct, 2),
                        "threshold_pct": self._thresholds.stop_loss_pct,
                    },
                )
            )
        return results

    def _check_drawdown(
        self, portfolio_name: str, initial_capital: float, current_value: float
    ) -> list[RiskCheckResult]:
        if initial_capital <= 0:
            return []
        drawdown_pct = ((current_value - initial_capital) / initial_capital) * 100
        triggered = drawdown_pct < -self._thresholds.max_drawdown_pct
        return [
            RiskCheckResult(
                rule="drawdown",
                triggered=triggered,
                details={
                    "portfolio": portfolio_name,
                    "initial_capital": initial_capital,
                    "current_value": current_value,
                    "drawdown_pct": round(drawdown_pct, 2),
                    "threshold_pct": self._thresholds.max_drawdown_pct,
                },
            )
        ]

    def _check_concentration(self, portfolio_name: str, positions: list[dict[str, Any]]) -> list[RiskCheckResult]:
        results: list[RiskCheckResult] = []
        for pos in positions:
            symbol = pos.get("symbol", "Unknown")
            weight = pos.get("weight_pct") or 0.0
            triggered = weight > self._thresholds.max_position_concentration_pct
            results.append(
                RiskCheckResult(
                    rule="concentration",
                    triggered=triggered,
                    details={
                        "portfolio": portfolio_name,
                        "symbol": symbol,
                        "weight_pct": round(weight, 2),
                        "threshold_pct": self._thresholds.max_position_concentration_pct,
                    },
                )
            )
        return results

    def _check_daily_loss(
        self, portfolio_name: str, initial_capital: float, positions: list[dict[str, Any]]
    ) -> list[RiskCheckResult]:
        total_unrealized = sum(p.get("unrealized_pnl") or 0.0 for p in positions)
        if initial_capital <= 0:
            return []
        daily_loss_pct = (total_unrealized / initial_capital) * 100
        triggered = daily_loss_pct < -self._thresholds.daily_loss_limit_pct
        return [
            RiskCheckResult(
                rule="daily_loss",
                triggered=triggered,
                details={
                    "portfolio": portfolio_name,
                    "total_unrealized_pnl": round(total_unrealized, 2),
                    "daily_loss_pct": round(daily_loss_pct, 2),
                    "threshold_pct": self._thresholds.daily_loss_limit_pct,
                },
            )
        ]

    async def _send_alerts(self, triggered: list[RiskCheckResult]) -> None:
        """Send notifications for all triggered risk rules via Telegram."""
        try:
            from integrations.notifications import NotificationTemplates, TelegramSender

            sender = TelegramSender()

            for result in triggered:
                rule = result.rule
                d = result.details

                if rule == "stop_loss":
                    msg = NotificationTemplates.stop_loss_alert(
                        symbol=d.get("symbol", "?"),
                        current_price=d.get("current_price", 0),
                        stop_price=d.get("avg_cost", 0) * (1 - self._thresholds.stop_loss_pct / 100),
                        loss_pct=d.get("loss_pct", 0),
                    )
                elif rule == "drawdown":
                    msg = NotificationTemplates.drawdown_warning(
                        current_drawdown=d.get("drawdown_pct", 0),
                        max_drawdown=self._thresholds.max_drawdown_pct,
                    )
                elif rule == "concentration":
                    msg = NotificationTemplates.position_concentration_warning(
                        symbol=d.get("symbol", "?"),
                        weight_pct=d.get("weight_pct", 0),
                        max_pct=self._thresholds.max_position_concentration_pct,
                    )
                elif rule == "daily_loss":
                    msg = NotificationTemplates.daily_loss_warning(
                        daily_pnl=d.get("total_unrealized_pnl", 0),
                        loss_limit=self._thresholds.daily_loss_limit_pct,
                    )
                else:
                    msg = f"Risk alert: {rule} — {d}"

                await sender.send(msg)
                logger.warning("Risk alert sent: %s — %s", rule, d)

        except Exception as e:
            logger.error("Failed to send risk alerts: %s", e)
