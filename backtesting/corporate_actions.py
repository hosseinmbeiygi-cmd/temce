from __future__ import annotations

from datetime import date
from typing import Any

from domain.market_data.corporate_action import CorporateAction


class CorporateActionAdjuster:
    def adjust_volume(self, volume: int, action: CorporateAction) -> int:
        if action.action_type == "stock_split" and action.ratio > 0:
            return int(volume / action.ratio)
        if action.action_type == "capital_increase" and action.ratio > 0:
            return int(volume * (1 + action.ratio))
        return volume

    def _as_if_factor(self, action: CorporateAction) -> float:
        """Multiplier applied to pre-action prices for the 'as-if-no-action' view.

        The canonical ``CorporateAction.adjustment_factor`` already encodes the
        direction of each action (splits, reverse splits, capital increases), so
        its inverse restores the pre-action price level.
        """
        adj_factor = action.adjustment_factor
        return 1.0 / adj_factor if adj_factor else 1.0

    def adjust_prices_with_dates(
        self,
        points: list[tuple[Any, float]],
        actions: list[CorporateAction],
        *,
        as_of: Any | None = None,
    ) -> list[float]:
        """Adjust price series for corporate actions with exact dates.

        'As-if-no-action' methodology: prices BEFORE the action date
        are multiplied by the factor so the series shows what prices
        would have been without the corporate action.

        Cash dividends are handled by adding the dividend amount to pre-dividend
        prices (since holders receive the cash, the stock price drops by ~dividend
        on ex-date; backward adjustment restores the pre-drop price).

        Args:
            points: List of (datetime, price) tuples, oldest first.
            actions: Corporate actions to apply.
            as_of: Optional cutoff date. Only actions with date <= as_of
                   are applied. This prevents look-ahead bias by ignoring
                   future corporate actions when computing historical values.

        Returns:
            Adjusted prices (same length as input), with prices before
            the action date adjusted by the cumulative factor.
        """
        if not points:
            return []

        if not actions:
            return [p for _, p in points]

        # Chronological order. Undated actions cannot gate any point, so drop
        # them up front (also keeps the sort key non-Optional for type checkers).
        dated_actions = [a for a in actions if a.date is not None]
        sorted_actions = sorted(dated_actions, key=lambda a: a.date or date.min)

        # Filter actions by as_of date if provided
        if as_of is not None:
            as_of_date = as_of.date() if hasattr(as_of, "date") else as_of
            sorted_actions = [
                a for a in sorted_actions if a.date is not None and a.date <= as_of_date
            ]

        # Separate cash dividends from other actions
        cash_dividends = [a for a in sorted_actions if a.action_type == "cash_dividend"]
        other_actions = [a for a in sorted_actions if a.action_type != "cash_dividend"]

        # (effective date, as-if multiplier) for non-dividend actions
        schedule = [
            (a.date, self._as_if_factor(a)) for a in other_actions if a.date is not None
        ]

        # Compute cumulative factor at each point: a point is adjusted by every
        # action that occurs AFTER it.
        adjusted: list[float] = []
        for dt, price in points:
            point_date = dt.date() if hasattr(dt, "date") else dt
            cum_factor = 1.0
            dividend_adjustment = 0.0

            # Multiplicative factors (splits, capital increases)
            for action_date, factor in schedule:
                if action_date is not None and action_date > point_date:
                    cum_factor *= factor

            # Additive cash dividends
            for div in cash_dividends:
                if div.date is not None and div.date > point_date and div.value > 0:
                    dividend_adjustment += div.value

            adjusted.append(price * cum_factor + dividend_adjustment)

        return adjusted
