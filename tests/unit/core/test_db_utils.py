"""Unit tests for all helpers in core/db_utils.py.

Covers:
  - safe_row_value: None row, out-of-bounds, None value, valid value, boolean
  - safe_row_float: float conversion, NaN, Inf, empty string, bool, string numbers
  - safe_row_int: int conversion, float truncation, string parsing, bool
  - safe_row_str: string conversion, None, non-string, custom default
  - safe_float: scalar float, thousand separators, None, bool, NaN, Inf, 'Infinity'
  - safe_int: scalar int, float string, bool, None
"""

from __future__ import annotations

from core.db_utils import (
    safe_float,
    safe_int,
    safe_row_float,
    safe_row_int,
    safe_row_str,
    safe_row_value,
)

# ═══════════════════════════════════════════════════════════════════
# 1. safe_row_value — base helper
# ═══════════════════════════════════════════════════════════════════


class TestSafeRowValue:
    def test_none_row_returns_default(self) -> None:
        assert safe_row_value(None, idx=0) is None

    def test_none_row_custom_default(self) -> None:
        assert safe_row_value(None, idx=0, default="N/A") == "N/A"

    def test_out_of_bounds_idx_returns_default(self) -> None:
        row = (10, 20)
        assert safe_row_value(row, idx=5) is None

    def test_out_of_bounds_custom_default(self) -> None:
        row = (10, 20)
        assert safe_row_value(row, idx=5, default=0) == 0

    def test_negative_idx_returns_default(self) -> None:
        row = (10, 20)
        assert safe_row_value(row, idx=-1) is None

    def test_none_value_in_row_returns_default(self) -> None:
        row = (None, 20)
        assert safe_row_value(row, idx=0) is None

    def test_valid_int_value(self) -> None:
        row = (42,)
        assert safe_row_value(row, idx=0) == 42

    def test_valid_float_value(self) -> None:
        row = (3.14,)
        assert safe_row_value(row, idx=0) == 3.14

    def test_valid_string_value(self) -> None:
        row = ("hello",)
        assert safe_row_value(row, idx=0) == "hello"

    def test_valid_zero_int(self) -> None:
        """0 is a valid value, not None — should return 0, not default."""
        row = (0,)
        assert safe_row_value(row, idx=0) == 0

    def test_valid_zero_float(self) -> None:
        row = (0.0,)
        assert safe_row_value(row, idx=0) == 0.0

    def test_valid_empty_string(self) -> None:
        """Empty string is a valid value — should return '', not default."""
        row = ("",)
        assert safe_row_value(row, idx=0) == ""

    def test_valid_false_bool(self) -> None:
        """False is a valid value — should return False, not default."""
        row = (False,)
        assert safe_row_value(row, idx=0) is False

    def test_empty_tuple_returns_default(self) -> None:
        assert safe_row_value((), idx=0) is None

    def test_index_error_handled(self) -> None:
        """Indices past the end should not raise."""
        row = (1, 2, 3)
        assert safe_row_value(row, idx=99, default=-1) == -1

    def test_non_sequence_row(self) -> None:
        """Non-indexable row should fall back gracefully."""
        assert safe_row_value(42, idx=0, default="fallback") == "fallback"


# ═══════════════════════════════════════════════════════════════════
# 2. safe_row_float — type-coerced float from DB row
# ═══════════════════════════════════════════════════════════════════


