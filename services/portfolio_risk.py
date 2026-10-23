"""Gate 9 — the real portfolio-risk context for the signal decision engine.

``services/quant_signal_orchestrator.py`` used to hand the decision engine
``portfolio_risk_approved=True`` along with a comment admitting that the
portfolio validator "is not called here" (audit finding D-03: Gate 9 was
fail-OPEN, contradicting the fail-closed claim made for the pipeline).

This module is that missing validator. It reads the paper-trading ledger —
``paper_trades`` / ``paper_equity_history`` (migrations 0029, 0106) — and
derives the two figures Gate 9 checks:

  ``open_risk_pct``            max loss still at risk across open positions
  ``correlated_exposure_pct``  capital allocated to the candidate's market

When the ledger cannot be read the state is *not approved*, so Gate 9 blocks
the candidate instead of silently releasing it. Every statement is a SELECT.

Risk of one open position is ``capital_allocated * (entry - stop) / entry``
when the position carries a stop below its entry, otherwise a conservative
``DEFAULT_STOP_PCT`` of the allocation. Equity is the latest
``paper_equity_history`` row, falling back to the paper account's initial
capital.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_INITIAL_CAPITAL = 1_000_000_000.0  # 1B Rial — same base as PaperTradingService
DEFAULT_STOP_PCT = 0.05  # assumed stop when an open position carries none

_OPEN_POSITIONS_SQL = text(
    """
    SELECT market,
           COALESCE(SUM(
               CASE
                   WHEN stop_loss_price IS NOT NULL
                        AND entry_price IS NOT NULL
                        AND entry_price > 0
                        AND stop_loss_price < entry_price
                   THEN COALESCE(capital_allocated, 0)
                        * (entry_price - stop_loss_price) / entry_price
                   ELSE COALESCE(capital_allocated, 0) * :stop_pct
               END
           ), 0)                                            AS open_risk,
           COALESCE(SUM(COALESCE(capital_allocated, 0)), 0) AS exposure,
           COUNT(*)                                         AS positions
    FROM paper_trades
    WHERE status = 'open'
    GROUP BY market
    """
)

_LATEST_EQUITY_SQL = text(
    "SELECT equity FROM paper_equity_history ORDER BY date DESC LIMIT 1"
)


def compute_open_risk(
    rows: Iterable[Mapping[str, Any]],
    equity: float | None,
    stop_pct: float = DEFAULT_STOP_PCT,
) -> tuple[float, dict[str, float]]:
    """Pure helper: ``(open_risk_pct, exposure_pct_by_market)``.

    ``rows`` are ledger aggregates per market with ``open_risk`` and
    ``exposure`` keys; every ratio is taken against the account equity.
    """
    base = float(equity) if equity and float(equity) > 0 else DEFAULT_INITIAL_CAPITAL
    total_risk = 0.0
    exposure: dict[str, float] = {}
    for row in rows:
        market = str(row["market"] or "unknown")
        exposure[market] = exposure.get(market, 0.0) + float(row["exposure"] or 0.0)
        total_risk += float(row["open_risk"] or 0.0)
    return total_risk / base, {m: v / base for m, v in exposure.items()}


@dataclass(frozen=True)
class PortfolioRiskState:
    """Portfolio context handed to Gate 9 for one pipeline run."""

    approved: bool
    equity: float = DEFAULT_INITIAL_CAPITAL
    open_risk_pct: float = 0.0
    exposure_by_market: Mapping[str, float] = field(default_factory=dict)
    reason: str = ""

    def for_market(self, market: str) -> tuple[bool, float, float]:
        """``(approved, open_risk_pct, correlated_exposure_pct)`` for *market*."""
        correlated = float(self.exposure_by_market.get(market or "", 0.0))
        return self.approved, self.open_risk_pct, correlated


def unapproved_state(reason: str) -> PortfolioRiskState:
    """State for an unreadable ledger — Gate 9 must BLOCK on this."""
    return PortfolioRiskState(approved=False, reason=reason)


async def load_portfolio_risk(session: AsyncSession | None = None) -> PortfolioRiskState:
    """Read the paper-trading ledger; fail CLOSED when it cannot be read.

    The pipeline's own callers (API endpoints, the paper-trading job) run after
    the process has booted its database, so the ledger is read through either
    the injected session or ``core.database.async_session_factory`` — the same
    handle ``SignalDecisionEngine`` uses for its regime query. A cold handle is
    reported as an unapproved state rather than opened here: a one-off engine
    (or a unit test) must not spin up a database connection of its own.
    """
    try:
        if session is not None:
            return await _read(session)

        import core.database as _db

        if _db.async_session_factory is None:
            return unapproved_state("database not initialised in this process")
        async with _db.async_session_factory() as own_session:
            return await _read(own_session)
    except Exception as exc:  # noqa: BLE001 — any failure must block, never approve
        logger.warning(
            "Portfolio risk unavailable (%s: %s) — Gate 9 fails CLOSED",
            type(exc).__name__,
            exc,
        )
        return unapproved_state(f"{type(exc).__name__}: {exc}")


async def _read(session: AsyncSession) -> PortfolioRiskState:
    rows = (
        await session.execute(_OPEN_POSITIONS_SQL, {"stop_pct": DEFAULT_STOP_PCT})
    ).mappings().all()
    equity_row = (await session.execute(_LATEST_EQUITY_SQL)).first()
    equity = (
        float(equity_row[0])
        if equity_row and equity_row[0] is not None
        else DEFAULT_INITIAL_CAPITAL
    )
    open_risk_pct, exposure = compute_open_risk(rows, equity, DEFAULT_STOP_PCT)
    logger.debug(
        "Portfolio risk: equity=%.0f open_risk=%.2f%% markets=%d",
        equity,
        open_risk_pct * 100,
        len(exposure),
    )
    return PortfolioRiskState(
        approved=True,
        equity=equity,
        open_risk_pct=open_risk_pct,
        exposure_by_market=exposure,
        reason="paper-trading ledger read",
    )
