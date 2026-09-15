from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class ForexRate:
    from_currency: str
    to_currency: str
    rate: float
    date: date
    source: str = ""


@dataclass
class ForexPosition:
    instrument_id: str
    base_currency: str
    quantity: float
    avg_price_base: float
    pnl_base: float = 0.0


class ForexManager:
    def __init__(self, base_currency: str = "IRR") -> None:
        self._base_currency = base_currency
        self._rates: dict[str, list[ForexRate]] = {}
        self._positions: dict[str, ForexPosition] = {}
        self._conversion_log: list[dict[str, Any]] = []

    @property
    def base_currency(self) -> str:
        return self._base_currency

    def add_rate(self, rate: ForexRate) -> None:
        key = f"{rate.from_currency}_{rate.to_currency}"
        if key not in self._rates:
            self._rates[key] = []
        self._rates[key].append(rate)
        self._rates[key].sort(key=lambda r: r.date)

    def add_rates(self, rates: list[ForexRate]) -> None:
        for rate in rates:
            self.add_rate(rate)

    def get_rate(self, from_currency: str, to_currency: str, dt: date | None = None) -> float | None:
        if from_currency == to_currency:
            return 1.0
        key = f"{from_currency}_{to_currency}"
        rates = self._rates.get(key)
        if not rates:
            inverse_key = f"{to_currency}_{from_currency}"
            inverse_rates = self._rates.get(inverse_key)
            if inverse_rates:
                inverse_rate = self._get_rate_at_date(inverse_rates, dt)
                if inverse_rate is not None and inverse_rate > 0:
                    return 1.0 / inverse_rate
            return None
        return self._get_rate_at_date(rates, dt)

    def _get_rate_at_date(self, rates: list[ForexRate], dt: date | None = None) -> float | None:
        if not rates:
            return None
        if dt is None:
            return rates[-1].rate
        for r in reversed(rates):
            if r.date <= dt:
                return r.rate
        return rates[0].rate

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        dt: date | None = None,
    ) -> float:
        if from_currency == to_currency:
            return amount
        rate = self.get_rate(from_currency, to_currency, dt)
        if rate is None:
            msg = f"No rate available for {from_currency} -> {to_currency}"
            raise ValueError(msg)
        converted = amount * rate
        self._conversion_log.append(
            {
                "amount": amount,
                "from": from_currency,
                "to": to_currency,
                "rate": rate,
                "date": dt,
                "result": converted,
            }
        )
        return converted

    def convert_to_base(self, amount: float, from_currency: str, dt: date | None = None) -> float:
        return self.convert(amount, from_currency, self._base_currency, dt)

    def convert_from_base(self, amount: float, to_currency: str, dt: date | None = None) -> float:
        return self.convert(amount, self._base_currency, to_currency, dt)

    def add_position(
        self,
        instrument_id: str,
        base_currency: str,
        quantity: float,
        avg_price_base: float,
    ) -> None:
        self._positions[instrument_id] = ForexPosition(
            instrument_id=instrument_id,
            base_currency=base_currency,
            quantity=quantity,
            avg_price_base=avg_price_base,
        )

    def get_position_value_in_base(
        self, instrument_id: str, current_price_base: float, dt: date | None = None
    ) -> float:
        pos = self._positions.get(instrument_id)
        if pos is None:
            return 0.0
        return pos.quantity * current_price_base

    def get_total_pnl_in_base(self, instrument_id: str, current_price_base: float) -> float:
        pos = self._positions.get(instrument_id)
        if pos is None:
            return 0.0
        return (current_price_base - pos.avg_price_base) * pos.quantity

    def get_conversion_history(self) -> list[dict[str, Any]]:
        return list(self._conversion_log)

    def clear(self) -> None:
        self._rates.clear()
        self._positions.clear()
        self._conversion_log.clear()
