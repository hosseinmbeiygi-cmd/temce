from __future__ import annotations

from datetime import date

from backtesting.engine.forex_manager import ForexManager, ForexRate


class TestForexManager:
    def test_initial_state(self):

        fm = ForexManager("IRR")
        assert fm.base_currency == "IRR"

    def test_add_rate(self):

        fm = ForexManager()
        rate = ForexRate(from_currency="USD", to_currency="IRR", rate=420000, date=date(2024, 1, 1))
        fm.add_rate(rate)
        assert fm.get_rate("USD", "IRR") == 420000

    def test_get_rate_same_currency(self):

        fm = ForexManager()
        assert fm.get_rate("USD", "USD") == 1.0

    def test_get_rate_nonexistent(self):

        fm = ForexManager()
        rate = fm.get_rate("USD", "EUR")
        assert rate is None

    def test_get_rate_by_date(self):

        fm = ForexManager()
        fm.add_rate(ForexRate("USD", "IRR", 400000, date(2024, 1, 1)))
        fm.add_rate(ForexRate("USD", "IRR", 420000, date(2024, 6, 1)))
        rate = fm.get_rate("USD", "IRR", date(2024, 3, 1))
        assert rate == 400000

    def test_inverse_rate(self):

        fm = ForexManager()
        fm.add_rate(ForexRate("IRR", "USD", 0.00000238, date(2024, 1, 1)))
        rate = fm.get_rate("USD", "IRR", date(2024, 1, 1))
        assert rate is not None
        assert abs(rate - 420168) < 1000

    def test_convert(self):

        fm = ForexManager()
        fm.add_rate(ForexRate("USD", "IRR", 420000, date(2024, 1, 1)))
        result = fm.convert(100, "USD", "IRR")
        assert result == 42_000_000

    def test_convert_same_currency(self):

        fm = ForexManager()
        result = fm.convert(100, "USD", "USD")
        assert result == 100

    def test_convert_no_rate_raises(self):

        fm = ForexManager()
        try:
            fm.convert(100, "USD", "EUR")
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass

    def test_convert_to_base(self):

        fm = ForexManager("IRR")
        fm.add_rate(ForexRate("USD", "IRR", 420000, date(2024, 1, 1)))
        result = fm.convert_to_base(100, "USD", date(2024, 1, 1))
        assert result == 42_000_000

    def test_add_rates_bulk(self):

        fm = ForexManager()
        rates = [
            ForexRate("USD", "IRR", 400000, date(2024, 1, 1)),
            ForexRate("USD", "IRR", 420000, date(2024, 6, 1)),
        ]
        fm.add_rates(rates)
        assert fm.get_rate("USD", "IRR", date(2024, 3, 1)) == 400000

    def test_position_tracking(self):

        fm = ForexManager()
        fm.add_position("USD_asset", "USD", 1000, 1.5)
        value = fm.get_position_value_in_base("USD_asset", 2.0)
        assert value == 2000

    def test_position_pnl(self):

        fm = ForexManager()
        fm.add_position("USD_asset", "USD", 1000, 1.5)
        pnl = fm.get_total_pnl_in_base("USD_asset", 2.0)
        assert pnl == 500

    def test_get_conversion_history(self):

        fm = ForexManager()
        fm.add_rate(ForexRate("USD", "IRR", 420000, date(2024, 1, 1)))
        fm.convert(100, "USD", "IRR")
        history = fm.get_conversion_history()
        assert len(history) == 1

    def test_clear(self):

        fm = ForexManager()
        fm.add_rate(ForexRate("USD", "IRR", 420000, date(2024, 1, 1)))
        fm.add_position("test", "USD", 100, 1.0)
        fm.clear()
        assert fm.get_rate("USD", "IRR") is None