class TestSafeRowFloat:
    def test_none_row_returns_default(self) -> None:
        assert safe_row_float(None, idx=0) == 0.0

    def test_none_row_custom_default(self) -> None:
        assert safe_row_float(None, idx=0, default=1.0) == 1.0

    def test_none_value_returns_default(self) -> None:
        row = (None,)
        assert safe_row_float(row, idx=0) == 0.0

    def test_valid_float(self) -> None:
        row = (3.14,)
        assert safe_row_float(row, idx=0) == 3.14

    def test_valid_int(self) -> None:
        row = (42,)
        assert safe_row_float(row, idx=0) == 42.0

    def test_zero_int_returns_0(self) -> None:
        """0 should return 0.0, not None."""
        row = (0,)
        assert safe_row_float(row, idx=0) == 0.0

    def test_zero_float_returns_0(self) -> None:
        row = (0.0,)
        assert safe_row_float(row, idx=0) == 0.0

    def test_negative_float(self) -> None:
        row = (-5.5,)
        assert safe_row_float(row, idx=0) == -5.5

    def test_string_number(self) -> None:
        row = ("123.45",)
        assert safe_row_float(row, idx=0) == 123.45

    def test_string_with_commas_returns_default(self) -> None:
        """safe_row_float does NOT strip thousand separators (safe_float does)."""
        row = ("1,234.56",)
        assert safe_row_float(row, idx=0) == 0.0

    def test_empty_string_returns_default(self) -> None:
        row = ("",)
        assert safe_row_float(row, idx=0) == 0.0

    def test_whitespace_string_returns_default(self) -> None:
        row = ("   ",)
        assert safe_row_float(row, idx=0) == 0.0

    def test_nan_returns_default(self) -> None:
        row = (float("nan"),)
        assert safe_row_float(row, idx=0) == 0.0

    def test_inf_returns_default(self) -> None:
        row = (float("inf"),)
        assert safe_row_float(row, idx=0) == 0.0

    def test_neg_inf_returns_default(self) -> None:
        row = (float("-inf"),)
        assert safe_row_float(row, idx=0) == 0.0

    def test_bool_true(self) -> None:
        row = (True,)
        assert safe_row_float(row, idx=0) == 1.0

    def test_bool_false(self) -> None:
        row = (False,)
        assert safe_row_float(row, idx=0) == 0.0

    def test_out_of_bounds(self) -> None:
        row = (10.0,)
        assert safe_row_float(row, idx=5, default=-1.0) == -1.0

    def test_negative_idx(self) -> None:
        row = (10.0, 20.0)
        assert safe_row_float(row, idx=-1) == 0.0

    def test_str_infinity_returns_inf(self) -> None:
        """Python's float('Infinity') succeeds, so safe_row_float returns inf."""
        row = ("Infinity",)
        result = safe_row_float(row, idx=0)
        import math
        assert math.isinf(result)

    def test_non_numeric_string_returns_default(self) -> None:
        row = ("not-a-number",)
        assert safe_row_float(row, idx=0) == 0.0

    def test_empty_row(self) -> None:
        assert safe_row_float((), idx=0) == 0.0

    def test_multiple_columns_selects_correct_idx(self) -> None:
        row = ("SKIP", 99.5, "SKIP")
        assert safe_row_float(row, idx=1) == 99.5


# ═══════════════════════════════════════════════════════════════════
# 3. safe_row_int — type-coerced int from DB row
# ═══════════════════════════════════════════════════════════════════


class TestSafeRowInt:
    def test_none_row_returns_default(self) -> None:
        assert safe_row_int(None, idx=0) == 0

    def test_none_row_custom_default(self) -> None:
        assert safe_row_int(None, idx=0, default=-1) == -1

    def test_none_value_returns_default(self) -> None:
        row = (None,)
        assert safe_row_int(row, idx=0) == 0

    def test_valid_int(self) -> None:
        row = (42,)
        assert safe_row_int(row, idx=0) == 42

    def test_zero_int(self) -> None:
        row = (0,)
        assert safe_row_int(row, idx=0) == 0

    def test_negative_int(self) -> None:
        row = (-5,)
        assert safe_row_int(row, idx=0) == -5

    def test_float_truncation(self) -> None:
        """Float values should be truncated to int."""
        row = (3.99,)
        assert safe_row_int(row, idx=0) == 3

    def test_negative_float_truncation(self) -> None:
        row = (-3.99,)
        assert safe_row_int(row, idx=0) == -3

    def test_float_zero(self) -> None:
        row = (0.0,)
        assert safe_row_int(row, idx=0) == 0

    def test_string_number(self) -> None:
        row = ("123",)
        assert safe_row_int(row, idx=0) == 123

    def test_string_float(self) -> None:
        """String '123.0' should be parsed correctly via float first."""
        row = ("123.0",)
        assert safe_row_int(row, idx=0) == 123

    def test_string_float_truncation(self) -> None:
        """String '3.99' should truncate to 3."""
        row = ("3.99",)
        assert safe_row_int(row, idx=0) == 3

    def test_empty_string_returns_default(self) -> None:
        row = ("",)
        assert safe_row_int(row, idx=0) == 0

    def test_whitespace_string_returns_default(self) -> None:
        row = ("  ",)
        assert safe_row_int(row, idx=0) == 0

    def test_bool_true(self) -> None:
        row = (True,)
        assert safe_row_int(row, idx=0) == 1

    def test_bool_false(self) -> None:
        row = (False,)
        assert safe_row_int(row, idx=0) == 0

    def test_nan_returns_default(self) -> None:
        row = (float("nan"),)
        assert safe_row_int(row, idx=0) == 0

    def test_inf_returns_default(self) -> None:
        row = (float("inf"),)
        assert safe_row_int(row, idx=0) == 0

    def test_neg_inf_returns_default(self) -> None:
        row = (float("-inf"),)
        assert safe_row_int(row, idx=0) == 0

    def test_non_numeric_string_returns_default(self) -> None:
        row = ("not-a-number",)
        assert safe_row_int(row, idx=0) == 0

    def test_out_of_bounds(self) -> None:
        row = (10,)
        assert safe_row_int(row, idx=5, default=-1) == -1

    def test_negative_idx(self) -> None:
        row = (10, 20)
        assert safe_row_int(row, idx=-1) == 0

    def test_large_float_via_string(self) -> None:
        """Large values should not overflow."""
        row = ("9999999999",)
        assert safe_row_int(row, idx=0) == 9999999999


