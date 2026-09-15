from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExposureManager:
    max_single_position_pct: float = 10.0
    max_sector_pct: float = 30.0
    max_leverage: float = 1.0

    def check_position_exposure(self, position_value: float, total_capital: float) -> bool:
        if total_capital <= 0:
            return False
        pct = (position_value / total_capital) * 100
        return pct <= self.max_single_position_pct

    def check_sector_exposure(self, sector_value: float, total_capital: float) -> bool:
        if total_capital <= 0:
            return False
        pct = (sector_value / total_capital) * 100
        return pct <= self.max_sector_pct

    def check_leverage(self, gross_exposure: float, total_capital: float) -> bool:
        if total_capital <= 0:
            return False
        return (gross_exposure / total_capital) <= self.max_leverage
