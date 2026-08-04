"""Multi-Timeframe Confirmer — validates signals across multiple timeframes.

A signal is stronger when multiple timeframes agree on the direction.
This reduces false signals from short-term noise.

Supported timeframes: daily, 2day, 3day, weekly, monthly, quarterly
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from services.multi_market_signal_engine import (
    MultiMarketSignalEngine,  # used by _trend_for_timeframe for TIMEFRAMES dict
)

logger = get_logger(__name__)


@dataclass
class TimeframeVote:
    """Vote from a single timeframe."""
    timeframe: str
    direction: str
    score: float
    strength: float
    confidence: float
    supports_signal: bool  # agrees with the primary signal?


@dataclass
class MultiTimeframeResult:
    """Result of multi-timeframe confirmation."""
    symbol: str
    market: str
    primary_direction: str
    confirmed_direction: str
    confirmation_level: str  # strong / moderate / weak / opposite
    timeframe_votes: list[TimeframeVote]
    agreement_ratio: float  # 0-1: proportion of timeframes agreeing
    score_boost: float      # multiplier for the signal score

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "primary_direction": self.primary_direction,
            "confirmed_direction": self.confirmed_direction,
            "confirmation_level": self.confirmation_level,
            "timeframe_votes": [
                {
                    "timeframe": v.timeframe,
                    "direction": v.direction,
                    "score": round(v.score, 2),
                    "strength": round(v.strength, 3),
                    "supports_signal": v.supports_signal,
                }
                for v in self.timeframe_votes
            ],
            "agreement_ratio": round(self.agreement_ratio, 2),
            "score_boost": round(self.score_boost, 2),
        }


class MultiTimeframeConfirmer:
    """Validates signals across multiple timeframes to confirm direction."""

    # Hierarchy: shorter timeframes are more reactive, longer are more reliable
    TIMEFRAME_HIERARCHY = ["daily", "2day", "3day", "weekly", "monthly", "quarterly"]

    def __init__(self) -> None:
        pass

    async def confirm_signal(
        self,
        symbol: str,
        market: str,
        primary_direction: str,
        primary_timeframe: str = "daily",
        required_agreement: float = 0.5,  # minimum agreement ratio
    ) -> MultiTimeframeResult:
        """Check signal across multiple timeframes and return confirmation.

        Args:
            symbol: the trading symbol
            market: market type (stock, gold, etc.)
            primary_direction: the original signal direction
            primary_timeframe: the primary signal's timeframe
            required_agreement: minimum proportion of timeframes that must agree

        Returns:
            MultiTimeframeResult with confirmation level and score boost
        """
        timeframes_to_check = self.TIMEFRAME_HIERARCHY.copy()

        # Remove primary timeframe from check list (it's already confirmed)
        if primary_timeframe in timeframes_to_check:
            timeframes_to_check.remove(primary_timeframe)

        votes: list[TimeframeVote] = []

        for tf in timeframes_to_check:
            vote = await self._get_timeframe_vote(
                symbol=symbol,
                market=market,
                timeframe=tf,
                primary_direction=primary_direction,
            )
            votes.append(vote)

        # Calculate agreement
        total_votes = len(votes)

        if total_votes > 0:
            # Weight by hierarchy position (longer timeframes get more weight)
            total_weight = 0.0
            weighted_agreement = 0.0

            for i, v in enumerate(votes):
                # Higher index in hierarchy = longer timeframe = more weight
                weight = 1.0 + (i / max(total_votes, 1))  # 1.0 to 2.0
                total_weight += weight

                if v.supports_signal:
                    weighted_agreement += weight

            agreement_ratio = weighted_agreement / max(total_weight, 0.001)
        else:
            agreement_ratio = 1.0

        # Determine confirmation — thresholds derive from required_agreement
        # (strong = high bar, moderate = required bar, weak = partial support).
        strong_bar = max(required_agreement, min(0.80, required_agreement + 0.30))
        weak_bar = max(required_agreement * 0.4, 0.20)
        if agreement_ratio >= strong_bar:
            confirmation_level = "strong"
            score_boost = 1.3  # 30% boost
            confirmed_direction = primary_direction
        elif agreement_ratio >= required_agreement:
            confirmation_level = "moderate"
            score_boost = 1.15  # 15% boost
            confirmed_direction = primary_direction
        elif agreement_ratio >= weak_bar:
            confirmation_level = "weak"
            score_boost = 0.9  # 10% penalty
            confirmed_direction = primary_direction
        else:
            # Most timeframes disagree — likely false signal
            if primary_direction in ("buy", "sell"):
                # Check if there's a strong opposing signal
                opposing_votes = [v for v in votes
                                  if v.direction != primary_direction
                                  and v.direction != "hold"
                                  and v.strength > 0.3]
                if len(opposing_votes) >= 2:
                    confirmation_level = "opposite"
                    score_boost = 0.5
                    confirmed_direction = opposing_votes[0].direction
                else:
                    confirmation_level = "weak"
                    score_boost = 0.8
                    confirmed_direction = primary_direction
            else:
                confirmation_level = "weak"
                score_boost = 0.9
                confirmed_direction = primary_direction

        return MultiTimeframeResult(
            symbol=symbol,
            market=market,
            primary_direction=primary_direction,
            confirmed_direction=confirmed_direction,
            confirmation_level=confirmation_level,
            timeframe_votes=votes,
            agreement_ratio=agreement_ratio,
            score_boost=score_boost,
        )

    async def _get_timeframe_vote(
        self,
        symbol: str,
        market: str,
        timeframe: str,
        primary_direction: str,
    ) -> TimeframeVote:
        """Get the signal vote for a specific timeframe by computing trend directly.

        Uses _trend_for_timeframe which is a cheap DB query (~1 row per timeframe)
        instead of generate_all() which would generate signals for ALL symbols.
        """
        try:
            direction, strength = await self._trend_for_timeframe(
                symbol, market, timeframe
            )
            return TimeframeVote(
                timeframe=timeframe,
                direction=direction,
                score=strength * 100,
                strength=strength,
                confidence=0.6,
                supports_signal=(direction == primary_direction),
            )
        except Exception as e:
            logger.debug("Could not get %s vote for %s: %s", timeframe, symbol, e)
            return TimeframeVote(
                timeframe=timeframe,
                direction="hold",
                score=50,
                strength=0.0,
                confidence=0.0,
                supports_signal=True,  # neutral — don't penalize
            )

    async def _trend_for_timeframe(
        self, symbol: str, market: str, timeframe: str
    ) -> tuple[str, float]:
        """Determine trend direction from price history for a given timeframe."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return "hold", 0.0

            async with async_session_factory() as session:
                table_map = {
                    "stock": "brsapi_historical_daily",
                    "gold": "brsapi_gold_coin_history",
                    "currency": "brsapi_currency_history",
                    "crypto": "brsapi_gold_currency_pro_daily_history",
                }
                table = table_map.get(market, "brsapi_historical_daily")

                tf_days = MultiMarketSignalEngine.TIMEFRAMES.get(timeframe, 5)

                r = await session.execute(text(f"""
                    SELECT price_close
                    FROM {table}
                    WHERE symbol = :symbol AND price_close > 0
                    ORDER BY date DESC
                    LIMIT {tf_days * 2 + 1}
                """), {"symbol": symbol})

                closes = [row[0] for row in r.fetchall() if row[0] > 0]
                closes.reverse()

                if len(closes) < tf_days:
                    return "hold", 0.0

                # Simple momentum
                ret = (closes[-1] - closes[-tf_days]) / max(closes[-tf_days], 0.001)
                strength = min(1.0, abs(ret) * 5)

                if ret > 0.01:
                    return "buy", strength
                elif ret < -0.01:
                    return "sell", strength
                return "hold", strength * 0.5

        except Exception as e:
            logger.debug("Could not compute trend for %s: %s", symbol, e)
            return "hold", 0.0

    async def confirm_multiple(
        self,
        signals: list[dict[str, Any]],
        required_agreement: float = 0.5,
    ) -> list[MultiTimeframeResult]:
        """Run multi-timeframe confirmation on a batch of signals."""
        results: list[MultiTimeframeResult] = []

        for signal in signals:
            result = await self.confirm_signal(
                symbol=signal.get("symbol", ""),
                market=signal.get("market", "stock"),
                primary_direction=signal.get("direction", "hold"),
                primary_timeframe=signal.get("timeframe", "daily"),
                required_agreement=required_agreement,
            )
            results.append(result)

        return results
