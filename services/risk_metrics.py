"""📉 Portfolio risk, computed from the rows that exist — never from a template.

The previous `/api/v1/risk` endpoint returned eight hardcoded figures («VaR -۲.۴٪»,
«Sharpe ۱.۸۷», …) and the page that renders them had its own fake defaults plus a
`Math.sin`-based "drawdown chart". None of it described anybody's money. This module
replaces that with the rule the rest of the platform follows:

* a metric is derived from stored prices and stored positions, and says so in ``basis``;
* when the inputs are missing — no portfolio, too few days, no benchmark rows — the metric
  comes back ``unknown`` with the reason, rather than a plausible-looking number;
* nothing is annualised, and no risk-free rate is assumed, because the daily count of the
  TSE and a bill rate are not stored anywhere: an annualised Sharpe would be arithmetic
  dressed as observation. So there is no Sharpe and no Sortino here, and «نوسان» means
  *daily* volatility of the observed returns.

The ok/warning/danger colouring only ever comes from :class:`RiskThresholds` — the same
policy `LiveRiskMonitorService` enforces — so a metric is never called "dangerous" by a
threshold nobody chose.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.live_risk_monitor import RiskThresholds

logger = get_logger(__name__)

#: Below this many observed returns nothing is reported at all. A 5-point "VaR" is noise
#: presented as risk, which is worse than saying the window is too short.
MIN_POINTS = 20

MetricState = Literal["ok", "warning", "danger", "unknown"]


@dataclass(frozen=True)
class Metric:
    """One risk figure, its state, and the evidence it was computed from."""

    key: str
    label: str
    unit: str
    state: MetricState
    value: float | None = None
    basis: str = ""
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "label": self.label, "unit": self.unit, "state": self.state,
            "value": self.value, "basis": self.basis, "note": self.note,
        }


def unknown(key: str, label: str, unit: str, note: str) -> Metric:
    return Metric(key=key, label=label, unit=unit, state="unknown", note=note)


def daily_returns(values: Sequence[float]) -> list[float]:
    """Simple returns in percent.

    A pair enters the window only when both sides are positive prices: a stored 0.0 (holiday,
    suspended symbol, failed parse) would otherwise arrive as a -100% day and dominate the
    left tail that VaR and CVaR are read from.
    """

    out: list[float] = []
    for prev, nxt in zip(values, values[1:], strict=False):
        if prev and prev > 0 and nxt and nxt > 0:
            out.append((nxt - prev) / prev * 100)
    return out


def percentile(xs: Sequence[float], q: float) -> float | None:
    """Linear-interpolated percentile (``q`` in 0..1). Deterministic, no numpy dependency."""

    if not xs:
        return None
    ordered = sorted(xs)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * max(0.0, min(1.0, q))
    low = math.floor(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def historical_var(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    """The ``1-confidence`` quantile of observed returns, in percent (negative = loss)."""

    if len(returns) < MIN_POINTS:
        return None
    return percentile(returns, 1.0 - confidence)


def conditional_var(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    """Mean of the tail beyond VaR. Empty tail (a period with no losses) reports None."""

    var = historical_var(returns, confidence)
    if var is None:
        return None
    tail = [r for r in returns if r <= var]
    if not tail:
        return None
    return sum(tail) / len(tail)


def daily_volatility(returns: Sequence[float]) -> float | None:
    """Sample standard deviation of the observed *daily* returns, in percent."""

    if len(returns) < MIN_POINTS:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def drawdown_series(values: Sequence[float]) -> list[float]:
    """Percent below the running peak — 0 while at a new high, negative below it."""

    out: list[float] = []
    peak: float | None = None
    for value in values:
        peak = value if peak is None or value > peak else peak
        out.append(0.0 if not peak else (value - peak) / peak * 100)
    return out


def max_drawdown(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    series = drawdown_series(values)
    return min(series) if series else None


def beta(asset_returns: Sequence[float], benchmark_returns: Sequence[float]) -> float | None:
    """CAPM beta over the paired window. Mismatched or short windows return None."""

    n = min(len(asset_returns), len(benchmark_returns))
    if n < MIN_POINTS:
        return None
    a = list(asset_returns[:n])
    b = list(benchmark_returns[:n])
    ma = sum(a) / n
    mb = sum(b) / n
    var_b = sum((x - mb) ** 2 for x in b)
    if var_b == 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / var_b


def concentration(weights: Sequence[float]) -> float | None:
    """Largest single position weight, in percent."""

    return max(weights) if weights else None


def _state_for(value: float | None, limit: float, invert: bool = False) -> MetricState:
    """Colour by the platform's own threshold: breach = danger, two thirds of it = warning."""

    if value is None:
        return "unknown"
    magnitude = -value if invert else value
    if magnitude > limit:
        return "danger"
    if magnitude > limit * 0.66:
        return "warning"
    return "ok"


