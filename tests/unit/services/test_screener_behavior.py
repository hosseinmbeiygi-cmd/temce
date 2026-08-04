"""Unit tests for safe_row_float behavioral change in screener_service.

Verifies that returning 0.0 instead of None for falsy DB values
does not break the _apply_fundamental_filter logic.

See also: test_screener_filters.py for broader filter tests.
"""

from __future__ import annotations

from core.db_utils import safe_row_float, safe_row_str
from services.screener_service import ScreenerService

# ════════════════════════════════════════════════════════════════
# 1. safe_row_float vs old float() pattern
# ════════════════════════════════════════════════════════════════


class TestSafeRowFloatBehavior:
    """Verify safe_row_float handles None, 0, empty string, NaN, Inf correctly."""

    def test_none_value(self) -> None:
        """None in row[0] → 0.0 (not None)."""
        row = (None, None, None)
        assert safe_row_float(row, idx=0) == 0.0

    def test_zero_float(self) -> None:
        """0.0 in row → 0.0 (not None as old pattern would return)."""
        row = (0.0, None, None)
        assert safe_row_float(row, idx=1) == 0.0

    def test_valid_float(self) -> None:
        """5.0 in row → 5.0."""
        row = (5.0, None, None)
        assert safe_row_float(row, idx=0) == 5.0

    def test_int_zero(self) -> None:
        """int 0 in row → 0.0."""
        row = (0, None, None)
        assert safe_row_float(row, idx=0) == 0.0

    def test_empty_string(self) -> None:
        """Empty string in row → 0.0."""
        row = ("", None, None)
        assert safe_row_float(row, idx=0) == 0.0

    def test_string_number(self) -> None:
        """String '5' in row → 5.0."""
        row = ("5", None, None)
        assert safe_row_float(row, idx=0) == 5.0

    def test_nan(self) -> None:
        """NaN in row → 0.0."""
        row = (float("nan"), None, None)
        assert safe_row_float(row, idx=0) == 0.0

    def test_inf(self) -> None:
        """Infinity in row → 0.0."""
        row = (float("inf"), None, None)
        assert safe_row_float(row, idx=0) == 0.0


# ════════════════════════════════════════════════════════════════
# 2. _apply_fundamental_filter edge cases
# ════════════════════════════════════════════════════════════════


class TestApplyFundamentalFilter:
    """Verify filter logic with 0.0 values (not None)."""

    def setup_method(self) -> None:
        self.svc = ScreenerService()

    def _filter(self, data: dict, max_debt_to_equity: float = 3.0, min_roe: float = 0.0) -> list[str]:
        instruments = [{"symbol": sym, "name": sym} for sym in data]
        filtered = self.svc._apply_fundamental_filter(
            instruments, data,
            max_debt_to_equity=max_debt_to_equity,
            min_roe=min_roe,
        )
        return [i["symbol"] for i in filtered]

    def test_healthy_stock_passes(self) -> None:
        """Stock with normal ratios should pass."""
        data = {"FOLAD": {"pe_ratio": 5.0, "roe": 25.0, "debt_to_equity": 0.8, "net_margin": 15.0, "eps": 500}}
        result = self._filter(data)
        assert "FOLAD" in result

    def test_all_zeros_passes(self) -> None:
        """All-zero fundamental data should pass (0.0 D/E not > 3.0, 0.0 ROE not < 0.0)."""
        data = {"KHODRO": {"pe_ratio": 0.0, "roe": 0.0, "debt_to_equity": 0.0, "net_margin": 0.0, "eps": 0}}
        result = self._filter(data)
        assert "KHODRO" in result

    def test_no_fundamental_data_passes(self) -> None:
        """Symbol in instruments but missing from fundamental_data should pass through."""
        instruments = [{"symbol": "RAMZ", "name": "Test Co"}]
        fundamental_data: dict = {}  # RAMZ has no fundamental data entry
        filtered = self.svc._apply_fundamental_filter(
            instruments, fundamental_data,
            max_debt_to_equity=3.0,
            min_roe=0.0,
        )
        assert len(filtered) == 1
        assert filtered[0]["symbol"] == "RAMZ"

    def test_high_debt_filtered(self) -> None:
        """D/E > 3.0 should be filtered out."""
        data = {"SHPNA": {"pe_ratio": 3.0, "roe": 30.0, "debt_to_equity": 8.0, "net_margin": 10.0, "eps": 800}}
        result = self._filter(data)
        assert "SHPNA" not in result

    def test_negative_roe_filtered(self) -> None:
        """ROE < 0.0 should be filtered out."""
        data = {"KEGOL": {"pe_ratio": 6.0, "roe": -5.0, "debt_to_equity": 0.5, "net_margin": 12.0, "eps": 600}}
        result = self._filter(data)
        assert "KEGOL" not in result

    def test_mixed_filtered_correctly(self) -> None:
        """Multiple symbols: only those violating criteria are filtered."""
        data = {
            "FOLAD": {"pe_ratio": 5.0, "roe": 25.0, "debt_to_equity": 0.8, "net_margin": 15.0, "eps": 500},
            "KHODRO": {"pe_ratio": 0.0, "roe": 0.0, "debt_to_equity": 0.0, "net_margin": 0.0, "eps": 0},
            "SHPNA": {"pe_ratio": 3.0, "roe": 30.0, "debt_to_equity": 8.0, "net_margin": 10.0, "eps": 800},
            "KEGOL": {"pe_ratio": 6.0, "roe": -5.0, "debt_to_equity": 0.5, "net_margin": 12.0, "eps": 600},
            "BANK": {"pe_ratio": 0.0, "roe": 12.0, "debt_to_equity": 0.0, "net_margin": 0.0, "eps": 0},
        }
        result = self._filter(data)
        assert "FOLAD" in result    # healthy
        assert "KHODRO" in result   # all zeros -> passes
        assert "BANK" in result     # D/E=0, ROE=12 -> passes
        assert "SHPNA" not in result  # D/E=8.0 > 3.0 -> filtered
        assert "KEGOL" not in result  # ROE=-5.0 < 0.0 -> filtered


