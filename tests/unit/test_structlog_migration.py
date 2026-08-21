"""Tests for core.logging structlog migration.

Verifies:
1. get_logger returns an object with stdlib-compatible API (.info, .warning, etc.)
2. JSON output includes timestamp, level, logger name, message
3. bind_context / unbind_context work correctly
4. SafeStreamHandler still handles encoding errors gracefully
5. setup_logging configures structlog processors
"""

from __future__ import annotations

import io
import json
import logging
import sys

from core.logging import (
    SafeStreamHandler,
    bind_context,
    clear_context,
    get_logger,
    setup_logging,
    unbind_context,
)


class TestGetLoggerCompat:
    """get_logger must return an object with the same API as stdlib Logger."""

    def test_returns_bound_logger(self):
        logger = get_logger("test.compat")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "exception")

    def test_same_name_returns_same_instance(self):
        l1 = get_logger("test.singleton")
        l2 = get_logger("test.singleton")
        assert l1 is l2

    def test_different_names_return_different_instances(self):
        l1 = get_logger("test.a")
        l2 = get_logger("test.b")
        assert l1 is not l2


class TestJsonOutput:
    """Verify JSON log output contains expected fields."""

    def test_json_message_includes_fields(self, capsys):
        setup_logging()
        logger = get_logger("test.json_output")
        logger.info("test_event", symbol="خودرو", count=42)

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.strip().splitlines() if ln]
        # structlog uses "event" key for the message
        found = None
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("event") == "test_event":
                    found = data
                    break
            except json.JSONDecodeError:
                continue

        assert found is not None, f"test_event not found in output: {lines[-3:]}"
        assert found["level"] == "info"
        assert "timestamp" in found

    def test_exception_includes_exc_info(self, capsys):
        setup_logging()
        logger = get_logger("test.json_exc")
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("error_occurred")

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.strip().splitlines() if ln]
        found = None
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("event") == "error_occurred":
                    found = data
                    break
            except json.JSONDecodeError:
                continue

        assert found is not None
        assert "exception" in found or "exc_info" in found


class TestContextBinding:
    """bind_context / unbind_context add fields to all subsequent logs."""

    def test_bind_adds_fields(self, capsys):
        setup_logging()
        clear_context()
        try:
            bind_context(request_id="req-123", job_name="sync")
            # Use a unique name to avoid cache hits from prior tests
            logger = get_logger("test.ctx_bind_1")
            logger.info("with_context")

            captured = capsys.readouterr()
            lines = [ln for ln in captured.out.strip().splitlines() if ln]
            for line in lines:
                try:
                    data = json.loads(line)
                    if data.get("event") == "with_context":
                        assert data.get("request_id") == "req-123"
                        assert data.get("job_name") == "sync"
                        return
                except json.JSONDecodeError:
                    continue
            raise AssertionError("with_context not found in output")
        finally:
            clear_context()

    def test_unbind_removes_fields(self, capsys):
        setup_logging()
        clear_context()
        try:
            bind_context(request_id="req-456")
            unbind_context("request_id")
            logger = get_logger("test.ctx_unbind_1")
            logger.info("after_unbind")

            captured = capsys.readouterr()
            lines = [ln for ln in captured.out.strip().splitlines() if ln]
            for line in lines:
                try:
                    data = json.loads(line)
                    if data.get("event") == "after_unbind":
                        assert "request_id" not in data
                        return
                except json.JSONDecodeError:
                    continue
            raise AssertionError("after_unbind not found in output")
        finally:
            clear_context()

    def test_clear_context_removes_all(self, capsys):
        setup_logging()
        bind_context(request_id="x", job_name="y")
        clear_context()
        logger = get_logger("test.ctx_clear_1")
        logger.info("after_clear")

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.strip().splitlines() if ln]
        for line in lines:
            try:
                data = json.loads(line)
                if data.get("event") == "after_clear":
                    assert "request_id" not in data
                    assert "job_name" not in data
                    return
            except json.JSONDecodeError:
                continue
        raise AssertionError("after_clear not found in output")


class TestSafeStreamHandler:
    """SafeStreamHandler must still handle encoding errors gracefully."""

    def _make_handler(self, encoding: str = "cp1252"):
        stream = io.TextIOWrapper(io.BytesIO(), encoding=encoding)
        handler = SafeStreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        return handler, stream

    def test_ascii_written_normally(self):
        handler, stream = self._make_handler()
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello world", (), None)
        handler.emit(record)
        assert b"hello world" in stream.buffer.getvalue()

    def test_unencodable_replaced_gracefully(self):
        handler, stream = self._make_handler()
        record = logging.LogRecord("test", logging.INFO, "", 0, "سیگنال → test", (), None)
        handler.emit(record)
        out = stream.buffer.getvalue().decode("cp1252", errors="replace")
        assert "[TEXT ENCODING ERROR]" in out

    def test_exception_with_unencodable_text_dropped(self):
        handler, stream = self._make_handler()
        try:
            raise ValueError("خطای فارسی")
        except Exception:
            record = logging.LogRecord(
                "test", logging.ERROR, "", 0, "failed %s", ("فولاد",),
                sys.exc_info(),
            )
        handler.emit(record)
        # Should be dropped silently (no output)
        assert stream.buffer.getvalue() == b""

    def test_exception_with_ascii_text_written(self):
        handler, stream = self._make_handler()
        try:
            raise ValueError("ascii error")
        except Exception:
            record = logging.LogRecord(
                "test", logging.ERROR, "", 0, "failed %s", ("x",),
                sys.exc_info(),
            )
        handler.emit(record)
        out = stream.buffer.getvalue().decode("cp1252", errors="replace")
        assert "failed x" in out
        assert "ValueError" in out
