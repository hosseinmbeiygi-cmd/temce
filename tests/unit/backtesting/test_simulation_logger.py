from __future__ import annotations

from backtesting.observability.simulation_logger import (
    SimulationLogger,
    SimulationLogLevel,
)


class TestSimulationLogger:
    def test_log_levels(self):
        logger = SimulationLogger("test", min_level=SimulationLogLevel.DEBUG)
        logger.debug("TEST", "debug message")
        logger.info("TEST", "info message")
        logger.warning("TEST", "warning message")
        logger.error("TEST", "error message")
        logger.critical("TEST", "critical message")
        assert len(logger.entries) == 5

    def test_min_level_filtering(self):

        logger = SimulationLogger("test", min_level=SimulationLogLevel.WARNING)
        logger.debug("TEST", "debug message")
        logger.info("TEST", "info message")
        logger.warning("TEST", "warning message")
        assert len(logger.entries) == 1

    def test_log_order_rejected(self):

        logger = SimulationLogger("test")
        logger.log_order_rejected("order_1", "insufficient_balance", "IRAN123")
        entries = logger.get_errors()
        assert len(entries) == 1
        assert entries[0].category == "ORDER_REJECTED"
        assert entries[0].instrument_id == "IRAN123"

    def test_log_data_mismatch(self):

        logger = SimulationLogger("test")
        logger.log_data_mismatch("price", 100.0, None, "IRAN123")
        warnings = logger.get_warnings()
        assert len(warnings) == 1
        assert warnings[0].category == "DATA_MISMATCH"

    def test_log_calibration_issue(self):

        logger = SimulationLogger("test")
        logger.log_calibration_issue("impact_eta", 0.5, "outside expected range", "IRAN123")
        warnings = logger.get_warnings()
        assert len(warnings) == 1
        assert warnings[0].category == "CALIBRATION"

    def test_log_fill_issue(self):

        logger = SimulationLogger("test")
        logger.log_fill_issue("order_1", 500, 1000, "IRAN123")
        entries = logger.get_by_category("FILL")
        assert len(entries) == 1

    def test_log_slippage(self):

        logger = SimulationLogger("test")
        logger.log_slippage("IRAN123", 100.0, 100.5)
        entries = logger.get_by_category("SLIPPAGE")
        assert len(entries) == 1

    def test_summary(self):

        logger = SimulationLogger("test")
        logger.info("TEST", "msg1")
        logger.warning("TEST", "msg2")
        logger.error("TEST", "msg3")
        summary = logger.summary()
        assert summary["total"] == 3
        assert summary["counts"]["INFO"] == 1
        assert summary["counts"]["WARNING"] == 1
        assert summary["counts"]["ERROR"] == 1

    def test_step_tracking(self):

        logger = SimulationLogger("test")
        logger.set_step(42)
        logger.info("TEST", "step message")
        assert logger.entries[0].simulation_step == 42

    def test_clear(self):

        logger = SimulationLogger("test")
        logger.info("TEST", "msg")
        logger.clear()
        assert len(logger.entries) == 0

    def test_max_entries(self):

        logger = SimulationLogger("test", max_entries=5)
        for i in range(10):
            logger.info("TEST", f"msg {i}")
        assert len(logger.entries) == 5

    def test_handler_callback(self):

        logger = SimulationLogger("test")
        received = []

        def handler(entry):
            received.append(entry)

        logger.add_handler(handler)
        logger.info("TEST", "callback msg")
        assert len(received) == 1
