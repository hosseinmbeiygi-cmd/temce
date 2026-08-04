from __future__ import annotations

from iran_market_data.app.utils.normalizer import (
    normalize_persian_text,
    persian_digits_to_english,
)


class TestNormalizePersianText:
    """Tests for normalize_persian_text function."""

    def test_normalize_arabic_yeh_to_persian(self) -> None:
        """Arabic yeh (ي) should be converted to Persian yeh (ی)."""
        result = normalize_persian_text("ي")
        assert result == "ی"

    def test_normalize_arabic_kaf_to_persian(self) -> None:
        """Arabic kaf (ك) should be converted to Persian kaf (ک)."""
        result = normalize_persian_text("ك")
        assert result == "ک"

    def test_normalize_multiple_characters(self) -> None:
        """Multiple characters should all be normalized."""
        result = normalize_persian_text("يك")
        assert result == "یک"

    def test_normalize_zwnj_to_space(self) -> None:
        """ZWNJ (U+200C) should be replaced with space."""
        text = "متن\u200cفارسی"
        result = normalize_persian_text(text)
        assert " " in result

    def test_normalize_extra_whitespace(self) -> None:
        """Extra whitespace should be collapsed."""
        result = normalize_persian_text("متن   فارسی")
        assert result == "متن فارسی"

    def test_normalize_none_input(self) -> None:
        """None input should return None."""
        assert normalize_persian_text(None) is None

    def test_normalize_empty_string(self) -> None:
        """Empty string should return empty string."""
        result = normalize_persian_text("")
        assert result == ""

    def test_normalize_already_normalized(self) -> None:
        """Already normalized text should remain unchanged."""
        text = "سلام دنیا"
        result = normalize_persian_text(text)
        assert result == text

    def test_normalize_leading_trailing_spaces(self) -> None:
        """Leading/trailing spaces should be stripped."""
        result = normalize_persian_text("  متن  ")
        assert result == "متن"


class TestPersianDigitsToEnglish:
    """Tests for persian_digits_to_english function."""

    def test_persian_digits_conversion(self) -> None:
        """Persian digits (۱۲۳) should be converted to English (123)."""
        result = persian_digits_to_english("۱۲۳")
        assert result == "123"

    def test_arabic_digits_conversion(self) -> None:
        """Arabic digits (١٢٣) should be converted to English (123)."""
        result = persian_digits_to_english("١٢٣")
        assert result == "123"

    def test_mixed_digits_conversion(self) -> None:
        """Mixed Persian and Arabic digits should all be converted."""
        result = persian_digits_to_english("۱۲٣")
        assert result == "123"

    def test_english_digits_unchanged(self) -> None:
        """English digits should remain unchanged."""
        result = persian_digits_to_english("123")
        assert result == "123"

    def test_none_input(self) -> None:
        """None input should return None."""
        assert persian_digits_to_english(None) is None

    def test_empty_string(self) -> None:
        """Empty string should return empty string."""
        assert persian_digits_to_english("") == ""

    def test_all_persian_digits(self) -> None:
        """All 10 Persian digits should be converted correctly."""
        result = persian_digits_to_english("۰۱۲۳۴۵۶۷۸۹")
        assert result == "0123456789"

    def test_all_arabic_digits(self) -> None:
        """All 10 Arabic digits should be converted correctly."""
        result = persian_digits_to_english("٠١٢٣٤٥٦٧٨٩")
        assert result == "0123456789"
