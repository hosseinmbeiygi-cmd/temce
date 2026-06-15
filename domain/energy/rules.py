from __future__ import annotations

from domain.energy.entities import EnergyInstrument
from domain.energy.sessions import TradingSession


def validate_energy_price(price: float) -> bool:
    return price >= 0


def validate_volume(volume: float) -> bool:
    return volume >= 0


def is_session_open(session: TradingSession) -> bool:
    return session.status == "open"


def is_instrument_active(instrument: EnergyInstrument) -> bool:
    return instrument.is_active


def can_trade(instrument: EnergyInstrument, session: TradingSession) -> bool:
    return instrument.is_active and session.status == "open"
