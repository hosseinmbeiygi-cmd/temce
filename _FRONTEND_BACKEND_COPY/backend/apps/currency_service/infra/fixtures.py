"""Mock currency rate fixtures with parametric jitter.

Used until real Tgju/Nobitex/Bonbast collectors are wired in.
Override at runtime with ``CURRENCY_OVERRIDE_JSON`` env var.
"""

from __future__ import annotations

import json
import os
import random
from datetime import UTC, datetime

from apps.currency_service.domain.entities import RatePair, RateSnapshot

# Stable baseline — values match the spec's worked example.
DEFAULT_RATES: dict[str, dict[str, int | float | str]] = {
    "free": {
        "buy": 614_500,
        "sell": 615_000,
        "daily_change": 1.2,
        "source": "بازار غیررسمی",
    },
    "usdt": {
        "buy": 619_000,
        "sell": 620_000,
        "daily_change": 1.4,
        "source": "نوبیتکس",
    },
    "nima": {
        "buy": 344_000,
        "sell": 345_000,
        "daily_change": 0.0,
        "source": "سامانه نیما",
    },
    "official_cbi": 315_000,
}

DEFAULT_JITTER_PCT = 0.3  # ±0.3% on every refresh


def _env_jitter() -> float:
    raw = os.getenv("CURRENCY_JITTER_PCT")
    if not raw:
        return DEFAULT_JITTER_PCT
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_JITTER_PCT


def _env_override() -> dict | None:
    raw = os.getenv("CURRENCY_OVERRIDE_JSON")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _jitter_price(base: int, pct: float, factor: float | None = None) -> int:
    """Random multiplicative jitter inside ±pct%.

    Pass ``factor`` to share jitter across buy/sell of the same venue so
    the spread direction stays sane.
    """
    if pct <= 0:
        return base
    f = factor if factor is not None else 1.0 + random.uniform(-pct / 100.0, pct / 100.0)
    return int(round(base * f))


def _jitter_change(base: float, abs_pct: float = 0.5) -> float:
    return round(base + random.uniform(-abs_pct, abs_pct), 2)


def load_fixture_snapshot() -> RateSnapshot:
    """Build a RateSnapshot with optional override and jitter."""
    pct = _env_jitter()
    base = _env_override() or DEFAULT_RATES

    free_raw = base["free"]
    usdt_raw = base["usdt"]
    nima_raw = base["nima"]
    cbi = int(base["official_cbi"])

    # Shared jitter factor per venue so buy ≤ sell stays intact.
    free_factor = 1.0 + random.uniform(-pct / 100.0, pct / 100.0) if pct > 0 else 1.0
    usdt_factor = 1.0 + random.uniform(-pct / 100.0, pct / 100.0) if pct > 0 else 1.0
    nima_factor = 1.0 + random.uniform(-pct / 100.0, pct / 100.0) if pct > 0 else 1.0

    free = RatePair(
        name="دلار بازار آزاد",
        source=str(free_raw["source"]),
        buy_price=_jitter_price(int(free_raw["buy"]), pct, free_factor),
        sell_price=_jitter_price(int(free_raw["sell"]), pct, free_factor),
        daily_change_pct=_jitter_change(float(free_raw["daily_change"])),
    )
    usdt = RatePair(
        name="تتر (USDT)",
        source=str(usdt_raw["source"]),
        buy_price=_jitter_price(int(usdt_raw["buy"]), pct, usdt_factor),
        sell_price=_jitter_price(int(usdt_raw["sell"]), pct, usdt_factor),
        daily_change_pct=_jitter_change(float(usdt_raw["daily_change"])),
    )
    nima = RatePair(
        name="حواله نیما",
        source=str(nima_raw["source"]),
        buy_price=_jitter_price(int(nima_raw["buy"]), pct, nima_factor),
        sell_price=_jitter_price(int(nima_raw["sell"]), pct, nima_factor),
        daily_change_pct=_jitter_change(float(nima_raw["daily_change"]), 0.1),
    )

    return RateSnapshot(
        timestamp=datetime.now(tz=UTC),
        free=free,
        usdt=usdt,
        nima=nima,
        official_cbi=cbi,
    )
