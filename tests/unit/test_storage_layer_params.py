"""Parameter-mapping tests for ``ingestion.storage.StorageLayer``.

The daily OHLCV writer used ``data.get("first_price") or data.get("open")``:
a legitimate ``0`` price (no trade) was silently replaced by the fallback
field. The writer must only fall back when the primary value is missing.
"""

from __future__ import annotations

from ingestion.storage import StorageLayer


class FakeDB:
    def __init__(self) -> None:
        self.query = ""
        self.params: tuple = ()

    async def execute(self, query, *params):
        self.query = query
        self.params = params
        return "INSERT 0 1"


async def test_daily_ohlcv_keeps_zero_price() -> None:
    db = FakeDB()
    await StorageLayer(db).write_daily_ohlcv(
        "INS-1",
        {
            "trade_date": 20261028,
            "first_price": 0,
            "open": 1500,
            "high_price": 0,
            "high": 1600,
            "low_price": None,
            "low": 1400,
            "close_price": 0,
            "close": 1550,
            "volume": 10,
            "value": 15_000,
            "trade_count": 3,
        },
    )

    instrument_id, trade_date, open_, high, low, close = db.params[:6]
    assert instrument_id == "INS-1"
    assert trade_date == 20261028
    assert open_ == 0  # explicit 0 wins over the fallback
    assert high == 0
    assert low == 1400  # None falls back
    assert close == 0
    assert "ON CONFLICT (instrument_id, trade_date) DO UPDATE" in db.query
