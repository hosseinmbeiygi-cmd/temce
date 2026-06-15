from __future__ import annotations


def normalize_persian_text(text: str | None) -> str | None:
    """Normalize Persian text: fix yeh and kaf characters, remove ZWNJ."""
    if text is None:
        return None

    replacements: dict[str, str] = {
        "\u064a": "\u06cc",  # Arabic yeh → Persian yeh
        "\u0643": "\u06a9",  # Arabic kaf → Persian kaf
        "\u200c": " ",  # ZWNJ → space
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return " ".join(text.split())


def persian_digits_to_english(text: str | None) -> str | None:
    """Convert Persian/Arabic digits to English digits."""
    if text is None:
        return None

    persian_digits = "\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9"
    arabic_digits = "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669"
    english_digits = "0123456789"

    for p, e in zip(persian_digits, english_digits, strict=False):
        text = text.replace(p, e)

    for a, e in zip(arabic_digits, english_digits, strict=False):
        text = text.replace(a, e)

    return text
