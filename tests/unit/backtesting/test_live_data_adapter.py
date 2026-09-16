from __future__ import annotations

import asyncio
import contextlib

from backtesting.data.live_data_adapter import (
    BrsApiAdapter,
    LiveDataAdapterFactory,
    LiveDataConfig,
    TSEWebServiceAdapter,
)


class TestLiveDataAdapter:
    def test_tse_adapter_connect(self):
        config = LiveDataConfig(api_key="test_key", base_url="https://test.com")
        adapter = TSEWebServiceAdapter(config)
        assert adapter.config.api_key == "test_key"

    def test_tse_adapter_fetch_quote_sync(self):
        adapter = TSEWebServiceAdapter()
        quote = asyncio.run(adapter.fetch_quote("IRAN123"))
        assert quote.instrument_id == "IRAN123"

    def test_factory_creates_adapter(self):
        adapter = LiveDataAdapterFactory.create("tse_webservice")
        assert adapter is not None

    def test_factory_unknown_type(self):
        with contextlib.suppress(ValueError):
            LiveDataAdapterFactory.create("unknown")
            raise AssertionError("Should have raised ValueError")

    def test_subscribe_unsubscribe_sync(self):
        adapter = TSEWebServiceAdapter()

        def callback(x):
            return x

        asyncio.run(adapter.subscribe_quotes("IRAN123", callback))
        assert "IRAN123" in adapter.get_subscribed_instruments()
        asyncio.run(adapter.unsubscribe_quotes("IRAN123", callback))
        assert "IRAN123" not in adapter.get_subscribed_instruments()

    def test_clear_cache(self):
        adapter = TSEWebServiceAdapter()
        adapter.clear_cache()

    def test_fetch_trades_default_sync(self):
        adapter = BrsApiAdapter()
        trades = asyncio.run(adapter.fetch_trades("IRAN123"))
        assert trades == []

    def test_fetch_orderbook_default_sync(self):
        adapter = TSEWebServiceAdapter()
        book = asyncio.run(adapter.fetch_orderbook("IRAN123"))
        assert "bids" in book
        assert "asks" in book

    def test_connect_disconnect(self):
        adapter = BrsApiAdapter()
        asyncio.run(adapter.connect())
        asyncio.run(adapter.disconnect())
