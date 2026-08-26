"""Unit tests for core.logging.SafeStreamHandler encoding safety.

Regression for the \"--- Logging error ---\" spam seen when running the API on
Windows: the stdlib StreamHandler.emit swallows UnicodeEncodeError internally
and routes it to handleError(), printing a traceback per failed record instead
of letting SafeStreamHandler degrade gracefully.

These tests use a real cp1252-encoded stream so non-ASCII writes actually
raise UnicodeEncodeError, reproducing the production condition.
"""

from __future__ import annotations

import io
import logging

from core.logging import SafeStreamHandler


def _make_logger() -> tuple[logging.Logger, io.TextIOWrapper]:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    handler = SafeStreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("test.safe_handler")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger, stream


def _out(stream: io.TextIOWrapper) -> str:
    return stream.buffer.getvalue().decode("cp1252", errors="replace")


def test_ascii_message_written_normally():
    logger, stream = _make_logger()
    logger.info("hello world")
    assert "hello world" in _out(stream)


def test_unencodable_message_replaced_gracefully():
    logger, stream = _make_logger()
    # '→' and Persian are not representable in cp1252
    logger.info("سیگنال → test")
    out = _out(stream)
    assert "[TEXT ENCODING ERROR]" in out
    assert "→" not in out


def test_exception_with_unencodable_text_dropped_silently():
    """logger.exception with Persian/→ text must NOT trigger handleError."""

    logger, stream = _make_logger()
    try:
        raise ValueError("خطای فارسی → boom")
    except Exception:
        logger.exception("Failed to sync fund %s", "فولاد")
    # No output at all (dropped), and crucially no "--- Logging error ---"
    assert _out(stream) == ""


def test_exception_with_ascii_text_written():
    logger, stream = _make_logger()
    try:
        raise ValueError("ascii error")
    except Exception:
        logger.exception("failed %s", "x")
    out = _out(stream)
    assert "failed x" in out
    assert "ValueError" in out or "Traceback" in out
