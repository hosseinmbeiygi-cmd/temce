"""Unit tests for FxAdapter — FX price validation and normalization.

Tests the jump detection logic, price validation, normalization,
and symbol helper methods. Pure functions, no DB / async I/O.
"""

from __future__ import annotations

from ingestion.fx.fx_adapter import (
    FX_MAX_STALENESS_MIN,
    FX_MAX_SUSPECT_RATIO,
    FX_MIN_ROWS,
    FX_TRACKED_SYMBOLS,
    FxAdapter,
)

# ── Helpers ───────────────────────────────────────────────────────────


def _raw_row(symbol: str = "USD", price: float = 200500.0, **overrides) -> dict:
    """Create a raw FX price row for testing."""
    row = {
        "symbol": symbol,
        "name": "دلار",
        "price": price,
        "change_value": 100.0,
        "change_percent": 0.05,
        "unit": "IRR",
        "date": "1405-05-14",
        "time": "12:00:00",
        "time_unix": 1724745600,
        "fetched_at": "2026-08-27T08:00:00Z",
        "raw_json": "{}",
    }
    row.update(overrides)
    return row


# ── FxAdapter.validate() Tests ────────────────────────────────────────


class TestFxAdapterValidate:
    """Test FxAdapter.validate() jump detection and price validation."""

    def test_valid_prices_pass(self):
        """Normal prices within threshold should pass validation."""
        adapter = FxAdapter()
        raw = [
            _raw_row("USD", 200500),
            _raw_row("EUR", 233970),
        ]
        result = adapter.validate(raw, last_known={"USD": 200000, "EUR": 230000})

        assert len(result.clean_rows) == 2
        assert result.dropped_count == 0
        assert result.suspicious_count == 0

    def test_price_zero_is_dropped(self):
        """Price of 0 should be dropped."""
        adapter = FxAdapter()
        raw = [_raw_row("USD", 0)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 0
        assert result.dropped_count == 1

    def test_negative_price_is_dropped(self):
        """Negative price should be dropped."""
        adapter = FxAdapter()
        raw = [_raw_row("USD", -1000)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 0
        assert result.dropped_count == 1

    def test_none_price_is_dropped(self):
        """None price should be dropped."""
        adapter = FxAdapter()
        raw = [_raw_row("USD", None)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 0
        assert result.dropped_count == 1

    def test_small_jump_within_threshold(self):
        """Jump of 5% (within 8% threshold) should pass."""
        adapter = FxAdapter(max_jump_pct=0.08)
        raw = [_raw_row("USD", 210000)]
        result = adapter.validate(raw, last_known={"USD": 200000})

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 0
        assert result.clean_rows[0]["quality_flag"] == 0

    def test_jump_at_threshold_is_not_suspicious(self):
        """Jump of exactly 8% should NOT be flagged (threshold is > not >=)."""
        adapter = FxAdapter(max_jump_pct=0.08)
        raw = [_raw_row("USD", 216000)]  # exactly 8% jump from 200000
        result = adapter.validate(raw, last_known={"USD": 200000})

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 0  # exactly 8% is NOT > 8%
        assert result.clean_rows[0]["quality_flag"] == 0

    def test_large_jump_is_suspicious(self):
        """Jump of 10% should be flagged as suspicious."""
        adapter = FxAdapter(max_jump_pct=0.08)
        raw = [_raw_row("USD", 220000)]  # 10% jump from 200000
        result = adapter.validate(raw, last_known={"USD": 200000})

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 1
        assert result.clean_rows[0]["quality_flag"] == 2

    def test_downward_jump_is_suspicious(self):
        """Downward jump of 10% should also be flagged."""
        adapter = FxAdapter(max_jump_pct=0.08)
        raw = [_raw_row("USD", 180000)]  # 10% drop from 200000
        result = adapter.validate(raw, last_known={"USD": 200000})

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 1
        assert result.clean_rows[0]["quality_flag"] == 2

    def test_no_previous_price_cannot_validate_jump(self):
        """Without last_known price, jump cannot be validated — flag=0."""
        adapter = FxAdapter()
        raw = [_raw_row("USD", 200500)]
        result = adapter.validate(raw, last_known={})

        assert len(result.clean_rows) == 1
        assert result.clean_rows[0]["quality_flag"] == 0

    def test_first_occurrence_of_symbol_no_jump(self):
        """New symbol not in last_known should pass with quality_flag=0."""
        adapter = FxAdapter()
        raw = [_raw_row("NEW_SYMBOL", 100000)]
        result = adapter.validate(raw, last_known={"USD": 200000})

        assert len(result.clean_rows) == 1
        assert result.clean_rows[0]["quality_flag"] == 0

    def test_mixed_valid_and_invalid(self):
        """Mix of valid and invalid rows should handle each correctly."""
        adapter = FxAdapter()
        raw = [
            _raw_row("USD", 200500),  # valid
            _raw_row("EUR", 0),  # invalid — dropped
            _raw_row("GBP", -100),  # invalid — dropped
            _raw_row("AED", 54000),  # valid
        ]
        result = adapter.validate(raw, last_known={"USD": 200000, "EUR": 230000})

        assert len(result.clean_rows) == 2
        assert result.dropped_count == 2
        assert result.suspicious_count == 0

    def test_fetched_at_added_when_missing(self):
        """fetched_at should be added when missing."""
        adapter = FxAdapter()
        raw = [_raw_row("USD", 200500, fetched_at=None)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 1
        assert result.clean_rows[0]["fetched_at"] is not None

    def test_custom_max_jump_pct(self):
        """Custom max_jump_pct should be respected."""
        adapter = FxAdapter(max_jump_pct=0.05)  # 5% threshold
        raw = [_raw_row("USD", 209000)]  # 4.5% jump from 200000
        result = adapter.validate(raw, last_known={"USD": 200000})

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 0  # 4.5% < 5% threshold

    def test_custom_max_jump_pct_exceeded(self):
        """Jump exceeding custom threshold should be flagged."""
        adapter = FxAdapter(max_jump_pct=0.05)  # 5% threshold
        raw = [_raw_row("USD", 211000)]  # 5.5% jump from 200000
        result = adapter.validate(raw, last_known={"USD": 200000})

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 1

    def test_multiple_symbols_independent_jump_detection(self):
        """Jump detection should be independent per symbol."""
        adapter = FxAdapter(max_jump_pct=0.08)
        raw = [
            _raw_row("USD", 217000),  # 8.5% jump — suspicious
            _raw_row("EUR", 234000),  # 0.01% jump — normal
        ]
        result = adapter.validate(raw, last_known={"USD": 200000, "EUR": 233970})

        assert len(result.clean_rows) == 2
        assert result.suspicious_count == 1
        assert result.clean_rows[0]["quality_flag"] == 2  # USD suspicious
        assert result.clean_rows[1]["quality_flag"] == 0  # EUR normal

    def test_errors_list_populated(self):
        """Errors list should contain dropped row descriptions."""
        adapter = FxAdapter()
        raw = [
            _raw_row("USD", 0),
            _raw_row("EUR", -100),
        ]
        result = adapter.validate(raw)

        assert len(result.errors) == 2
        assert "USD" in result.errors[0]
        assert "EUR" in result.errors[1]


# ── FxAdapter.normalize() Tests ───────────────────────────────────────


class TestFxAdapterNormalize:
    """Test FxAdapter.normalize() output schema."""

    def test_normalize_basic_fields(self):
        """Normalized row should contain all required fields."""
        adapter = FxAdapter()
        raw = [_raw_row("USD", 200500)]
        result = adapter.validate(raw)
        normalized = adapter.normalize(result.clean_rows)

        assert len(normalized) == 1
        row = normalized[0]
        assert row["symbol"] == "USD"
        assert row["price"] == 200500
        assert row["name"] == "دلار"
        assert row["unit"] == "IRR"
        assert row["market"] == "fx"

    def test_normalize_preserves_quality_flag(self):
        """quality_flag should be preserved in normalized output."""
        adapter = FxAdapter(max_jump_pct=0.08)
        raw = [_raw_row("USD", 217000)]  # 8.5% jump — suspicious
        result = adapter.validate(raw, last_known={"USD": 200000})
        normalized = adapter.normalize(result.clean_rows)

        assert normalized[0]["quality_flag"] == 2

    def test_normalize_adds_fetched_at(self):
        """fetched_at should be set if not present."""
        adapter = FxAdapter()
        raw = [_raw_row("USD", 200500, fetched_at=None)]
        result = adapter.validate(raw)
        normalized = adapter.normalize(result.clean_rows)

        assert normalized[0]["fetched_at"] is not None

    def test_normalize_empty_input(self):
        """Empty input should return empty list."""
        adapter = FxAdapter()
        normalized = adapter.normalize([])
        assert normalized == []


# ── FxAdapter Helper Methods Tests ────────────────────────────────────


class TestFxAdapterHelpers:
    """Test FxAdapter helper methods."""

    def test_is_primary_usd(self):
        """USD should be a primary symbol."""
        adapter = FxAdapter()
        assert adapter.is_primary("USD") is True

    def test_is_primary_eur(self):
        """EUR should be a primary symbol."""
        adapter = FxAdapter()
        assert adapter.is_primary("EUR") is True

    def test_is_primary_unknown(self):
        """Unknown symbol should not be primary."""
        adapter = FxAdapter()
        assert adapter.is_primary("XYZ") is False

    def test_symbol_label_usd(self):
        """USD should have correct label."""
        adapter = FxAdapter()
        assert adapter.symbol_label("USD") == "دلار / بازار آزاد"

    def test_symbol_label_eur(self):
        """EUR should have correct label."""
        adapter = FxAdapter()
        assert adapter.symbol_label("EUR") == "یورو / بازار آزاد"

    def test_symbol_label_unknown(self):
        """Unknown symbol should return the symbol itself."""
        adapter = FxAdapter()
        assert adapter.symbol_label("XYZ") == "XYZ"

    def test_custom_primary_symbols(self):
        """Custom primary symbols should be respected."""
        adapter = FxAdapter(primary_symbols=["BTC", "ETH"])
        assert adapter.is_primary("BTC") is True
        assert adapter.is_primary("USD") is False


# ── Constants Tests ───────────────────────────────────────────────────


class TestFxConstants:
    """Test FX module constants."""

    def test_fx_tracked_symbols_is_list(self):
        """FX_TRACKED_SYMBOLS should be a list."""
        assert isinstance(FX_TRACKED_SYMBOLS, list)
        assert len(FX_TRACKED_SYMBOLS) > 0

    def test_fx_tracked_symbols_contains_usd(self):
        """FX_TRACKED_SYMBOLS should contain USD."""
        assert "USD" in FX_TRACKED_SYMBOLS

    def test_fx_min_rows_positive(self):
        """FX_MIN_ROWS should be positive."""
        assert FX_MIN_ROWS > 0

    def test_fx_max_staleness_positive(self):
        """FX_MAX_STALENESS_MIN should be positive."""
        assert FX_MAX_STALENESS_MIN > 0

    def test_fx_max_suspect_ratio_between_0_and_1(self):
        """FX_MAX_SUSPECT_RATIO should be between 0 and 1."""
        assert 0 < FX_MAX_SUSPECT_RATIO < 1
