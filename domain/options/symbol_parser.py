"""Option symbol parser for the Tehran Stock Exchange (TSE/IFB).

Spec reference: ``معماری-پلتفرم-آپشن-بورس-تهران.md`` §5.2 (Symbol Parser).

Iranian option tickers carry structure::

    <base symbol> + <type char> + <strike> [+ <expiry yyyymmdd>]

Both Persian and Latin renderings are supported.  In live market data the
type is almost always spelled out as a word — ``ط`` (tal, call) or ``ت``
(tahod, put) — while abbreviated Latin ``C``/``P`` and full words
(``CALL``/``PUT``, ``طلب``/``تعهد``) are accepted for robustness.

Examples
--------
>>> parse_option_symbol("خودروط600001001")
{'base': 'خودرو', 'option_type': 'CALL', 'strike': 600.0, ...}
>>> parse_option_symbol("فولاد-ط-6000-20260921")
{'base': 'فولاد', 'option_type': 'CALL', 'strike': 6000.0, ...}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class OptionSymbolError(ValueError):
    """Raised when a ticker does not match any known option-symbol shape."""


@dataclass(frozen=True)
class ParsedOptionSymbol:
    base_symbol: str
    option_type: str  # "CALL" | "PUT"
    strike: float
    raw: str
    expiry: str | None = None  # yyyymmdd when present in the ticker
    digits: list[float] = field(default_factory=list)


# Persian → Latin digit folding (۰-۹ → 0-9).
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# Type tokens, longest first so full words win over single chars.
_CALL_TOKENS = ("طلب", "CALL", "call", "Call", "ط", "C")
_PUT_TOKENS = ("تعهد", "PUT", "put", "Put", "ت", "P")

_ZWNJ = "\u200c"  # zero-width non-joiner often glued into tickers


def _fold(ticker: str) -> str:
    return ticker.translate(_PERSIAN_DIGITS).replace(_ZWNJ, "").strip()


def _split_type(ticker: str) -> tuple[str, str, int] | None:
    """Return (base, option_type, index_of_type_token) or None."""
    for token in _CALL_TOKENS:
        idx = ticker.find(token)
        if idx > 0:  # must follow at least one base char
            return ticker[:idx], "CALL", idx + len(token)
    for token in _PUT_TOKENS:
        idx = ticker.find(token)
        if idx > 0:
            return ticker[:idx], "PUT", idx + len(token)
    return None


def _numeric_suffix(text: str) -> tuple[list[float], str | None]:
    """Extract all integer groups and an optional trailing yyyymmdd date."""
    numbers = re.findall(r"\d+", text)
    digits: list[float] = []
    expiry: str | None = None

    if numbers and len(numbers[-1]) in (6, 8) and re.fullmatch(r"(?:20)?\d{6}", numbers[-1]):
        candidate = numbers[-1]
        # 6-digit dates look like yymmdd; 8-digit like yyyymmdd.
        expiry = candidate if len(candidate) == 8 else None
        numbers = numbers[:-1]

    for number in numbers:
        digits.append(float(number))

    return digits, expiry


def parse_option_symbol(ticker: str) -> ParsedOptionSymbol:
    """Parse an Iranian option ticker into its structured components.

    Raises ``OptionSymbolError`` when the ticker does not look like an
    option symbol at all.
    """
    if not ticker or not isinstance(ticker, str):
        raise OptionSymbolError("نماد خالی است")

    cleaned = _fold(ticker)
    split = _split_type(cleaned)
    if split is None:
        raise OptionSymbolError(f"نماد نامعتبر: {ticker}")

    base, option_type, rest_start = split
    base = base.strip(" -_.")
    if not base:
        raise OptionSymbolError(f"نماد پایه یافت نشد: {ticker}")

    rest = cleaned[rest_start:]
    digits, expiry = _numeric_suffix(rest)
    if not digits:
        raise OptionSymbolError(f"قیمت اعمال یافت نشد: {ticker}")

    strike = digits[0]
    return ParsedOptionSymbol(
        base_symbol=base,
        option_type=option_type,
        strike=strike,
        raw=ticker,
        expiry=expiry,
        digits=digits,
    )


def is_option_symbol(ticker: str) -> bool:
    """Cheap check used by ingestion pipelines to route rows."""
    if not ticker:
        return False
    cleaned = _fold(ticker)
    return _split_type(cleaned) is not None


def parse_or_none(ticker: str) -> ParsedOptionSymbol | None:
    """Non-raising variant for batch pipelines."""
    try:
        return parse_option_symbol(ticker)
    except OptionSymbolError:
        return None
