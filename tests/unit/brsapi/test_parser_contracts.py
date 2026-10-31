"""Every BrsApi parser draws the same line between "no data" and "unreadable".

A parser that cannot read the payload raises :class:`BrsApiParseError` with a
code, so ``BrsApiSyncService`` records ``outcome="parse_error"`` instead of a
successful sync with ``items_count=0`` — and so the sync dashboards show a
code. A payload the provider legitimately answered with nothing (``{}``,
``[]``, ``{"status": "no_data"}`` or a metadata-only envelope) still parses to
an empty result.

The envelope cases matter because ``BrsApiResponse.is_empty`` only recognises
``{"status": "no_data"}``: a metadata-only envelope such as
``{"code_http": 200, "successful": true, "message_error": null}`` reaches the
parser, and must not be turned into an all-default row.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from brsapi.parsers import (
    CodalParser,
    CommodityParser,
    CurrencyParser,
    Gold24hParser,
    GoldCoinParser,
    GoldCurrencyParser,
    GoldCurrencyProParser,
    ImeParser,
    TsetmcParser,
)
from brsapi.parsers.errors import BrsApiParseError
from brsapi.services.sync_service import BrsApiSyncService

PROVIDER_ENVELOPE = {"code_http": 200, "successful": True, "message_error": None}
NO_DATA = {"status": "no_data"}

ALL_PARSERS = [
    (TsetmcParser.parse_symbol_detail, "SymbolDetail"),
    (TsetmcParser.parse_nav, "NAV"),
    (TsetmcParser.parse_index, "Index"),
    (TsetmcParser.parse_options, "Option"),
    (TsetmcParser.parse_history_price, "HistoryPrice"),
    (TsetmcParser.parse_history_real_legal, "HistoryRealLegal"),
    (CommodityParser.parse, "Commodity"),
    (GoldCoinParser.parse, "GoldCoin"),
    (GoldCoinParser.parse_history, "GoldCoinHistory"),
    (CurrencyParser.parse, "Currency"),
    (CurrencyParser.parse_24h, "Currency24h"),
    (CurrencyParser.parse_history, "CurrencyHistory"),
    (Gold24hParser.parse, "Gold24h"),
    (GoldCurrencyParser.parse_gold, "GoldCurrency/gold"),
    (GoldCurrencyParser.parse_crypto, "GoldCurrency/crypto"),
    (GoldCurrencyProParser.parse_gold, "Pro/gold"),
    (GoldCurrencyProParser.parse_history_24h, "Pro/history_24h"),
    (GoldCurrencyProParser.parse_daily_history, "Pro/history_daily"),
    (ImeParser.parse_futures, "IME"),
    (ImeParser.parse_certificates, "IME"),
    (CodalParser.parse_announcements_only, "Codal"),
]


# ── Every parser: None is a missing payload, never an empty success ─────────


@pytest.mark.parametrize(("parser", "label"), ALL_PARSERS, ids=[x[1] for x in ALL_PARSERS])
def test_none_payload_is_missing_payload(parser, label):
    with pytest.raises(BrsApiParseError) as excinfo:
        parser(None)
    assert excinfo.value.code == "missing_payload"


@pytest.mark.parametrize(("parser", "label"), ALL_PARSERS, ids=[x[1] for x in ALL_PARSERS])
def test_no_data_envelopes_stay_empty(parser, label):
    """A provider answer without rows is not an error."""
    result = parser(NO_DATA)
    assert (result or []) == []


# ── TSETMC: single-record and dict-or-list shapes ──────────────────────────


def test_symbol_detail_rejects_scalars_and_unknown_envelopes():
    with pytest.raises(BrsApiParseError) as scalar:
        TsetmcParser.parse_symbol_detail("garbage")
    assert scalar.value.code == "unexpected_shape"

    with pytest.raises(BrsApiParseError) as envelope:
        TsetmcParser.parse_symbol_detail({"foo": 1})
    assert envelope.value.code == "unrecognised_envelope"


def test_symbol_detail_metadata_envelope_is_not_a_record():
    """The envelope must not be stored as a detail row with empty fields."""
    assert TsetmcParser.parse_symbol_detail(PROVIDER_ENVELOPE) is None
    assert TsetmcParser.parse_symbol_detail({}) is None


def test_nav_rejects_scalars_and_unknown_envelopes():
    with pytest.raises(BrsApiParseError) as scalar:
        TsetmcParser.parse_nav(3)
    assert scalar.value.code == "unexpected_shape"

    with pytest.raises(BrsApiParseError) as envelope:
        TsetmcParser.parse_nav({"foo": 1})
    assert envelope.value.code == "unrecognised_envelope"

    # A metadata envelope must not become a zero-valued NAV snapshot.
    assert TsetmcParser.parse_nav(PROVIDER_ENVELOPE) is None


def test_index_rejects_unknown_envelopes_but_accepts_a_single_index():
    with pytest.raises(BrsApiParseError) as envelope:
        TsetmcParser.parse_index({"foo": 1})
    assert envelope.value.code == "unrecognised_envelope"

    assert TsetmcParser.parse_index(PROVIDER_ENVELOPE) == []
    single = TsetmcParser.parse_index({"index": 1.0})
    assert len(single) == 1


def test_history_parsers_reject_scalars():
    for parser in (TsetmcParser.parse_history_price, TsetmcParser.parse_history_real_legal):
        with pytest.raises(BrsApiParseError) as excinfo:
            parser("garbage")
        assert excinfo.value.code == "unexpected_shape"


# ── Commodity family ───────────────────────────────────────────────────────


def test_commodity_rejects_unknown_envelope_and_keeps_empty_category():
    with pytest.raises(BrsApiParseError) as envelope:
        CommodityParser.parse({"foo": 1})
    assert envelope.value.code == "unrecognised_envelope"

    assert CommodityParser.parse({"metal_precious": []}) == []
    assert CommodityParser.parse(PROVIDER_ENVELOPE) == []


def test_gold_coin_and_currency_reject_unknown_envelopes():
    for parser in (GoldCoinParser.parse, CurrencyParser.parse, CurrencyParser.parse_24h, Gold24hParser.parse):
        with pytest.raises(BrsApiParseError) as excinfo:
            parser({"foo": 1})
        assert excinfo.value.code == "unrecognised_envelope"
        assert parser(PROVIDER_ENVELOPE) == []


def test_gold_currency_section_absent_is_empty_but_unknown_is_an_error():
    # The combined payload answered, just without this section.
    assert GoldCurrencyParser.parse_gold({"currency": [{"symbol": "USD"}]}) == []
    # A payload naming none of the sections is an envelope we cannot read.
    with pytest.raises(BrsApiParseError) as excinfo:
        GoldCurrencyParser.parse_gold({"foo": 1})
    assert excinfo.value.code == "unrecognised_envelope"


def test_gold_currency_history_requires_a_list():
    for parser in (GoldCoinParser.parse_history, CurrencyParser.parse_history):
        with pytest.raises(BrsApiParseError) as excinfo:
            parser({"foo": 1})
        assert excinfo.value.code == "unexpected_shape"


def test_pro_section_absent_is_empty_but_unknown_is_an_error():
    payload = {"data": {"currency": [{"symbol": "USD", "price": 1}]}}
    assert GoldCurrencyProParser.parse_section(payload, "gold") == []

    with pytest.raises(BrsApiParseError) as excinfo:
        GoldCurrencyProParser.parse_section({"data": {"foo": []}}, "gold")
    assert excinfo.value.code == "unrecognised_envelope"


def test_pro_history_requires_a_history_list():
    payload = {"data": {"foo": []}}
    for parser in (
        GoldCurrencyProParser.parse_history_24h,
        GoldCurrencyProParser.parse_daily_history,
    ):
        with pytest.raises(BrsApiParseError) as excinfo:
            parser(payload)
        assert excinfo.value.code == "unrecognised_envelope"
        assert parser(PROVIDER_ENVELOPE) == []


# ── IME: a provider envelope must not become a blank contract ──────────────


def test_ime_envelope_does_not_fabricate_a_contract_row():
    assert ImeParser.parse_futures(PROVIDER_ENVELOPE) == []
    with pytest.raises(BrsApiParseError) as excinfo:
        ImeParser.parse_futures({"unexpected": 1})
    assert excinfo.value.code == "unrecognised_envelope"


def test_ime_single_contract_object_still_parses():
    records = ImeParser.parse_futures({"contract_code": "F-1", "pl": 10})
    assert len(records) == 1
    assert records[0]["contract_code"] == "F-1"


# ── Codal ──────────────────────────────────────────────────────────────────


def test_codal_rejects_scalars_and_unknown_envelopes():
    with pytest.raises(BrsApiParseError) as scalar:
        CodalParser.parse("garbage")
    assert scalar.value.code == "unexpected_shape"

    with pytest.raises(BrsApiParseError) as envelope:
        CodalParser.parse({"count_announcement": 0, "count_page": 0})
    assert envelope.value.code == "unrecognised_envelope"


def test_codal_no_data_is_an_empty_page():
    page = CodalParser.parse(NO_DATA)
    assert page == {"count_announcement": 0, "count_page": 0, "announcements": []}


def test_codal_non_list_announcements_is_a_shape_error():
    with pytest.raises(BrsApiParseError) as excinfo:
        CodalParser.parse({"announcement": {"title": "x"}})
    assert excinfo.value.code == "unexpected_shape"


# ── Sync: the Codal page parse error is recorded, not raised ───────────────


class _FakeSession:
    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0

    def add(self, obj) -> None:
        self.added.append(obj)

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


async def test_sync_codal_records_parse_error_with_code():
    session = _FakeSession()
    svc = BrsApiSyncService(client=_FakeClient({"unexpected": 1}), session=session)

    report = await svc.sync_codal(session)

    assert report.success is False
    assert report.outcome == "parse_error"
    assert "ParseError[unrecognised_envelope]" in (report.error or "")

    log_row = session.added[-1]
    assert log_row.status == "error"
    assert log_row.outcome == "parse_error"
    assert "ParseError[unrecognised_envelope]" in (log_row.error_message or "")


async def test_sync_codal_no_data_page_is_empty_not_failed():
    session = _FakeSession()
    svc = BrsApiSyncService(client=_FakeClient(NO_DATA), session=session)

    report = await svc.sync_codal(session)

    assert report.success is True
    assert report.outcome == "empty"
