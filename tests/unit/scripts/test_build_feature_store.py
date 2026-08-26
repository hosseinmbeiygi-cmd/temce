from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

# ── Fake session that records executed statements ──────────────────────────

class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def scalars(self):
        return self._rows

    def scalar(self):
        return self._rows[0] if self._rows else None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows if isinstance(rows, list) else [rows]

    def fetchall(self):
        return self._rows

    def scalars(self):
        return self._rows

    def scalar(self):
        return self._rows[0] if self._rows else None


class _FakeStream:
    """Mimics a streamed query result with yield_per."""
    def __init__(self, symbols):
        self._partitions = [[(s,)] for s in symbols]

    def yield_per(self, n):
        return self

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for p in self._partitions:
            yield p


class _FakeSession:
    def __init__(self, symbols=None, max_date=None):
        self._symbols = symbols or ["فولاد", "وبملت"]
        self._max_date = max_date or date(2026, 8, 10)
        self.executed = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def stream(self, stmt):
        return _FakeStream(self._symbols)

    async def execute(self, stmt, *args, **kwargs):
        self.executed.append(str(stmt))
        return _FakeResult([self._max_date])

    async def commit(self):
        self.commits += 1


class _FakeEngine:
    async def compute_all_features(self, symbol):
        return {
            "symbol": symbol,
            "features": {
                "last_price": 5000.0,
                "volume": 1_000_000,
                "trade_value": 5e9,
                "trade_count": 100,
                "rsi_14": 55.0,
                "macd_signal": 1.0,
                "sma_20": 4900.0,
                "atr_14": 80.0,
                "volume_spike": 1.5,
                "eps_ttm": 400,
                "pe_ratio": 12.0,
                "queue_status": "BUY_QUEUE",
                "queue_volume_ratio": 0.8,
                "queue_days_streak": 2,
                "queue_type_change": "NO_CHANGE",
                "distance_to_limit": 0.3,
                "final_score": 82.0,
                "final_decision": "BUY",
            },
        }


# ── Feature engine double ──────────────────────────────────────────────────

class _FakeEngine:
    async def compute_all_features(self, symbol):
        return {
            "symbol": symbol,
            "features": {
                "last_price": 5000.0,
                "volume": 1_000_000,
                "trade_value": 5e9,
                "trade_count": 100,
                "rsi_14": 55.0,
                "macd_signal": 1.0,
                "sma_20": 4900.0,
                "atr_14": 80.0,
                "volume_spike": 1.5,
                "eps_ttm": 400,
                "pe_ratio": 12.0,
                "queue_status": "BUY_QUEUE",
                "queue_volume_ratio": 0.8,
                "queue_days_streak": 2,
                "queue_type_change": "NO_CHANGE",
                "distance_to_limit": 0.3,
                "final_score": 82.0,
                "final_decision": "BUY",
            },
        }


def test_load_active_symbols_streams():
    from scripts.build_feature_store import FeatureStoreBuilder

    session = _FakeSession(symbols=["الف", "ب", "ج", "د"])
    builder = FeatureStoreBuilder()

    async def run():
        return await builder._load_active_symbols(session)

    syms = asyncio.run(run())
    assert syms == ["الف", "ب", "ج", "د"]


def test_compute_symbol_maps_features_to_columns():
    from scripts.build_feature_store import FeatureStoreBuilder

    session = _FakeSession()
    builder = FeatureStoreBuilder()

    with patch("services.feature_engine.FeatureEngine", return_value=_FakeEngine()):
        async def run():
            return await builder._compute_symbol(session, "فولاد")

        row = asyncio.run(run())

    assert row["symbol"] == "فولاد"
    assert row["trade_date"] == date(2026, 8, 10)
    assert row["price_close"] == 5000.0
    assert row["queue_status"] == "BUY_QUEUE"
    assert row["final_decision"] == "BUY"
    assert row["final_decision"] == "BUY"
    assert row["trade_date"] == date(2026, 8, 10)
    # features_json keeps the full payload
    assert row["features_json"]["final_score"] == 82.0


def test_compute_symbol_handles_no_features():
    from scripts.build_feature_store import FeatureStoreBuilder

    session = _FakeSession()
    builder = FeatureStoreBuilder()

    class _EmptyEngine:
        async def compute_all_features(self, symbol):
            return {"symbol": symbol, "features": {}}

    with patch("services.feature_engine.FeatureEngine", return_value=_EmptyEngine()):
        async def run():
            return await builder._compute_symbol(session, "فولاد")

        # features empty → returns None (no row)
        row = asyncio.run(run())
    assert row is None


def test_sanitize_row_drops_nan():

    from scripts.build_feature_store import _sanitize_row

    row = {"a": 1.0, "b": float("nan"), "c": float("inf"), "d": None, "e": {"x": float("nan"), "y": 2}}
    cleaned = _sanitize_row(row)
    assert cleaned["a"] == 1.0
    assert cleaned["b"] is None
    assert cleaned["c"] is None
    assert cleaned["d"] is None
    assert cleaned["e"]["x"] is None
    assert cleaned["e"]["y"] == 2


def test_build_all_commits_and_logs():
    from scripts.build_feature_store import FeatureStoreBuilder

    session = _FakeSession(symbols=["فولاد", "وبملت"])
    builder = FeatureStoreBuilder(symbols=["فولاد", "وبملت"], workers=2)

    async def fake_get_session():
        yield session

    def fake_factory():
        s = _FakeSession(symbols=["فولاد", "وبملت"])
        s._max_date = date(2026, 8, 10)
        return s

    with patch("scripts.build_feature_store.get_session", fake_get_session), \
         patch("scripts.build_feature_store.async_session_factory", fake_factory), \
         patch("services.feature_engine.FeatureEngine", return_value=_FakeEngine()), \
         patch.object(builder, "_save_rows", new=AsyncMock()):
        async def run():
            return await builder.build_all()

        stats = asyncio.run(run())

    assert stats["ok"] == 2
    assert stats["rows"] == 2
    assert stats["fail"] == 0
