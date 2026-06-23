from __future__ import annotations

import pytest

from core.config import Settings


@pytest.fixture(autouse=True)
def test_settings():
    settings = Settings(_env_file=None, database_url="sqlite:///:memory:")
    return settings


@pytest.fixture
def sample_instrument_data():
    return {
        "id": "inst_test_001",
        "symbol": "فولاد",
        "name": "فولاد مبارکه اصفهان",
        "isin": "IRO1FOLD0001",
        "market_type": "bours",
        "asset_class": "equity",
    }


@pytest.fixture
def sample_quote_data():
    return {
        "id": "q_test_001",
        "instrument_id": "inst_test_001",
        "symbol": "فولاد",
        "price_close": 15000,
        "price_open": 14900,
        "price_high": 15100,
        "price_low": 14850,
        "volume": 5000000,
        "value": 75000000000,
        "date": "2024-01-15",
        "time": "12:30:00",
    }

