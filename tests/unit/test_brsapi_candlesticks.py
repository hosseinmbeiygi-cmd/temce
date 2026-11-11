"""Unit tests for the BrsApi candlestick sync/parser fixes.

Covers:
1. ``TsetmcParser.parse_candlesticks`` derives ``gregorian_date`` /
   ``shamsi_date`` from the API's Jalali ``date`` field.
2. ``CandlestickModel`` declares the dual-date columns (matches the live DB
   created by migration 0025).
3. ``BrsApiSyncService.sync_candlesticks`` tags every record with the
   requested ``candle_type`` (previously left NULL, making the data
   invisible to ``get_candlesticks``) and forwards ``count``.
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jdatetime
import pytest

from brsapi.models import CandlestickModel
from brsapi.parsers import TsetmcParser
from brsapi.parsers.errors import BrsApiParseError
from brsapi.services.sync_service import BrsApiSyncService, SyncReport

# ── Parser: Jalali → dual dates ───────────────────────────────────────


def test_parse_candlesticks_derives_gregorian_and_shamsi():
    """``date`` is Jalali ('1404/02/23'); gregorian_date must be the real
    Gregorian date and shamsi_date the normalized YYYY-MM-DD."""
    records = TsetmcParser.parse_candlesticks({
        "candles": [
            {
                "date": "1404/02/23",
                "time": "12:28",
                "open": 7370,
                "high": 7450,
                "low": 7360,
                "close": 7400,
                "volume": 21520911,
            }
        ]
    })
    assert len(records) == 1
    rec = records[0]
    assert rec["date"] == "1404/02/23"
    assert rec["shamsi_date"] == "1404-02-23"
    # Must be a real date object — asyncpg rejects strings for DATE columns.
    assert isinstance(rec["gregorian_date"], date)
    # Round-trip: gregorian_date must map back to the same Jalali date.
    assert jdatetime.date.fromgregorian(date=rec["gregorian_date"]) == jdatetime.date(1404, 2, 23)
    # Intraday fields preserved.
    assert rec["time"] == "12:28"
    assert rec["open"] == 7370.0
    assert rec["volume"] == 21520911


def test_parse_candlesticks_accepts_dash_format_and_bad_dates():
    """Dash-separated Jalali dates work; unparseable dates degrade to None
    while empty dates (intraday bars) are stamped with today."""
    records = TsetmcParser.parse_candlesticks({"data": [{"date": "1405-05-12"}]})
    assert records[0]["shamsi_date"] == "1405-05-12"
    assert isinstance(records[0]["gregorian_date"], date)

    bad = TsetmcParser.parse_candlesticks({"candles": [{"date": "garbage"}]})
    assert bad[0]["gregorian_date"] is None


def test_parse_candlesticks_handles_plain_list_envelope():
    """The parser also tolerates a bare list payload."""
    records = TsetmcParser.parse_candlesticks([{"date": "1404/02/23", "open": 1}])
    assert len(records) == 1
    assert isinstance(records[0]["gregorian_date"], date)


def test_parse_candlesticks_unwraps_real_api_envelopes():
    """The real API wraps candles in type-specific keys
    (candle_daily_adjusted / candle_daily / candle_intraday). The parser
    must unwrap them instead of treating the whole dict as one candle
    (which previously stored a single empty row per symbol)."""
    payload = {
        "l18": "فولاد",
        "type": 3,
        "count": 4200,
        "candle_daily_adjusted": [
            {"date": "1405-05-18", "open": 2401, "high": 2401, "low": 2263, "close": 2291, "volume": 12950170918},
            {"date": "1405-05-17", "open": 2305, "high": 2374, "low": 2305, "close": 2360, "volume": 8751481850},
        ],
    }
    records = TsetmcParser.parse_candlesticks(payload)
    assert len(records) == 2
    assert records[0]["date"] == "1405-05-18"
    assert records[0]["shamsi_date"] == "1405-05-18"
    assert isinstance(records[0]["gregorian_date"], date)
    assert records[1]["close"] == 2360.0


def test_parse_candlesticks_unwraps_unadjusted_envelope():
    """type=2 uses the candle_daily key."""
    payload = {
        "l18": "فولاد",
        "type": 2,
        "count": 5,
        "candle_daily": [{"date": "1405-05-18", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}],
    }
    records = TsetmcParser.parse_candlesticks(payload)
    assert len(records) == 1
    assert records[0]["shamsi_date"] == "1405-05-18"


def test_parse_candlesticks_ignores_no_data_envelope():
    """Metadata-only payloads (no_data / error envelopes) must not produce
    a garbage zero-valued candle row."""
    for payload in ({"status": "no_data"}, {"code_http": 200, "successful": True, "message_error": None}):
        records = TsetmcParser.parse_candlesticks(payload)
        assert records == []


def test_parse_candlesticks_stamps_intraday_with_today():
    """type=1 realtime bars have no date — only time. The parser stamps
    today's Jalali date so the chart has a full timestamp and dual-date
    columns are populated."""
    payload = {
        "l18": "فولاد",
        "type": 1,
        "count": 105,
        "candle_intraday": [
            {"time": "12:28", "open": 2279, "high": 2294, "low": 2279, "close": 2284, "volume": 82058859},
            {"time": "12:26", "open": 2278, "high": 2279, "low": 2275, "close": 2276, "volume": 67969563},
        ],
    }
    records = TsetmcParser.parse_candlesticks(payload)
    assert len(records) == 2
    today = jdatetime.date.today().strftime("%Y-%m-%d")
    assert records[0]["date"] == today
    assert records[0]["shamsi_date"] == today
    assert isinstance(records[0]["gregorian_date"], date)
    assert records[0]["time"] == "12:28"


# ── Parser: BrsApiParseError contract ──────────────────────────────────


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (None, "missing_payload"),
        ("{\"candles\": []}", "unexpected_shape"),
        (42, "unexpected_shape"),
        ({"candles": "not-a-list"}, "unexpected_shape"),
        ({"candle_daily": {"date": "1404/02/23"}}, "unexpected_shape"),
        ({"unexpected": []}, "unrecognised_envelope"),
        ({"foo": 1, "bar": 2}, "unrecognised_envelope"),
    ],
)
def test_parse_candlesticks_raises_typed_error(payload, code):
    """Unreadable payloads raise BrsApiParseError carrying a stable code,
    instead of logging a warning and returning ``[]`` like a no-data day."""
    with pytest.raises(BrsApiParseError) as excinfo:
        TsetmcParser.parse_candlesticks(payload)
    assert excinfo.value.code == code


def test_parse_candlesticks_empty_response_stays_empty_not_an_error():
    """An envelope that explicitly says "no bars" is a successful empty
    parse — it must not be reported as malformed data."""
    assert TsetmcParser.parse_candlesticks({}) == []
    assert TsetmcParser.parse_candlesticks({"status": "no_data"}) == []
    assert TsetmcParser.parse_candlesticks({"candles": []}) == []
    assert TsetmcParser.parse_candlesticks({"l18": "فولاد", "type": 3, "count": 0}) == []


# ── Model: dual-date columns declared ─────────────────────────────────


def test_candlestick_model_has_dual_date_columns():
    cols = CandlestickModel.__table__.c
    assert "gregorian_date" in cols
    assert "shamsi_date" in cols
    assert cols.gregorian_date.type.python_type is date


# ── Sync: candle_type tagging + count param ───────────────────────────


async def test_sync_candlesticks_tags_candle_type_and_forward_params():
    """Records must carry symbol, ins_id AND candle_type; params must
    include type + count."""
    svc = BrsApiSyncService(session=AsyncMock())
    svc._lookup_ins_id = AsyncMock(return_value="10001")

    captured: dict = {}

    async def _fake_sync(**kwargs):
        captured.update(kwargs)
        return SyncReport(endpoint="/Tsetmc/Candlestick.php", success=True, items_count=1)

    svc.sync = _fake_sync  # type: ignore[method-assign]

    report = await svc.sync_candlesticks(
        svc._session, "فولاد", candle_type="2", count=120
    )
    assert report.success
    assert captured["params"] == {"l18": "فولاد", "type": "2", "count": "120"}

    records = captured["parser"]({
        "candles": [{"date": "1404/02/23", "open": 1, "high": 2, "low": 0.5, "close": 1.5}]
    })
    assert len(records) == 1
    assert records[0]["symbol"] == "فولاد"
    assert records[0]["ins_id"] == "10001"
    assert records[0]["candle_type"] == "2"
    assert records[0]["gregorian_date"] is not None


async def test_sync_candlesticks_omits_count_when_none():
    """count=None must not add a count param (API default = full series)."""
    svc = BrsApiSyncService(session=AsyncMock())
    svc._lookup_ins_id = AsyncMock(return_value=None)

    captured: dict = {}

    async def _fake_sync(**kwargs):
        captured.update(kwargs)
        return SyncReport(endpoint="/Tsetmc/Candlestick.php", success=True)

    svc.sync = _fake_sync  # type: ignore[method-assign]

    await svc.sync_candlesticks(svc._session, "فولاد", candle_type="3")
    assert captured["params"] == {"l18": "فولاد", "type": "3"}


# ── Sync: malformed payload → parse_error, code preserved ─────────────


class _EmptyResult:
    """Stand-in for a SQLAlchemy Result whose lookup found nothing."""

    def scalar_one_or_none(self):
        return None


class _FakeSession:
    """Minimal session: the ins_id lookup, the sync-log add and the commit."""

    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

    async def execute(self, *_args, **_kwargs):
        return _EmptyResult()

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class _FakeClient:
    def __init__(self, data) -> None:
        self.data = data

    async def fetch(self, endpoint, params=None, category_override=None):
        return SimpleNamespace(
            success=True,
            value=SimpleNamespace(
                endpoint=endpoint.path,
                data=self.data,
                is_empty=not self.data,
                raw_bytes=None,
                status_code=200,
                received_at=None,
            ),
        )


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"candles": "not-a-list"}, "unexpected_shape"),
        ({"unexpected": []}, "unrecognised_envelope"),
    ],
)
async def test_sync_candlesticks_malformed_payload_is_parse_error(payload, code):
    """A malformed candlestick response must fail the sync with
    ``outcome=parse_error`` and the structured code in the message — not a
    successful sync with ``items_count=0``. The code reaches both the report
    and the ``brsapi_sync_log`` row the dashboards read."""
    session = _FakeSession()
    svc = BrsApiSyncService(client=_FakeClient(payload), session=session)

    report = await svc.sync_candlesticks(session, "فولاد", candle_type="3")

    assert report.success is False
    assert report.outcome == "parse_error"
    assert report.items_count == 0
    assert f"ParseError[{code}]" in (report.error or "")

    # Only the sync-log entry was added — no candle row was written.
    assert len(session.added) == 1
    log_row = session.added[0]
    assert log_row.status == "error"
    assert log_row.outcome == "parse_error"
    assert log_row.items_count == 0
    assert f"ParseError[{code}]" in (log_row.error_message or "")
    assert session.commits == 1


async def test_sync_candlesticks_no_data_envelope_stays_empty_success():
    """The counterpart guarantee: a recognised no-data answer is a successful
    empty sync, so the parse-error path above does not swallow quiet days."""
    session = _FakeSession()
    svc = BrsApiSyncService(
        client=_FakeClient({"status": "no_data"}), session=session
    )

    report = await svc.sync_candlesticks(session, "فولاد", candle_type="3")

    assert report.success is True
    assert report.outcome == "empty"
    assert session.added[0].outcome == "empty"


async def test_sync_candlesticks_refreshes_realtime_series():
    """type=1 realtime must delete the symbol's previous bars before insert
    so repeated polls never accumulate duplicate 2-min bars."""
    session = AsyncMock()
    svc = BrsApiSyncService(session=session)
    svc._lookup_ins_id = AsyncMock(return_value=None)

    async def _fake_sync(**kwargs):
        return SyncReport(endpoint="/Tsetmc/Candlestick.php", success=True)

    svc.sync = _fake_sync  # type: ignore[method-assign]

    await svc.sync_candlesticks(session, "فولاد", candle_type="1", count=120)

    assert session.execute.await_count >= 1
    del_sql = str(session.execute.await_args_list[0].args[0])
    assert "DELETE" in del_sql.upper()
    assert "brsapi_candlesticks" in del_sql
    assert "candle_type" in del_sql
    # params forwarded correctly too
    assert session.flush.await_count >= 1