# ═══════════════════════════════════════════════════════════════════
# 4. safe_row_str — type-coerced string from DB row
# ═══════════════════════════════════════════════════════════════════


class TestSafeRowStr:
    def test_none_row_returns_default(self) -> None:
        assert safe_row_str(None, idx=0) == ""

    def test_none_row_custom_default(self) -> None:
        assert safe_row_str(None, idx=0, default="N/A") == "N/A"

    def test_none_value_returns_default(self) -> None:
        """None in a column should return default (not 'None' string)."""
        row = (None,)
        assert safe_row_str(row, idx=0) == ""

    def test_none_value_custom_default(self) -> None:
        row = (None,)
        assert safe_row_str(row, idx=0, default="(empty)") == "(empty)"

    def test_string_value(self) -> None:
        row = ("ABC",)
        assert safe_row_str(row, idx=0) == "ABC"

    def test_int_value(self) -> None:
        """int should be converted to string."""
        row = (123,)
        assert safe_row_str(row, idx=0) == "123"

    def test_float_value(self) -> None:
        """float should be converted to string."""
        row = (3.14,)
        assert safe_row_str(row, idx=0) == "3.14"

    def test_bool_true(self) -> None:
        row = (True,)
        assert safe_row_str(row, idx=0) == "True"

    def test_bool_false(self) -> None:
        row = (False,)
        assert safe_row_str(row, idx=0) == "False"

    def test_empty_string_preserved(self) -> None:
        """Empty string is a valid value, should not return default."""
        row = ("",)
        assert safe_row_str(row, idx=0) == ""

    def test_zero_int(self) -> None:
        """0 should return '0', not default."""
        row = (0,)
        assert safe_row_str(row, idx=0) == "0"

    def test_zero_padded_string(self) -> None:
        row = ("00123",)
        assert safe_row_str(row, idx=0) == "00123"

    def test_out_of_bounds(self) -> None:
        row = ("A",)
        assert safe_row_str(row, idx=5, default="N/A") == "N/A"

    def test_negative_idx(self) -> None:
        row = ("A", "B")
        assert safe_row_str(row, idx=-1) == ""

    def test_persian_text(self) -> None:
        row = ("فولاد مبارکه",)
        assert safe_row_str(row, idx=0) == "فولاد مبارکه"

    def test_none_never_returns_none(self) -> None:
        """safe_row_str should never return None, always str."""
        result = safe_row_str(None, idx=0)
        assert isinstance(result, str)
        result = safe_row_str((None,), idx=0)
        assert isinstance(result, str)
        result = safe_row_str((), idx=0)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# 5. safe_float — scalar float conversion
# ═══════════════════════════════════════════════════════════════════


