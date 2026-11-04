"""Persian ticker normalization shared by services and repositories.

Extracted from ``services.news_tag_symbol_mapper`` so the read repository can
normalize tags without importing the service layer (import-linter contract).
"""

from __future__ import annotations

import re

# Arabic → Persian character folding (applied to both tag and target).
_CHAR_MAP = {
    "ي": "ی",  # Arabic yeh
    "ك": "ک",  # Arabic kaf
    "ة": "ه",  # teh marbuta
    "ۀ": "ه",
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",  # alef variants (ticker context: safe fold)
    "ؤ": "و",
    "ئ": "ی",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}
_CHAR_RE = re.compile("[" + "".join(_CHAR_MAP) + "]")

# Zero-width joiners fold to a space (نیم‌فاصله ≡ فاصله for matching:
# ``سرمايه‌گذاري`` must equal ``سرمایه گذاری``); the rest are pure noise.
_ZWNJ_RE = re.compile("[‌‍]")
_STRIP_RE = re.compile("[‏‎‪-‮﻿ ]")


def normalize_persian(value: str | None) -> str:
    """Canonical Persian form of a ticker: fold Arabic chars, strip
    zero-width joiners, collapse whitespace, casefold (for latin digits)."""
    if not value:
        return ""
    v = _STRIP_RE.sub(" ", value)
    v = _ZWNJ_RE.sub(" ", v)
    v = _CHAR_RE.sub(lambda m: _CHAR_MAP[m.group(0)], v)
    v = " ".join(v.split())
    return v.casefold()


def spelling_variants(value: str | None) -> set[str]:
    """Spelling variants of a ticker: raw, Persian-normalized, and the
    Arabic back-spelled form (ی→ي، ک→ك)."""
    if not value:
        return set()
    norm = normalize_persian(value)
    arabic = norm.translate(str.maketrans("یک", "يك"))
    return {v for v in (value.strip(), norm, arabic) if v}
