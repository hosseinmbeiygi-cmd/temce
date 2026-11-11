"""``/stocks/v2`` must publish the source timestamp it served.

Audit API-05 follow-up (master plan section 10.1).  The 9-tab Stock
Intelligence panel reads ``/stocks/v2/...`` through ``apiGet``
(``frontend/src/components/StockIntelligencePanel.tsx``) and the shared
envelope contract (``schemas/common/responses.py::ApiResponse``) promises a
``data_as_of`` wall-clock stamp so consumers can tell a fresh snapshot from a
stale cache hit.  These routes returned bare ``{success, data}`` dicts with no
``data_as_of`` at all, so freshness was unknowable.

The tests drive the real routes with a stubbed
``StockReadThroughService`` (no PostgreSQL, no Redis) and assert the stamp
each tab advertises: the newest source timestamp it actually served, or an
explicit ``None`` when the payload carries no timestamped market data.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

TAPE_TS = datetime(2026, 10, 29, 9, 30)
TAPE_ISO = TAPE_TS.isoformat()
NEWS_TS = datetime(2026, 10, 28, 12, 0)
NEWS_ISO = NEWS_TS.isoformat()


class _Rows:
    """Result stub with the three accessors the routes use."""

    def __init__(self, rows: list[Any] | None = None, scalar: Any = None) -> None:
        self._rows = list(rows or [])
        self._scalar = scalar

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def scalar(self) -> Any:
        return self._scalar


class _FakeSession:
    """Serves queued query results in call order; never touches a database."""

    def __init__(self, *results: _Rows) -> None:
        self._queue = list(results)

    async def execute(self, statement: Any, params: Any = None) -> _Rows:
        return self._queue.pop(0) if self._queue else _Rows()

    async def commit(self) -> None:
        return None


class _FakeSvc:
    def __init__(
        self,
        *,
        tape: dict[str, Any] | None = None,
        indicators: dict[str, Any] | None = None,
        signal: dict[str, Any] | None = None,
        candles: list[dict[str, Any]] | None = None,
        session: _FakeSession | None = None,
    ) -> None:
        self.session = session or _FakeSession()
        self._tape = tape
        self._indicators = indicators
        self._signal = signal
        self._candles = candles or []

    async def get_live_tape(self, symbol: str, isin: str | None = None) -> dict[str, Any]:
        if self._tape is None:
            return {"symbol": symbol, "freshness": "stale", "data_available": False}
        return dict(self._tape)

    async def get_tape_reading_matrix(self, symbol: str) -> dict[str, Any]:
        return {"tape_score": 50.0}

    async def get_indicators(self, symbol: str) -> dict[str, Any]:
        return dict(self._indicators or {})

    async def get_full_signal(self, symbol: str) -> dict[str, Any]:
        return dict(self._signal or {})

    async def _load_daily_candles(self, symbol: str, limit: int = 260) -> list[dict[str, Any]]:
        return list(self._candles)


def _install(app: Any, svc: _FakeSvc) -> None:
    from apps.api.endpoints.stocks_v2 import _svc

    app.dependency_overrides[_svc] = lambda: svc


async def test_tape_envelope_carries_quoted_at(user_client, app) -> None:
    _install(
        app,
        _FakeSvc(tape={"symbol": "AAA", "last_price": 100.0, "quoted_at": TAPE_TS, "freshness": "live"}),
    )

    response = await user_client.get("/api/v1/stocks/v2/AAA/tape")

    body = response.json()
    assert response.status_code == 200, body
    assert body["data_as_of"] == TAPE_ISO
    assert body["data"]["tape"]["last_price"] == 100.0


async def test_indicators_envelope_carries_computed_at(user_client, app) -> None:
    _install(app, _FakeSvc(indicators={"ok": True, "computed_at": TAPE_TS, "rsi_14": 55.0}))

    response = await user_client.get("/api/v1/stocks/v2/AAA/indicators")

    body = response.json()
    assert response.status_code == 200, body
    assert body["data_as_of"] == TAPE_ISO


async def test_indicators_envelope_is_explicit_none_without_timestamp(user_client, app) -> None:
    _install(app, _FakeSvc(indicators={"ok": True, "rsi_14": 55.0}))

    response = await user_client.get("/api/v1/stocks/v2/AAA/indicators")

    body = response.json()
    assert response.status_code == 200, body
    assert "data_as_of" in body
    assert body["data_as_of"] is None


async def test_signal_envelope_carries_the_tape_timestamp(user_client, app) -> None:
    _install(
        app,
        _FakeSvc(
            tape={"symbol": "AAA", "quoted_at": TAPE_TS, "freshness": "live"},
            signal={"action": "hold", "layer_scores": {}, "targets": []},
        ),
    )

    response = await user_client.get("/api/v1/stocks/v2/AAA/signal")

    body = response.json()
    assert response.status_code == 200, body
    assert body["data_as_of"] == TAPE_ISO


async def test_news_envelope_carries_the_newest_published_at(user_client, app) -> None:
    session = _FakeSession(
        _Rows(
            [
                ("older", "src", datetime(2026, 10, 20, 8, 0), "neutral", 0.0, "none"),
                ("newer", "src", NEWS_TS, "positive", 0.5, "high"),
            ]
        )
    )
    _install(app, _FakeSvc(session=session))

    response = await user_client.get("/api/v1/stocks/v2/AAA/news")

    body = response.json()
    assert response.status_code == 200, body
    assert body["data_as_of"] == NEWS_ISO
    assert len(body["data"]["news"]) == 2


async def test_codal_envelope_carries_the_newest_publish_date(user_client, app) -> None:
    session = _FakeSession(
        _Rows([("a", date(2026, 10, 27), "L1"), ("b", date(2026, 10, 25), "L2")]),
        _Rows([]),
    )
    _install(app, _FakeSvc(session=session))

    response = await user_client.get("/api/v1/stocks/v2/AAA/codal")

    body = response.json()
    assert response.status_code == 200, body
    assert body["data_as_of"] == "2026-10-27"


async def test_history_envelope_carries_the_last_candle_date(user_client, app) -> None:
    candles = [
        {"date": "2026-10-26", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "value": 1.0},
        {"date": "2026-10-28", "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "volume": 2.0, "value": 2.0},
    ]
    _install(app, _FakeSvc(candles=candles))

    response = await user_client.get("/api/v1/stocks/v2/AAA/history")

    body = response.json()
    assert response.status_code == 200, body
    assert body["data_as_of"] == "2026-10-28"
    assert len(body["data"]["candles"]) == 2


async def test_market_pulse_envelope_carries_the_macro_indicator_date(user_client, app) -> None:
    session = _FakeSession(
        _Rows([(date(2026, 10, 27), 1, 2, 3, "eroding", 1.0, 2.0)]),
        _Rows([]),
        _Rows([]),
    )
    _install(app, _FakeSvc(session=session))

    response = await user_client.get("/api/v1/stocks/v2/market-pulse")

    body = response.json()
    assert response.status_code == 200, body
    assert body["data_as_of"] == "2026-10-27"


async def test_peers_envelope_publishes_an_explicit_as_of_key(user_client, app) -> None:
    session = _FakeSession(_Rows([("IndustryA",)]), _Rows([("AAA", "Name", 1.0, 1.0, 0.5, 1e9, 10, 1, 1, 2, 3, 100, 200)]))
    _install(app, _FakeSvc(session=session))

    response = await user_client.get("/api/v1/stocks/v2/AAA/peers")

    body = response.json()
    assert response.status_code == 200, body
    assert "data_as_of" in body


async def test_dossier_envelope_publishes_an_explicit_as_of_key(user_client, app) -> None:
    session = _FakeSession(
        _Rows([("AAA", "Name", "ISIN", "Ind", "Main", "open", 1000, 25.0)]),
        _Rows([]),
        _Rows([]),
    )
    _install(app, _FakeSvc(session=session))

    response = await user_client.get("/api/v1/stocks/v2/AAA/dossier")

    body = response.json()
    assert response.status_code == 200, body
    assert "data_as_of" in body


async def test_volume_profile_envelope_publishes_an_explicit_as_of_key(user_client, app) -> None:
    _install(app, _FakeSvc(session=_FakeSession(_Rows([(100.0, 10.0), (110.0, 20.0)]))))

    response = await user_client.get("/api/v1/stocks/v2/AAA/volume-profile")

    body = response.json()
    assert response.status_code == 200, body
    assert "data_as_of" in body


async def test_history_csv_exports_the_data_as_of_header(user_client, app) -> None:
    """The CSV download is a StreamingResponse, not an envelope.

    It still has to publish the served snapshot's date, so the header is the
    only place the freshness contract can live on this route.
    """
    _install(
        app,
        _FakeSvc(
            candles=[
                {"date": "2026-10-26", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "value": 1.0},
                {"date": "2026-10-28", "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "volume": 2.0, "value": 2.0},
            ]
        ),
    )

    response = await user_client.get("/api/v1/stocks/v2/AAA/history/export.csv")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["x-data-as-of"] == "2026-10-28"
    lines = response.text.strip().splitlines()
    assert lines[0] == "date,open,high,low,close,volume,value"
    assert lines[-1].startswith("2026-10-28,")


async def test_history_csv_omits_the_header_when_there_is_no_data(user_client, app) -> None:
    _install(app, _FakeSvc(candles=[]))

    response = await user_client.get("/api/v1/stocks/v2/AAA/history/export.csv")

    assert response.status_code == 200, response.text
    assert "x-data-as-of" not in response.headers