class TestSafeFloat:
    def test_none_returns_default(self) -> None:
        assert safe_float(None) == 0.0

    def test_none_custom_default(self) -> None:
        assert safe_float(None, default=-1.0) == -1.0

    def test_float_value(self) -> None:
        assert safe_float(3.14) == 3.14

    def test_int_value(self) -> None:
        assert safe_float(42) == 42.0

    def test_zero_int(self) -> None:
        assert safe_float(0) == 0.0

    def test_negative_value(self) -> None:
        assert safe_float(-5.5) == -5.5

    def test_string_number(self) -> None:
        assert safe_float("123.45") == 123.45

    def test_string_with_thousand_separator(self) -> None:
        """Thousand-separated strings like '1,234' should parse correctly."""
        assert safe_float("1,234") == 1234.0

    def test_string_with_persian_separator(self) -> None:
        """Persian/Arabic thousand separator (٬) should be handled."""
        assert safe_float("1٬234") == 1234.0

    def test_string_with_commas_and_decimal(self) -> None:
        assert safe_float("1,234.56") == 1234.56

    def test_empty_string_returns_default(self) -> None:
        assert safe_float("") == 0.0

    def test_whitespace_string_returns_default(self) -> None:
        assert safe_float("   ") == 0.0

    def test_nan_returns_default(self) -> None:
        assert safe_float(float("nan")) == 0.0

    def test_inf_returns_default(self) -> None:
        assert safe_float(float("inf")) == 0.0

    def test_neg_inf_returns_default(self) -> None:
        assert safe_float(float("-inf")) == 0.0

    def test_string_infinity_returns_default(self) -> None:
        """Literal string 'Infinity' should return default."""
        assert safe_float("Infinity") == 0.0

    def test_non_numeric_string_returns_default(self) -> None:
        assert safe_float("not-a-number") == 0.0

    def test_bool_true(self) -> None:
        assert safe_float(True) == 1.0

    def test_bool_false(self) -> None:
        assert safe_float(False) == 0.0

    def test_percent_string_returns_default(self) -> None:
        """safe_float does NOT strip % sign — returns default."""
        assert safe_float("12.5%") == 0.0

    def test_negative_string(self) -> None:
        assert safe_float("-5.5") == -5.5

    def test_string_with_plus(self) -> None:
        assert safe_float("+10") == 10.0


# ═══════════════════════════════════════════════════════════════════
# 6. safe_int — scalar int conversion
# ═══════════════════════════════════════════════════════════════════


class TestSafeInt:
    def test_none_returns_default(self) -> None:
        assert safe_int(None) == 0

    def test_none_custom_default(self) -> None:
        assert safe_int(None, default=-1) == -1

    def test_int_value(self) -> None:
        assert safe_int(42) == 42

    def test_zero_int(self) -> None:
        assert safe_int(0) == 0

    def test_negative_int(self) -> None:
        assert safe_int(-5) == -5

    def test_float_truncation(self) -> None:
        """Float values should be truncated, not rounded."""
        assert safe_int(3.99) == 3
        assert safe_int(-3.99) == -3

    def test_float_zero(self) -> None:
        assert safe_int(0.0) == 0

    def test_string_number(self) -> None:
        assert safe_int("123") == 123

    def test_string_float(self) -> None:
        """String '123.0' should parse via float first."""
        assert safe_int("123.0") == 123

    def test_string_float_truncation(self) -> None:
        assert safe_int("3.99") == 3

    def test_empty_string_returns_default(self) -> None:
        assert safe_int("") == 0

    def test_whitespace_string_returns_default(self) -> None:
        assert safe_int("  ") == 0

    def test_non_numeric_string_returns_default(self) -> None:
        assert safe_int("not-a-number") == 0

    def test_bool_true(self) -> None:
        assert safe_int(True) == 1

    def test_bool_false(self) -> None:
        assert safe_int(False) == 0

    def test_nan_returns_default(self) -> None:
        assert safe_int(float("nan")) == 0

    def test_inf_returns_default(self) -> None:
        assert safe_int(float("inf")) == 0

    def test_neg_inf_returns_default(self) -> None:
        assert safe_int(float("-inf")) == 0

    def test_large_int_string(self) -> None:
        """Large values should not overflow when parsed."""
        assert safe_int("9999999999") == 9999999999

    def test_negative_string(self) -> None:
        assert safe_int("-5") == -5

    def test_string_with_commas_returns_default(self) -> None:
        """safe_int does NOT support thousand separators (safe_float does)."""
        assert safe_int("1,234") == 0  # ',' prevents parsing

    def test_percent_string_returns_default(self) -> None:
        assert safe_int("12%") == 0
