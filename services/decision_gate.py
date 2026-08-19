"""Smart Decision Gate — market-condition-aware overrides for Gates 2 & 4.

Features
--------
- **Gate 2 override (Model):** When 3-day volatility < 2 % (stagnant market),
  ignore the ML ensemble and rely purely on Mean-Reversion heuristics.
  When volume > 3× the 20-day average, boost ML voting weight by 50 %.

- **Gate 4 override (Regime):** Reads real-time index data from
  ``brsapi_index_values`` and tick-level snapshots from
  ``brsapi_symbol_snapshots`` to detect the current market regime with
  higher precision than the existing volatility heuristic.

Usage
-----
.. code-block:: python

    gate = SmartDecisionGate(session=db_session)
    override = await gate.evaluate(symbol="فولاد", market="stock")

    # Apply to Gate 2:
    if override.ignore_ml:
        candidate.ml_score = 0.0   # force rule-only
    candidate.ml_score *= override.ml_boost_multiplier

    # Apply to Gate 4:
    candidate.volatility_regime = override.volatility_regime
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Cached regime data (per-market, refreshed every 5 min) ──────────────────
_cached_market_state: dict[str, _MarketState] = {}
_CACHE_TTL = 300  # 5 minutes


# ── Public data class ───────────────────────────────────────────────────────


@dataclass
class GateOverride:
    """Override instructions for the decision engine gates.

    Attributes
    ----------
    ignore_ml : bool
        When ``True``, the ML ensemble should be bypassed entirely.
    ml_boost_multiplier : float
        Factor to multiply ML scores by (1.0 = no boost, 1.5 = +50 %).
    volatility_regime : float
        Updated volatility estimate (0–1) to use in Gate 4 & threshold calc.
    regime_label : str
        Human-readable regime: TREND / RANGE / HIGH_VOLATILITY / CRISIS.
    reason : str
        Explanation for the override decision.
    """

    ignore_ml: bool = False
    ml_boost_multiplier: float = 1.0
    volatility_regime: float = 0.5
    regime_label: str = "UNKNOWN"
    reason: str = "پیش‌فرض — بدون override"
    details: dict[str, Any] = field(default_factory=dict)


# ── Smart Decision Gate ─────────────────────────────────────────────────────


class SmartDecisionGate:
    """Reads real market state and produces override instructions.

    Parameters
    ----------
    session : Any | None
        An optional async DB session for fetching market data.
        When ``None``, the gate falls back to data-less heuristics.
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    # ── Public API ─────────────────────────────────────────────────────────

    async def evaluate(
        self,
        symbol: str,
        market: str,
    ) -> GateOverride:
        """Evaluate market conditions for *symbol* in *market*.

        Fetches:
        1. Index volatility (3-day change of TSE index).
        2. Symbol-level volume ratio (today vs 20-day avg).

        Returns a ``GateOverride`` that the caller applies to Gate 2 & 4.
        """
        market_state = await self._fetch_market_state(market)

        # ── Step 1: Detect stagnant market (volatility < threshold) ──
        stagnant, vol_regime = self._detect_stagnation(market_state)

        # ── Step 2: Detect volume surge ──
        vol_ratio = await self._fetch_volume_ratio(symbol, market)
        volume_surge = vol_ratio >= 3.0  # 3× 20-day average

        # ── Step 3: Compose override ──
        reasons: list[str] = []
        details: dict[str, Any] = {
            "index_change_pct_3d": market_state.index_change_3d,
            "volatility_regime_raw": vol_regime,
            "volume_ratio_20d": vol_ratio,
            "volume_surge": volume_surge,
        }

        if stagnant:
            # Low volatility → ignore ML, use mean-reversion only
            override = GateOverride(
                ignore_ml=True,
                ml_boost_multiplier=1.0,
                volatility_regime=vol_regime,
                regime_label="RANGE",
                reason=(
                    f"بازار رکود — دامنه نوسان ۳ روزه {market_state.index_change_3d:.1f}٪ "
                    f"(کمتر از ۲٪). الگوریتم ML نادیده گرفته شد و تنها سیگنال "
                    f"Mean-Reversion استفاده می‌شود."
                ),
                details=details,
            )
            reasons.append("stagnant_market")
        elif volume_surge:
            # Volume surge → boost ML weight
            override = GateOverride(
                ignore_ml=False,
                ml_boost_multiplier=1.5,
                volatility_regime=vol_regime,
                regime_label=market_state.regime_str or "TREND",
                reason=(
                    f"جهش حجم معاملات — نسبت {vol_ratio:.1f} برابر میانگین ۲۰ روزه. "
                    f"وزن رأی مدل ML به میزان ۵۰٪ افزایش یافت."
                ),
                details=details,
            )
            reasons.append("volume_surge")
        else:
            # Normal conditions — no override
            override = GateOverride(
                volatility_regime=vol_regime,
                regime_label=market_state.regime_str or "NORMAL",
                reason="شرایط بازار عادی — بدون تغییر در وزن ML.",
                details=details,
            )

        override.details["reasons"] = reasons
        logger.debug(
            "DecisionGate(%s/%s): ignore_ml=%s ml_boost=%.1f vol=%.2f surge=%s",
            symbol, market, override.ignore_ml, override.ml_boost_multiplier,
            vol_regime, volume_surge,
        )
        return override

    # ── Market-state fetcher ───────────────────────────────────────────────

    async def _fetch_market_state(self, market: str) -> _MarketState:
        """Fetch (or return cached) market-state from the DB.

        Data sources (in order):
          1. ``brsapi_index_values`` — 3-day index change + regime label.
          2. Volatility heuristic fallback.
        """
        now = time.time()
        cached = _cached_market_state.get(market)
        if cached and now - cached.fetched_at < _CACHE_TTL:
            return cached

        state = await self._query_market_state(market)
        _cached_market_state[market] = state
        return state

    async def _query_market_state(self, market: str) -> _MarketState:
        """Query the DB for index-based market state.

        Falls back to a neutral state when DB is unavailable.
        """
        if self._session is None:
            return _MarketState()

        try:
            from sqlalchemy import text

            # 3-day index change (TSE total index).
            r = await self._session.execute(
                text("""
                    SELECT index_change_pct
                    FROM brsapi_index_values
                    WHERE name = 'شاخص کل'
                      AND index_change_pct IS NOT NULL
                    ORDER BY date DESC, fetched_at DESC
                    LIMIT 3
                """)
            )
            rows = r.fetchall()

            if not rows:
                return _MarketState()

            # Use the most recent row for regime, but sum the 3 rows for
            # the cumulative 3-day change.
            latest_change = float(rows[0][0]) if rows[0][0] is not None else 0.0
            three_d_change = sum(
                float(row[0]) for row in rows if row[0] is not None
            )

            abs_change = abs(three_d_change)
            if abs_change >= 1.5:
                regime = "TREND" if three_d_change > 0 else "CRISIS"
            elif abs_change >= 0.8:
                regime = "TREND" if three_d_change > 0 else "HIGH_VOLATILITY"
            else:
                regime = "RANGE"

            # Convert 3-day change to a volatility regime score (0–1).
            vol_regime = min(1.0, abs_change / 5.0)

            return _MarketState(
                fetched_at=time.time(),
                index_change_3d=three_d_change,
                regime_str=regime,
                vol_regime=vol_regime,
            )
        except Exception as e:
            logger.debug("Market-state query failed: %s", e)
            return _MarketState()

    # ── Volume-ratio fetcher ───────────────────────────────────────────────

    async def _fetch_volume_ratio(
        self, symbol: str, market: str,
    ) -> float:
        """Fetch volume ratio: today / 20-day average.

        Uses ``brsapi_symbol_snapshots`` for today's volume and
        ``brsapi_historical_daily`` for the 20-day average.

        Returns 0.0 when data is unavailable.
        """
        if self._session is None:
            return 0.0

        try:
            from sqlalchemy import text

            # Today's volume from latest snapshot.
            r_today = await self._session.execute(
                text("""
                    SELECT trade_volume
                    FROM brsapi_symbol_snapshots
                    WHERE symbol = :sym
                      AND trade_volume > 0
                    ORDER BY fetched_at DESC
                    LIMIT 1
                """),
                {"sym": symbol},
            )
            today_row = r_today.fetchone()
            if not today_row or today_row[0] is None:
                return 0.0

            today_vol = float(today_row[0])

            # 20-day average volume from daily history.
            r_avg = await self._session.execute(
                text("""
                    SELECT AVG(trade_volume)
                    FROM (
                        SELECT trade_volume
                        FROM brsapi_historical_daily
                        WHERE symbol = :sym
                          AND trade_volume > 0
                        ORDER BY date DESC
                        LIMIT 20
                    ) recent
                """),
                {"sym": symbol},
            )
            avg_row = r_avg.fetchone()
            if not avg_row or avg_row[0] is None or float(avg_row[0]) <= 0:
                return 0.0

            avg_vol = float(avg_row[0])
            return today_vol / avg_vol

        except Exception as e:
            logger.debug("Volume-ratio fetch failed for %s: %s", symbol, e)
            return 0.0

    # ── Stagnation detection ───────────────────────────────────────────────

    @staticmethod
    def _detect_stagnation(state: _MarketState) -> tuple[bool, float]:
        """Return (is_stagnant, vol_regime).

        A market is stagnant when the absolute 3-day index change is < 2%.
        """
        abs_change = abs(state.index_change_3d)
        if state.index_change_3d == 0.0:
            return False, state.vol_regime  # no data → not stagnant
        stagnant = abs_change < 2.0
        vol_regime = state.vol_regime if state.vol_regime >= 0 else min(1.0, abs_change / 5.0)
        return stagnant, vol_regime


# ── Internal data class ─────────────────────────────────────────────────────


class _MarketState:
    """Cached market state for a single market."""

    __slots__ = (
        "fetched_at",
        "index_change_3d",
        "regime_str",
        "vol_regime",
    )

    def __init__(
        self,
        fetched_at: float = 0.0,
        index_change_3d: float = 0.0,
        regime_str: str = "UNKNOWN",
        vol_regime: float = 0.5,
    ) -> None:
        self.fetched_at = fetched_at
        self.index_change_3d = index_change_3d
        self.regime_str = regime_str
        self.vol_regime = vol_regime


# ── Global singleton ────────────────────────────────────────────────────────

_gate: SmartDecisionGate | None = None


def get_decision_gate(session: Any | None = None) -> SmartDecisionGate:
    """Get or create the global SmartDecisionGate singleton."""
    global _gate
    if _gate is None:
        _gate = SmartDecisionGate(session=session)
    return _gate