"""Unit tests for GoldAdapter — gold price validation and normalization."""

from __future__ import annotations

from ingestion.gold.gold_adapter import (
    GOLD_MAX_STALENESS_MIN,
    GOLD_MAX_SUSPECT_RATIO,
    GOLD_MIN_ROWS,
    GOLD_TRACKED_SYMBOLS,
    GoldAdapter,
)

# ── Helpers ───────────────────────────────────────────────────────────


def _raw_row(symbol: str = "IR_GOLD_18K", price: float = 21677400.0, **overrides) -> dict:
    """Create a raw gold price row for testing."""
    row = {
        "symbol": symbol,
        "name": "طلای ۱۸ عیار",
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


# ── GoldAdapter.validate() Tests ──────────────────────────────────────


class TestGoldAdapterValidate:
    """Test GoldAdapter.validate() price validation."""

    def test_valid_prices_pass(self):
        """Normal prices should pass validation."""
        adapter = GoldAdapter()
        raw = [
            _raw_row("IR_GOLD_18K", 21677400),
            _raw_row("IR_COIN_EMAMI", 214000000),
        ]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 2
        assert result.dropped_count == 0
        assert result.suspicious_count == 0

    def test_price_zero_is_dropped(self):
        """Price of 0 should be dropped."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", 0)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 0
        assert result.dropped_count == 1

    def test_negative_price_is_dropped(self):
        """Negative price should be dropped."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", -1000)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 0
        assert result.dropped_count == 1

    def test_none_price_is_dropped(self):
        """None price should be dropped."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", None)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 0
        assert result.dropped_count == 1

    def test_low_price_is_suspicious(self):
        """Price below 1000 should be flagged as suspicious."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", 500)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 1
        assert result.clean_rows[0]["quality_flag"] == 2

    def test_normal_price_not_suspicious(self):
        """Normal price should not be suspicious."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", 21677400)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 1
        assert result.suspicious_count == 0
        assert result.clean_rows[0]["quality_flag"] == 0

    def test_fetched_at_added_when_missing(self):
        """fetched_at should be added when missing."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", 21677400, fetched_at=None)]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 1
        assert result.clean_rows[0]["fetched_at"] is not None

    def test_mixed_valid_and_invalid(self):
        """Mix of valid and invalid rows should handle each correctly."""
        adapter = GoldAdapter()
        raw = [
            _raw_row("IR_GOLD_18K", 21677400),  # valid
            _raw_row("IR_COIN_EMAMI", 0),  # invalid — dropped
            _raw_row("IR_COIN_BAHAR", -100),  # invalid — dropped
            _raw_row("XAUUSD", 4619),  # valid
        ]
        result = adapter.validate(raw)

        assert len(result.clean_rows) == 2
        assert result.dropped_count == 2


# ── GoldAdapter.normalize() Tests ─────────────────────────────────────


class TestGoldAdapterNormalize:
    """Test GoldAdapter.normalize() output schema."""

    def test_normalize_basic_fields(self):
        """Normalized row should contain all required fields."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", 21677400)]
        result = adapter.validate(raw)
        normalized = adapter.normalize(result.clean_rows)

        assert len(normalized) == 1
        row = normalized[0]
        assert row["symbol"] == "IR_GOLD_18K"
        assert row["price"] == 21677400
        assert row["name"] == "طلای ۱۸ عیار"
        assert row["unit"] == "IRR"
        assert row["market"] == "gold"

    def test_normalize_preserves_quality_flag(self):
        """quality_flag should be preserved in normalized output."""
        adapter = GoldAdapter()
        raw = [_raw_row("IR_GOLD_18K", 500)]  # low price = suspicious
        result = adapter.validate(raw)
        normalized = adapter.normalize(result.clean_rows)

        assert normalized[0]["quality_flag"] == 2

    def test_normalize_empty_input(self):
        """Empty input should return empty list."""
        adapter = GoldAdapter()
        normalized = adapter.normalize([])
        assert normalized == []


# ── GoldAdapter Helper Methods Tests ──────────────────────────────────


class TestGoldAdapterHelpers:
    """Test GoldAdapter helper methods."""

    def test_is_primary_gold_18k(self):
        """IR_GOLD_18K should be a primary symbol."""
        adapter = GoldAdapter()
        assert adapter.is_primary("IR_GOLD_18K") is True

    def test_is_primary_xauusd(self):
        """XAUUSD should not be a primary symbol (it's a global feature)."""
        adapter = GoldAdapter()
        assert adapter.is_primary("XAUUSD") is False

    def test_is_global_feature_xauusd(self):
        """XAUUSD should be a global feature."""
        adapter = GoldAdapter()
        assert adapter.is_global_feature("XAUUSD") is True

    def test_is_global_feature_gold_18k(self):
        """IR_GOLD_18K should not be a global feature."""
        adapter = GoldAdapter()
        assert adapter.is_global_feature("IR_GOLD_18K") is False

    def test_symbol_label_gold_18k(self):
        """IR_GOLD_18K should have correct label."""
        adapter = GoldAdapter()
        assert adapter.symbol_label("IR_GOLD_18K") == "طلای ۱۸ عیار"

    def test_symbol_label_xauusd(self):
        """XAUUSD should have correct label."""
        adapter = GoldAdapter()
        assert adapter.symbol_label("XAUUSD") == "انس طلا جهانی"

    def test_symbol_label_unknown(self):
        """Unknown symbol should return the symbol itself."""
        adapter = GoldAdapter()
        assert adapter.symbol_label("XYZ") == "XYZ"


# ── Constants Tests ───────────────────────────────────────────────────


class TestGoldConstants:
    """Test gold module constants."""

    def test_gold_tracked_symbols_is_list(self):
        """GOLD_TRACKED_SYMBOLS should be a list."""
        assert isinstance(GOLD_TRACKED_SYMBOLS, list)
        assert len(GOLD_TRACKED_SYMBOLS) > 0

    def test_gold_tracked_symbols_contains_gold_18k(self):
        """GOLD_TRACKED_SYMBOLS should contain IR_GOLD_18K."""
        assert "IR_GOLD_18K" in GOLD_TRACKED_SYMBOLS

    def test_gold_min_rows_positive(self):
        """GOLD_MIN_ROWS should be positive."""
        assert GOLD_MIN_ROWS > 0

    def test_gold_max_staleness_positive(self):
        """GOLD_MAX_STALENESS_MIN should be positive."""
        assert GOLD_MAX_STALENESS_MIN > 0

    def test_gold_max_suspect_ratio_between_0_and_1(self):
        """GOLD_MAX_SUSPECT_RATIO should be between 0 and 1."""
        assert 0 < GOLD_MAX_SUSPECT_RATIO < 1
