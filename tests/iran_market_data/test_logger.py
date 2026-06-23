from __future__ import annotations

import io
import logging

from iran_market_data.app.utils.logger import setup_logger


class TestLogger:
    """Tests for setup_logger function."""

    def test_setup_logger_default(self) -> None:
        """Default logger should be created with correct name."""
        logger = setup_logger()
        assert logger.name == "iran_market_data"
        assert logger.level == logging.INFO

    def test_setup_logger_custom_name(self) -> None:
        """Custom logger name should be used."""
        logger = setup_logger("custom_logger")
        assert logger.name == "custom_logger"

    def test_setup_logger_custom_level(self) -> None:
        """Custom log level should be respected."""
        logger = setup_logger("test", "DEBUG")
        assert logger.level == logging.DEBUG

    def test_setup_logger_invalid_level(self) -> None:
        """Invalid level should default to INFO."""
        logger = setup_logger("test", "INVALID_LEVEL")
        assert logger.level == logging.INFO

    def test_setup_logger_adds_handler(self) -> None:
        """Logger should have at least one handler."""
        logger = setup_logger("test_handler")
        assert len(logger.handlers) >= 1

    def test_setup_logger_handler_is_streamhandler(self) -> None:
        """Handler should be a StreamHandler writing to stdout."""
        logger = setup_logger("test_stream")
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)

    def test_setup_logger_reentrant(self) -> None:
        """Calling setup_logger multiple times should not add duplicate handlers."""
        logger1 = setup_logger("reentrant_test")
        handler_count = len(logger1.handlers)

        logger2 = setup_logger("reentrant_test")
        assert len(logger2.handlers) == handler_count

    def test_logger_outputs_message(self) -> None:
        """Logger should actually output messages."""
        logger = setup_logger("output_test", "DEBUG")

        # Capture output
        handler = logger.handlers[0]
        stream = io.StringIO()
        old_stream = handler.stream
        handler.stream = stream

        try:
            logger.info("Hello, test!")
            output = stream.getvalue()
            assert "Hello, test!" in output
            assert "INFO" in output
        finally:
            handler.stream = old_stream