# ════════════════════════════════════════════════════════════════
# 3. Edge cases: None/missing data in row
# ════════════════════════════════════════════════════════════════


class TestSafeRowFloatEdgeCases:
    """Edge cases for safe_row_float with None, partial-None, boundaries."""

    def test_none_row(self) -> None:
        """Passing None as row returns default (0.0)."""
        assert safe_row_float(None, idx=0) == 0.0

    def test_none_row_custom_default(self) -> None:
        """Passing None as row returns custom default."""
        assert safe_row_float(None, idx=0, default=1.0) == 1.0

    def test_out_of_bounds_idx(self) -> None:
        """Index beyond row length returns default."""
        row = (10.0, 20.0)
        assert safe_row_float(row, idx=5, default=-1.0) == -1.0

    def test_negative_idx(self) -> None:
        """Negative index returns default (not supported)."""
        row = (10.0, 20.0)
        assert safe_row_float(row, idx=-1, default=0.0) == 0.0

    def test_partial_none_preserves_values(self) -> None:
        """Row with mixed None/values: None fields get 0.0, values preserved."""
        row = ("FAMLI", 8.0, 20.0, None, 12.0, 1000)
        assert safe_row_float(row, idx=1) == 8.0
        assert safe_row_float(row, idx=3) == 0.0  # None -> 0.0
        assert safe_row_float(row, idx=5) == 1000.0

    def test_empty_row(self) -> None:
        """Empty tuple returns default."""
        assert safe_row_float((), idx=0) == 0.0

    def test_all_none_tuple(self) -> None:
        """All-None row returns all 0.0."""
        row = ("TAPIKO", None, None, None, None, None)
        assert safe_row_float(row, idx=1) == 0.0
        assert safe_row_float(row, idx=2) == 0.0
        assert safe_row_float(row, idx=3) == 0.0
        assert safe_row_float(row, idx=4) == 0.0
        assert safe_row_float(row, idx=5) == 0.0


# ═══════════════════════════════════════════════════════════════════
# 4. safe_row_str — type-coerced string from DB row
# ═══════════════════════════════════════════════════════════════════


