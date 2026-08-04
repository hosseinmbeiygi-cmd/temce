"""Unit tests for MultiMarketSignalEngine's MarketSignal.to_standard().

Tests the 7-field standard signal schema (symbol, side, entry_price,
stop_loss, take_profit, confidence, timestamp) and its Persian
price-string parsing — pure functions, no DB / async I/O.
"""

from __future__ import annotations

from services.multi_market_signal_engine import MarketSignal, _extract_price


def _signal(**overrides):
    kwargs = {
        "symbol": "فولاد",
        "name": "فولاد مبارکه",
        "market": "stock",
        "direction": "buy",
        "timeframe": "daily",
        "entry_zone": "محدوده ورود: ۹۸۰,۰۰۰ تا ۱,۰۰۰,۰۰۰ ریال",
        "stop_loss": "۹۷۵,۰۰۰ ریال (کاهش ۵.۰٪)",
        "targets": "هدف اول: ۱,۰۵۰,۰۰۰ | هدف دوم: ۱,۱۰۰,۰۰۰",
        "risk_reward": "۱ به ۲",
        "price": 1_000_000.0,
        "change_pct": 2.5,
        "score": 75.0,
        "strength": 0.65,
        "confidence": 0.72,
        "source": "smart_money_technical",
        "created_at": "2024-01-01T00:00:00",
        **overrides,
    }
    return MarketSignal(**kwargs)


class TestMarketSignalToStandard:
    """Test MarketSignal.to_standard() output schema."""

    def test_contains_exactly_7_standard_fields(self):
        sig = _signal()
        std = sig.to_standard()
        assert set(std.keys()) == {
            "symbol", "side", "entry_price", "stop_loss",
            "take_profit", "confidence", "timestamp",
        }

    def test_standard_field_values(self):
        sig = _signal()
        std = sig.to_standard()
        assert std["symbol"] == "فولاد"
        assert std["side"] == "buy"
        assert std["entry_price"] == 1_000_000.0      # uses numeric price
        assert std["stop_loss"] == 975_000.0          # parsed from Persian string
        assert std["take_profit"] == 1_050_000.0      # first target parsed
        assert std["confidence"] == 0.72
        assert std["timestamp"] == "2024-01-01T00:00:00"

    def test_entry_price_falls_back_to_entry_zone_when_price_zero(self):
        sig = _signal(price=0.0)
        std = sig.to_standard()
        assert std["entry_price"] == 980_000.0  # first number in entry_zone

    def test_side_maps_sell_direction(self):
        std = _signal(direction="sell").to_standard()
        assert std["side"] == "sell"

    def test_unparseable_stop_loss_returns_none(self):
        sig = _signal(stop_loss="پریمیوم صفر (از دست دادن کل پریمیوم)")
        assert sig.to_standard()["stop_loss"] is None

    def test_confidence_rounded_to_4_decimals(self):
        std = _signal(confidence=0.72654321).to_standard()
        assert std["confidence"] == 0.7265

    def test_timestamp_falls_back_to_now_when_empty(self):
        sig = _signal(created_at="")
        ts = sig.to_standard()["timestamp"]
        assert ts  # non-empty ISO timestamp


class TestExtractPrice:
    """Test the _extract_price helper used by to_standard()."""

    def test_plain_number(self):
        assert _extract_price("95") == 95.0

    def test_persian_digits_with_thousands_separator(self):
        assert _extract_price("۹۷۵,۰۰۰ ریال") == 975_000.0

    def test_latin_digits_with_thousands_separator(self):
        assert _extract_price("1,050,000 ریال") == 1_050_000.0

    def test_decimal_prices(self):
        assert _extract_price("$1,234.56") == 1234.56

    def test_negative_number(self):
        assert _extract_price("-3.5%") == -3.5

    def test_million_suffix_from_fmt_price(self):
        # _fmt_price emits "1.1M" for prices >= 1M — must expand, not return 1.1
        assert _extract_price("1.1M ریال") == 1_100_000.0

    def test_thousand_suffix(self):
        assert _extract_price("2.5K") == 2_500.0

    def test_first_number_wins(self):
        assert _extract_price("هدف اول: ۱۰۵ | هدف دوم: ۱۱۰") == 105.0

    def test_million_suffix_in_targets(self):
        sig = _signal(targets="هدف اول: 1.1M | هدف دوم: 1.2M")
        assert sig.to_standard()["take_profit"] == 1_100_000.0

    def test_no_number_returns_none(self):
        assert _extract_price("پریمیوم صفر") is None

    def test_empty_string_returns_none(self):
        assert _extract_price("") is None
        assert _extract_price(None) is None
