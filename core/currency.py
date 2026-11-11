"""Rial ⇄ toman conversion for the Iranian market.

Two units circulate in this codebase:

* **Rial (IRR)** — what the market data feeds (BrsApi, TSETMC) return and what
  the ``brsapi_*`` tables store. Never divide those numbers by hand.
* **Toman (TMN)** — what users read in the UI, API responses, reports and logs.
  ``1 toman == 10 rial``.

All arithmetic goes through :class:`decimal.Decimal`: binary floats cannot
represent 0.1 exactly, and rounding drift on money is a bug, not a display
detail. ``None`` is propagated as ``None`` so callers can keep an optional
column optional instead of collapsing it to ``0``.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

__all__ = [
    "CURRENCY_RIAL",
    "CURRENCY_TOMAN",
    "RIAL_PER_TOMAN",
    "rial_to_toman",
    "rial_to_toman_float",
    "toman_to_rial",
]

#: ISO-4217 code for the rial.
CURRENCY_RIAL = "IRR"
#: Currency code used for toman-denominated user-facing values.
CURRENCY_TOMAN = "TMN"
#: ``1 toman == 10 rial`` since the 1932 reform — rial never gained a subunit.
RIAL_PER_TOMAN = Decimal("10")


def _to_decimal(value: Decimal | int | float | str | None) -> Decimal | None:
    """Coerce ``value`` to an exact ``Decimal``, preserving ``None``.

    Floats are accepted for convenience but converted through ``str`` so the
    binary noise (``1234.4999999999998``) never reaches the result.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("currency amounts must be numeric, not bool")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        result = Decimal(str(value))
    elif isinstance(value, str):
        # Feeds occasionally ship thousands separators.
        cleaned = value.strip().replace(",", "").replace("\u066c", "")
        if not cleaned:
            return None
        try:
            result = Decimal(cleaned)
        except InvalidOperation as exc:  # pragma: no cover - defensive
            raise ValueError(f"not a numeric amount: {value!r}") from exc
    else:
        raise TypeError(
            "currency amounts must be Decimal, int, float, str or None, "
            f"got {type(value).__name__}"
        )

    if not result.is_finite():
        raise ValueError(f"currency amount must be finite, got {value!r}")
    return result


def _round(value: Decimal, places: int | None) -> Decimal:
    if places is None:
        return value
    if places < 0:
        raise ValueError("places must be >= 0")
    exponent = Decimal(1).scaleb(-places)
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def rial_to_toman(
    value: Decimal | int | float | str | None,
    *,
    places: int | None = None,
) -> Decimal | None:
    """Convert a rial amount to toman (``value / 10``).

    Division by ten is exact in decimal, so by default no rounding happens; pass
    ``places=0`` to round to whole toman (``ROUND_HALF_UP``) for display.

    >>> rial_to_toman(1_234_500)
    Decimal('123450')
    >>> rial_to_toman(None) is None
    True
    """
    amount = _to_decimal(value)
    if amount is None:
        return None
    return _round(amount / RIAL_PER_TOMAN, places)


def rial_to_toman_float(
    value: Decimal | int | float | str | None,
    *,
    default: float | None = 0.0,
) -> float | None:
    """Rial → toman as a ``float`` for JSON payloads.

    Presentation only: keep arithmetic on the ``Decimal`` result of
    :func:`rial_to_toman` and use this at the serialisation boundary, where a
    JSON number is expected. ``None`` maps to ``default`` so a missing price
    stays missing in shape but never breaks ``json.dumps``.
    """
    converted = rial_to_toman(value)
    return default if converted is None else float(converted)


def toman_to_rial(
    value: Decimal | int | float | str | None,
    *,
    places: int | None = None,
) -> Decimal | None:
    """Convert a toman amount to rial (``value * 10``).

    >>> toman_to_rial(Decimal("123450"))
    Decimal('1234500')
    >>> toman_to_rial(None) is None
    True
    """
    amount = _to_decimal(value)
    if amount is None:
        return None
    return _round(amount * RIAL_PER_TOMAN, places)
