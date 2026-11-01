"""Structured logging contract and aggregation forwarding tests."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

import core.context as ctx
from core.config import settings
from core.logging import _build_json_formatter, get_logger, setup_logging
from integrations.observability.log_aggregator import (
    RedisLogHandler,
    install_aggregation_handler,
)


@pytest.fixture(autouse=True)
def _rebind_root_handlers_after_test() -> Iterator[None]:
    """Rebind logging to the live stdout after capsys teardown.

    ``setup_logging`` captures ``sys.stdout``; pytest closes the capture buffer
    at teardown, so a later test would otherwise log to a closed file.
    """
    yield
    setup_logging()


def _json_lines(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in text.strip().splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _find(records: list[dict[str, Any]], event: str) -> dict[str, Any] | None:
    for record in records:
        if record.get("event") == event:
            return record
    return None


class _FakeRedis:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, Any], int | None]] = []
        self.fail = False

    def xadd(self, key: str, fields: dict[str, Any], maxlen: int | None = None) -> str:
        if self.fail:
            raise RuntimeError("redis down")
        self.entries.append((key, fields, maxlen))
        return "1-0"


def _aggregation_handler(fake: _FakeRedis, source: str = "worker-1") -> RedisLogHandler:
    handler = RedisLogHandler(source=source)
    handler._client = fake
    handler.setFormatter(_build_json_formatter())
    return handler


def test_stdlib_records_are_json_with_extras(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging()
    logging.getLogger("thirdparty.audit").warning(
        "third_party_event", extra={"job": "sync", "attempt": 2}
    )

    record = _find(_json_lines(capsys.readouterr().out), "third_party_event")
    assert record is not None
    assert record["level"] == "warning"
    assert record["logger"] == "thirdparty.audit"
    assert record["job"] == "sync"
    assert record["attempt"] == 2
    assert "timestamp" in record


def test_context_ids_are_injected(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging()
    ctx.set_request_id("req-1")
    ctx.set_correlation_id("corr-1")
    ctx.set_user_id("user-1")
    try:
        get_logger("test.ctx_ids_structured").info("ctx_event")
    finally:
        ctx.set_request_id("")
        ctx.set_correlation_id("")
        ctx.set_user_id("")

    record = _find(_json_lines(capsys.readouterr().out), "ctx_event")
    assert record is not None
    assert record["request_id"] == "req-1"
    assert record["correlation_id"] == "corr-1"
    assert record["user_id"] == "user-1"


def test_stdlib_style_positional_args_are_interpolated(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging()
    get_logger("test.positional_args").info("synced %d symbols", 42)

    record = _find(_json_lines(capsys.readouterr().out), "synced 42 symbols")
    assert record is not None
    assert "positional_args" not in record


def test_unknown_value_types_are_stringified(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging()
    get_logger("test.unknown_types").info(
        "decimal_event", amount=Decimal("1.50"), when=datetime(2026, 1, 1)
    )

    record = _find(_json_lines(capsys.readouterr().out), "decimal_event")
    assert record is not None
    assert record["amount"] == "1.50"
    assert "2026" in record["when"]


def test_text_mode_stays_human_readable(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "log_format", "text")
    setup_logging()
    get_logger("test.text_mode_structured").info("text_event")

    output = capsys.readouterr().out
    assert "text_event" in output
    assert _json_lines(output) == []


def test_aggregator_ships_the_json_line_with_source() -> None:
    setup_logging()
    fake = _FakeRedis()
    handler = _aggregation_handler(fake)
    logger = logging.getLogger("agg.forward")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info("agg_event", extra={"attempt": 3})

    key, fields, maxlen = fake.entries[0]
    assert key == "log-aggregator:stream"
    assert maxlen == 50_000
    payload = json.loads(fields["data"])
    assert payload["event"] == "agg_event"
    assert payload["source"] == "worker-1"
    assert payload["attempt"] == 3


def test_aggregator_adds_source_to_structlog_records() -> None:
    setup_logging()
    fake = _FakeRedis()
    handler = _aggregation_handler(fake)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        get_logger("agg.structlog_structured").info("structlog_event", attempt=4)
    finally:
        root.removeHandler(handler)

    payload = json.loads(fake.entries[0][1]["data"])
    assert payload["event"] == "structlog_event"
    assert payload["source"] == "worker-1"
    assert payload["attempt"] == 4


def test_aggregator_fallback_payload_matches_json_contract() -> None:
    fake = _FakeRedis()
    handler = RedisLogHandler(source="svc")  # no formatter attached
    handler._client = fake
    record = logging.LogRecord("fallback.logger", logging.INFO, "", 0, "fallback_event", (), None)

    handler.emit(record)

    payload = json.loads(fake.entries[0][1]["data"])
    assert payload["event"] == "fallback_event"
    assert payload["logger"] == "fallback.logger"
    assert payload["source"] == "svc"
    assert "timestamp" in payload


def test_aggregator_failure_is_counted_not_raised() -> None:
    fake = _FakeRedis()
    fake.fail = True
    handler = _aggregation_handler(fake)

    record = logging.LogRecord("agg.fail", logging.INFO, "", 0, "boom", (), None)
    handler.emit(record)

    assert handler.failures == 1
    assert handler.published == 0


def test_install_aggregation_handler_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "log_aggregation_enabled", False)
    assert install_aggregation_handler(source="svc") is None


def test_install_aggregation_handler_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "log_aggregation_enabled", True)
    root = logging.getLogger()
    handler = install_aggregation_handler(
        source="svc", formatter=_build_json_formatter()
    )
    assert handler is not None
    try:
        assert handler in root.handlers
        assert handler.formatter is not None
    finally:
        root.removeHandler(handler)