class TestSafeRowStr:
    """Verify safe_row_str handles None, numeric, bool, and edge cases correctly."""

    def test_none_row_returns_default(self) -> None:
        """Passing None as row returns empty string."""
        assert safe_row_str(None, idx=0) == ""

    def test_none_row_custom_default(self) -> None:
        """Custom default is returned when row is None."""
        assert safe_row_str(None, idx=0, default="N/A") == "N/A"

    def test_none_value_returns_default_not_none_string(self) -> None:
        """None in a column returns default, not the string 'None'."""
        row = (None,)
        assert safe_row_str(row, idx=0) == ""

    def test_none_value_custom_default(self) -> None:
        """Custom default is returned when column value is None."""
        row = (None,)
        assert safe_row_str(row, idx=0, default="(empty)") == "(empty)"

    def test_string_value_passthrough(self) -> None:
        """String values pass through unchanged."""
        row = ("ABC",)
        assert safe_row_str(row, idx=0) == "ABC"

    def test_int_converted_to_str(self) -> None:
        """Integer values are converted to string."""
        row = (123,)
        assert safe_row_str(row, idx=0) == "123"

    def test_float_converted_to_str(self) -> None:
        """Float values are converted to string."""
        row = (3.14,)
        assert safe_row_str(row, idx=0) == "3.14"

    def test_bool_true_converted_to_str(self) -> None:
        """True becomes string 'True'."""
        row = (True,)
        assert safe_row_str(row, idx=0) == "True"

    def test_bool_false_converted_to_str(self) -> None:
        """False becomes string 'False'."""
        row = (False,)
        assert safe_row_str(row, idx=0) == "False"

    def test_empty_string_preserved(self) -> None:
        """Empty string is a valid value and should not be replaced by default."""
        row = ("",)
        assert safe_row_str(row, idx=0) == ""

    def test_zero_int_returns_zero_string(self) -> None:
        """Integer 0 should return '0', not default."""
        row = (0,)
        assert safe_row_str(row, idx=0) == "0"

    def test_zero_float_returns_zero_string(self) -> None:
        """Float 0.0 should return '0.0', not default."""
        row = (0.0,)
        assert safe_row_str(row, idx=0) == "0.0"

    def test_zero_padded_string(self) -> None:
        """Zero-padded strings like '00123' should be preserved."""
        row = ("00123",)
        assert safe_row_str(row, idx=0) == "00123"

    def test_out_of_bounds_returns_default(self) -> None:
        """Index beyond row length returns default."""
        row = ("A",)
        assert safe_row_str(row, idx=5, default="N/A") == "N/A"

    def test_negative_idx_returns_default(self) -> None:
        """Negative index returns default (not supported for slicing)."""
        row = ("A", "B")
        assert safe_row_str(row, idx=-1) == ""

    def test_empty_tuple_returns_default(self) -> None:
        """Empty tuple should return default."""
        assert safe_row_str((), idx=0) == ""

    def test_persian_text_preserved(self) -> None:
        """Persian/Arabic text should be preserved unchanged."""
        row = ("فولاد مبارکه",)
        assert safe_row_str(row, idx=0) == "فولاد مبارکه"

    def test_never_returns_none(self) -> None:
        """safe_row_str must never return None — always str."""
        cases = [
            None,           # None row
            (None,),        # None value
            (),              # empty tuple
            ("",),           # empty string
        ]
        for case in cases:
            result = safe_row_str(case, idx=0)
            assert isinstance(result, str), f"Expected str, got {type(result)} for {case}"

    def test_multiple_columns_selects_correct_idx(self) -> None:
        """With multiple columns, idx selects the right one."""
        row = ("SKIP", "TARGET", "SKIP")
        assert safe_row_str(row, idx=1) == "TARGET"

    def test_pattern_slicing_after_safe_row_str(self) -> None:
        """Common pattern in codebase: safe_row_str(row, idx=X)[:N] for truncation.

        This matches usage like:
            safe_row_str(row, idx=6)[:300]  # summary[:300]
            safe_row_str(row, idx=7)[:100]  # url[:100]
        """
        row = ("A" * 500,)
        truncated = safe_row_str(row, idx=0)[:100]
        assert len(truncated) == 100
        assert truncated == "A" * 100

    def test_pattern_fallback_chain(self) -> None:
        """Common pattern: safe_row_str(row, idx=6) or safe_row_str(row, idx=2).

        Matches usage like:
            "title": safe_row_str(row, idx=6) or safe_row_str(row, idx=2)
        """
        # idx=6 is None -> falls back to idx=2
        row = ("A", "B", "fallback_title", "D", "E", "F", None)
        result = safe_row_str(row, idx=6) or safe_row_str(row, idx=2)
        assert result == "fallback_title"

        # idx=6 is valid -> uses idx=6
        row2 = ("A", "B", "C", "D", "E", "F", "primary_title")
        result2 = safe_row_str(row2, idx=6) or safe_row_str(row2, idx=2)
        assert result2 == "primary_title"

        # Both are None -> empty string
        row3 = (None, None, None, None, None, None, None)
        result3 = safe_row_str(row3, idx=6) or safe_row_str(row3, idx=2)
        assert result3 == ""
