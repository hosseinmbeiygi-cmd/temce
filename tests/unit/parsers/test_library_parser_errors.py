"""Contract tests for library parsers' error reporting.

A valid response with zero records is ``[]``. A response we could not read is a
:class:`ParseError` — never a silent empty list, which made a sync report
``success=True`` with ``items_count=0`` for a broken upstream.
"""

from __future__ import annotations

import json

import pytest

from ingestion.parser.errors import ParseError
from ingestion.parser.library_parsers import _BaseLibParser


class DummyParser(_BaseLibParser):
    _source_name = "dummy"

    def _dispatch(self, data):
        if data.get("data_type") != "market_watch":
            return []
        now = "2026-01-01T00:00:00+00:00"
        return [self._market_snapshot(rec, now) for rec in data.get("records", [])]


async def test_invalid_json_raises_parse_error():
    with pytest.raises(ParseError) as excinfo:
        await DummyParser().parse(b"not json")

    assert excinfo.value.reason == "invalid_json"
    assert excinfo.value.source == "dummy"


async def test_empty_payload_raises_parse_error():
    with pytest.raises(ParseError) as excinfo:
        await DummyParser().parse(b"")

    assert excinfo.value.reason == "invalid_json"


async def test_html_response_raises_parse_error():
    with pytest.raises(ParseError) as excinfo:
        await DummyParser().parse(b"<html><body>Suspend.php</body></html>")

    assert excinfo.value.reason == "html_response"


async def test_html_doctype_response_raises_parse_error():
    payload = b"<!DOCTYPE html>\n<html><head><title>Suspend.php</title></head></html>"

    with pytest.raises(ParseError) as excinfo:
        await DummyParser().parse(payload)

    assert excinfo.value.reason == "html_response"


async def test_non_dict_payload_raises_parse_error():
    with pytest.raises(ParseError) as excinfo:
        await DummyParser().parse(json.dumps([1, 2, 3]).encode("utf-8"))

    assert excinfo.value.reason == "unexpected_shape"


async def test_object_without_envelope_fields_raises_parse_error():
    with pytest.raises(ParseError) as excinfo:
        await DummyParser().parse(b'{"message": "quota exhausted"}')

    assert excinfo.value.reason == "missing_required_fields"


async def test_valid_empty_records_stay_empty():
    payload = json.dumps({"data_type": "market_watch", "records": []}).encode("utf-8")

    assert await DummyParser().parse(payload) == []


async def test_valid_payload_still_dispatches_records():
    payload = json.dumps(
        {"data_type": "market_watch", "records": [{"symbol": "ABC", "lastPrice": 12.5}]}
    ).encode("utf-8")

    events = await DummyParser().parse(payload)

    assert [event.data["symbol"] for event in events] == ["ABC"]
    assert events[0].data["last_price"] == 12.5


def test_parse_error_message_carries_reason_and_source():
    exc = ParseError("html_response", "response is HTML", source="dummy")

    assert str(exc) == "dummy: html_response: response is HTML"
    assert exc.reason == "html_response"
