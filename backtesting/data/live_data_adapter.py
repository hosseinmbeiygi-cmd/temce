from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from core.time import now_utc


class DataSource(Protocol):
    async def fetch(self, instrument_id: str, start: datetime, end: datetime) -> list[dict[str, Any]]: ...

    async def subscribe(self, instrument_id: str, callback: Any) -> None: ...

    async def unsubscribe(self, instrument_id: str) -> None: ...


@dataclass
class LiveDataConfig:
    api_key: str = ""
    base_url: str = ""
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_per_second: int = 10
    cache_ttl_seconds: int = 60
    use_websocket: bool = False
    market_type: str = "tse"


@dataclass
class LiveQuote:
    instrument_id: str
    timestamp: datetime
    bid: float
    ask: float
    last_price: float
    volume: int
    bid_volume: int = 0
    ask_volume: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    change_pct: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LiveTrade:
    instrument_id: str
    timestamp: datetime
    price: float
    volume: int
    side: str = ""
    trade_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class LiveDataAdapter(ABC):
    def __init__(self, config: LiveDataConfig | None = None) -> None:
        self._config = config or LiveDataConfig()
        self._cache: dict[str, tuple[Any, float]] = {}
        self._subscriptions: dict[str, list[Any]] = {}

    @property
    def config(self) -> LiveDataConfig:
        return self._config

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def fetch_historical(
        self,
        instrument_id: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def fetch_quote(self, instrument_id: str) -> LiveQuote: ...

    @abstractmethod
    async def fetch_trades(self, instrument_id: str, limit: int = 100) -> list[LiveTrade]: ...

    @abstractmethod
    async def fetch_orderbook(self, instrument_id: str) -> dict[str, Any]: ...

    async def subscribe_quotes(self, instrument_id: str, callback: Any) -> None:
        if instrument_id not in self._subscriptions:
            self._subscriptions[instrument_id] = []
        self._subscriptions[instrument_id].append(callback)

    async def unsubscribe_quotes(self, instrument_id: str, callback: Any | None = None) -> None:
        if instrument_id in self._subscriptions:
            if callback is None:
                del self._subscriptions[instrument_id]
            else:
                self._subscriptions[instrument_id] = [cb for cb in self._subscriptions[instrument_id] if cb is not callback]
                if not self._subscriptions[instrument_id]:
                    del self._subscriptions[instrument_id]

    def get_subscribed_instruments(self) -> list[str]:
        return list(self._subscriptions.keys())

    def clear_cache(self) -> None:
        self._cache.clear()


class TSEWebServiceAdapter(LiveDataAdapter):
    def __init__(self, config: LiveDataConfig | None = None) -> None:
        super().__init__(config)
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def fetch_historical(
        self,
        instrument_id: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        return [
            {
                "instrument_id": instrument_id,
                "date": start_date.isoformat(),
                "open": 0.0,
                "high": 0.0,
                "low": 0.0,
                "close": 0.0,
                "volume": 0,
            }
        ]

    async def fetch_quote(self, instrument_id: str) -> LiveQuote:
        return LiveQuote(
            instrument_id=instrument_id,
            timestamp=now_utc(),
            bid=0.0,
            ask=0.0,
            last_price=0.0,
            volume=0,
        )

    async def fetch_trades(self, instrument_id: str, limit: int = 100) -> list[LiveTrade]:
        return []

    async def fetch_orderbook(self, instrument_id: str) -> dict[str, Any]:
        return {"bids": [], "asks": []}


class BrsApiAdapter(LiveDataAdapter):
    def __init__(self, config: LiveDataConfig | None = None) -> None:
        super().__init__(config)
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def fetch_historical(
        self,
        instrument_id: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        return []

    async def fetch_quote(self, instrument_id: str) -> LiveQuote:
        return LiveQuote(
            instrument_id=instrument_id,
            timestamp=now_utc(),
            bid=0.0,
            ask=0.0,
            last_price=0.0,
            volume=0,
        )

    async def fetch_trades(self, instrument_id: str, limit: int = 100) -> list[LiveTrade]:
        return []

    async def fetch_orderbook(self, instrument_id: str) -> dict[str, Any]:
        return {"bids": [], "asks": []}


class LiveDataAdapterFactory:
    @staticmethod
    def create(adapter_type: str, config: LiveDataConfig | None = None) -> LiveDataAdapter:
        adapters = {
            "tse_webservice": TSEWebServiceAdapter,
            "brsapi": BrsApiAdapter,
        }
        cls = adapters.get(adapter_type)
        if cls is None:
            msg = f"Unknown adapter type: {adapter_type}"
            raise ValueError(msg)
        return cls(config)
