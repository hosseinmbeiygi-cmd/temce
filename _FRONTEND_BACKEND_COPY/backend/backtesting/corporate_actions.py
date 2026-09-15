from __future__ import annotations

from domain.market_data.corporate_action import ActionType, CorporateAction


class CorporateActionAdjuster:
    def adjust_prices(self, prices: list[float], actions: list[CorporateAction]) -> list[float]:
        adjusted = prices.copy()
        for action in sorted(actions, key=lambda a: str(a.date)):
            factor = action.adjustment_factor
            if factor != 1.0:
                adjusted = [p / factor for p in adjusted]
        return adjusted

    def adjust_volume(self, volume: int, action: CorporateAction) -> int:
        if action.action_type == ActionType.STOCK_SPLIT and action.ratio > 0:
            return int(volume / action.ratio)
        if action.action_type == ActionType.CAPITAL_INCREASE and action.ratio > 0:
            return int(volume * (1 + action.ratio))
        return volume