@dataclass(frozen=True)
class PositionRow:
    symbol: str
    quantity: float
    avg_cost: float | None
    current_price: float | None
    market_value: float | None
    weight_pct: float | None


class PortfolioRiskService:
    """Assembles the risk picture for one user's own portfolios.

    Read-only by design: `LiveRiskMonitorService.check_all` pushes Telegram messages, so a
    page view must not call it. The same thresholds are reused here, without the side effect.
    """

    #: Days of price history pulled per symbol. A window shorter than MIN_POINTS returns
    #: nothing at all rather than a confident number.
    WINDOW_DAYS = 120

    def __init__(self, session: AsyncSession, thresholds: RiskThresholds | None = None) -> None:
        self.session = session
        self.thresholds = thresholds or RiskThresholds()

    async def portfolios(self, user_id: str) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    "SELECT id, name, initial_capital, current_value, updated_at "
                    "FROM portfolios WHERE owner = :owner ORDER BY name"
                ),
                {"owner": user_id},
            )
        ).fetchall()
        return [
            {
                "id": r[0], "name": r[1], "initial_capital": float(r[2] or 0),
                "current_value": float(r[3] or 0),
                "updated_at": r[4].isoformat() if getattr(r[4], "isoformat", None) else None,
            }
            for r in rows
        ]

    async def positions(self, portfolio_id: str) -> list[PositionRow]:
        rows = (
            await self.session.execute(
                text(
                    "SELECT symbol, quantity, avg_cost, current_price, market_value, weight_pct "
                    "FROM portfolio_positions WHERE portfolio_id = :pid AND symbol IS NOT NULL"
                ),
                {"pid": portfolio_id},
            )
        ).fetchall()
        return [
            PositionRow(
                symbol=str(r[0]), quantity=float(r[1] or 0),
                avg_cost=float(r[2]) if r[2] is not None else None,
                current_price=float(r[3]) if r[3] is not None else None,
                market_value=float(r[4]) if r[4] is not None else None,
                weight_pct=float(r[5]) if r[5] is not None else None,
            )
            for r in rows
        ]

    async def price_series(self, symbols: Sequence[str]) -> dict[str, list[tuple[date, float]]]:
        """Closing prices per symbol on the real calendar, oldest first."""

        if not symbols:
            return {}
        rows = (
            await self.session.execute(
                text(
                    "SELECT symbol, gregorian_date, price_close FROM brsapi_historical_daily "
                    "WHERE symbol = ANY(:symbols) AND gregorian_date IS NOT NULL AND price_close > 0 "
                    "ORDER BY symbol, gregorian_date"
                ),
                {"symbols": list(symbols)},
            )
        ).fetchall()
        out: dict[str, list[tuple[date, float]]] = {}
        for symbol, day, close in rows:
            if isinstance(day, str):  # a DATE column arrives as date; be tolerant of drivers
                continue
            out.setdefault(str(symbol), []).append((day, float(close)))
        return {s: series[-self.WINDOW_DAYS:] for s, series in out.items()}

    async def benchmark_series(self) -> list[tuple[date, float]]:
        """The market index (TEDPIX-style) series used for beta, if it is stored."""

        rows = (
            await self.session.execute(
                text(
                    "SELECT gregorian_date, index_value FROM brsapi_index_values "
                    "WHERE gregorian_date IS NOT NULL AND index_value > 0 "
                    "ORDER BY gregorian_date DESC LIMIT :n"
                ),
                {"n": self.WINDOW_DAYS},
            )
        ).fetchall()
        series = [(r[0], float(r[1])) for r in rows if not isinstance(r[0], str)]
        series.reverse()
        return series

    @staticmethod
    def value_curve(
        positions: Sequence[PositionRow], prices: dict[str, list[tuple[date, float]]]
    ) -> list[tuple[date, float]]:
        """Portfolio value on every date all symbols have traded.

        Dates are intersected rather than forward-filled: inventing a price for a holiday or a
        suspended symbol would put a fabricated point into the return series.
        """

        series = [prices.get(p.symbol) or [] for p in positions]
        if not positions or not all(series):
            return []
        common = set(dict(series[0]))
        for item in series[1:]:
            common &= set(dict(item))
        curves: list[dict[date, float]] = [dict(item) for item in series]
        out: list[tuple[date, float]] = []
        for day in sorted(common):
            total = 0.0
            for position, curve in zip(positions, curves, strict=True):
                total += position.quantity * curve[day]
            out.append((day, total))
        return out

    def _returns(self, pairs: Sequence[tuple[date, float]]) -> list[float]:
        return daily_returns([v for _, v in pairs])

    async def metrics(self, user_id: str) -> dict[str, Any]:
        """The whole risk payload: metrics, drawdown curve, live rule breaches and limits."""

        portfolios = await self.portfolios(user_id)
        if not portfolios:
            return {
                "state": "NO_PORTFOLIO",
                "portfolios": [],
                "metrics": [m.as_dict() for m in self._empty_metrics(
                    "شما پرتفویی در این برنامه ثبت نکرده‌اید."
                )],
                "drawdown": [],
                "alerts": [],
                "limits": self.limit_rows(),
                "note": (
                    "هیچ عدد ریسکی نمایش داده نمی‌شود چون هیچ موقعیتی ذخیره نشده است؛ "
                    "سابقهٔ قیمت‌ها هست، ولی پرتفوی شما نه."
                ),
            }

        all_positions: list[PositionRow] = []
        for portfolio in portfolios:
            all_positions.extend(await self.positions(portfolio["id"]))

        symbols = [p.symbol for p in all_positions]
        prices = await self.price_series(symbols)
        curve = self.value_curve(all_positions, prices)
        returns = self._returns(curve)
        benchmark = self._returns(await self.benchmark_series())

        var = historical_var(returns)
        cvar = conditional_var(returns)
        vol = daily_volatility(returns)
        mdd = max_drawdown([v for _, v in curve])
        weights = [p.weight_pct for p in all_positions if p.weight_pct is not None]
        conc = concentration(weights)
        b = beta(returns, benchmark) if benchmark else None

        missing_days = (
            f"کمتر از {MIN_POINTS} بازده روزانه در دسترس است ({len(returns)} تا)."
            if len(returns) < MIN_POINTS
            else ""
        )
        basis_curve = f"{len(returns)} بازده روزانهٔ واقعی از {len(symbols)} نماد"

        metrics = [
            Metric(
                key="var_95", label="VaR (۹۵٪)", unit="٪",
                state=_state_for(var, self.thresholds.daily_loss_limit_pct, invert=True)
                if var is not None else "unknown",
                value=round(var, 2) if var is not None else None,
                basis=basis_curve, note=missing_days,
            ),
            Metric(
                key="cvar_95", label="CVaR (۹۵٪)", unit="٪",
                state=_state_for(cvar, self.thresholds.daily_loss_limit_pct, invert=True)
                if cvar is not None else "unknown",
                value=round(cvar, 2) if cvar is not None else None,
                basis=basis_curve,
                note=missing_days or ("هیچ بازدهی پایین‌تر از VaR در این پنجره نبود." if cvar is None else ""),
            ),
            Metric(
                key="volatility_daily", label="نوسان روزانه", unit="٪",
                state="ok" if vol is not None else "unknown",
                value=round(vol, 2) if vol is not None else None,
                basis=basis_curve,
                note=missing_days or "سالانه‌سازی نشده: تعداد روز معاملاتی بازار مبنایی در برنامه ذخیره نمی‌شود.",
            ),
            Metric(
                key="max_drawdown", label="بیشترین افت", unit="٪",
                state=_state_for(mdd, self.thresholds.max_drawdown_pct, invert=True)
                if mdd is not None else "unknown",
                value=round(mdd, 2) if mdd is not None else None,
                basis=basis_curve, note=missing_days,
            ),
            Metric(
                key="beta", label="بتا نسبت به شاخص کل", unit="",
                state="ok" if b is not None else "unknown",
                value=round(b, 2) if b is not None else None,
                basis=f"{len(benchmark)} بازده شاخص از `brsapi_index_values`",
                note="" if b is not None else "شاخص کل در پنجرهٔ لازم ذخیره نشده است.",
            ),
            Metric(
                key="concentration", label="تمرکز در بزرگ‌ترین موقعیت", unit="٪",
                state=_state_for(conc, self.thresholds.max_position_concentration_pct)
                if conc is not None else "unknown",
                value=round(conc, 2) if conc is not None else None,
                basis=f"{len(weights)} وزن ذخیره‌شده در `portfolio_positions.weight_pct`",
                note="" if conc is not None else "وزن هیچ موقعیتی ذخیره نشده است.",
            ),
            Metric(
                key="sharpe", label="شارپ / سورتینو", unit="",
                state="unknown",
                basis="",
                note="نرخ بدون ریسک در هیچ جدولی ذخیره نمی‌شود؛ نسبت‌های ریسک-بازده محاسبه نمی‌شوند.",
            ),
        ]

        alerts = self._alerts(portfolios, all_positions)
        values = [v for _, v in curve]
        dd = [
            {"index": i, "date": day.isoformat(), "drawdown": round(depth, 3)}
            for i, ((day, _), depth) in enumerate(
                zip(curve, drawdown_series(values), strict=True), start=0
            )
        ]
        return {
            "state": "OK",
            "portfolios": portfolios,
            "metrics": [m.as_dict() for m in metrics],
            "drawdown": dd,
            "alerts": alerts,
            "limits": self.limit_rows(portfolios, all_positions),
            "note": "",
        }

    def _empty_metrics(self, why: str) -> list[Metric]:
        return [
            unknown("var_95", "VaR (۹۵٪)", "٪", why),
            unknown("cvar_95", "CVaR (۹۵٪)", "٪", why),
            unknown("volatility_daily", "نوسان روزانه", "٪", why),
            unknown("max_drawdown", "بیشترین افت", "٪", why),
            unknown("beta", "بتا نسبت به شاخص کل", "", why),
            unknown("concentration", "تمرکز در بزرگ‌ترین موقعیت", "٪", why),
            unknown("sharpe", "شارپ / سورتینو", "", "نرخ بدون ریسک در برنامه ذخیره نمی‌شود."),
        ]

    def limit_rows(
        self, portfolios: Sequence[dict[str, Any]] = (), positions: Sequence[PositionRow] = ()
    ) -> list[dict[str, Any]]:
        """The platform's own thresholds, with the measured value where one exists.

        A limit is a policy the app enforces (`RiskThresholds`), so showing it is not
        invention; the *current* column is only filled when positions support it.
        """

        weights = [p.weight_pct for p in positions if p.weight_pct is not None]
        conc = concentration(weights)
        drawdowns = [
            ((p["current_value"] - p["initial_capital"]) / p["initial_capital"] * 100)
            for p in portfolios
            if p["initial_capital"]
        ]
        rows = [
            {
                "type": "max_drawdown", "label": "حداکثر افت مجاز",
                "limit": self.thresholds.max_drawdown_pct, "unit": "٪",
                "current": round(min(drawdowns), 2) if drawdowns else None,
            },
            {
                "type": "position_concentration", "label": "حداکثر تمرکز در یک نماد",
                "limit": self.thresholds.max_position_concentration_pct, "unit": "٪",
                "current": round(conc, 2) if conc is not None else None,
            },
            {
                "type": "stop_loss", "label": "حد ضرر هر نماد",
                "limit": self.thresholds.stop_loss_pct, "unit": "٪",
                "current": self._worst_open_loss(positions),
            },
            {
                "type": "daily_loss", "label": "زیان مجاز",
                "limit": self.thresholds.daily_loss_limit_pct, "unit": "٪",
                "current": None,
            },
        ]
        for row in rows:
            current, limit = row["current"], row["limit"]
            if current is None:
                row["status"] = "unknown"
            elif abs(current) > limit:
                row["status"] = "exceeded"
            elif abs(current) > limit * 0.66:
                row["status"] = "warning"
            else:
                row["status"] = "ok"
        return rows

    @staticmethod
    def _worst_open_loss(positions: Sequence[PositionRow]) -> float | None:
        losses = [
            ((p.current_price - p.avg_cost) / p.avg_cost * 100)
            for p in positions
            if p.avg_cost and p.current_price
        ]
        return round(min(losses), 2) if losses else None

    def _alerts(
        self, portfolios: Sequence[dict[str, Any]], positions: Sequence[PositionRow]
    ) -> list[dict[str, Any]]:
        """Live rule breaches, derived from the same thresholds the monitor enforces."""

        out: list[dict[str, Any]] = []
        for position in positions:
            if position.avg_cost and position.current_price:
                loss = (position.current_price - position.avg_cost) / position.avg_cost * 100
                if loss < -self.thresholds.stop_loss_pct:
                    out.append({
                        "rule": "stop_loss", "severity": "high", "symbol": position.symbol,
                        "message": f"{position.symbol} {round(-loss, 2)}٪ زیر قیمت تمام‌شده است "
                                   f"(حد {self.thresholds.stop_loss_pct}٪).",
                    })
            if (position.weight_pct or 0) > self.thresholds.max_position_concentration_pct:
                out.append({
                    "rule": "concentration", "severity": "high", "symbol": position.symbol,
                    "message": f"وزن {position.symbol} ({position.weight_pct}٪) از حد "
                               f"{self.thresholds.max_position_concentration_pct}٪ عبور کرده.",
                })
        for portfolio in portfolios:
            if portfolio["initial_capital"]:
                change = (portfolio["current_value"] - portfolio["initial_capital"]) / portfolio["initial_capital"] * 100
                if change < -self.thresholds.max_drawdown_pct:
                    out.append({
                        "rule": "drawdown", "severity": "high", "symbol": None,
                        "message": f"پرتفوی «{portfolio['name']}» {round(-change, 2)}٪ افت کرده "
                                   f"(حد {self.thresholds.max_drawdown_pct}٪).",
                    })
        return out


__all__ = [
    "MIN_POINTS",
    "Metric",
    "PortfolioRiskService",
    "PositionRow",
    "beta",
    "conditional_var",
    "concentration",
    "daily_returns",
    "daily_volatility",
    "drawdown_series",
    "historical_var",
    "max_drawdown",
    "percentile",
]
