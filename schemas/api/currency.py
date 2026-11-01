"""Shared currency metadata for user-facing response schemas.

Response models keep the raw values they receive from the data layer (rial, as
stored by the feeds) and expose an additional ``*_toman`` computed field plus
an explicit ``currency`` marker. That keeps existing consumers working while
making the toman value and its unit unambiguous.

See :mod:`core.currency` for the conversion itself.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import Field

from core.currency import CURRENCY_RIAL, CURRENCY_TOMAN, rial_to_toman_float

__all__ = ["CurrencyCode", "currency_field", "toman"]

CurrencyCode = Literal["TMN", "IRR"]

#: ISO-4217 code of the unit the ``*_toman`` fields are expressed in.
TOMAN = CURRENCY_TOMAN
#: ISO-4217 code of the unit the raw price fields keep.
RIAL = CURRENCY_RIAL


def currency_field(*, description: str | None = None) -> Any:
    """Return the ``currency`` field shared by price-bearing schemas.

    Defaults to toman: everything this API shows a human is denominated in TMN.
    """
    return Field(
        default=CURRENCY_TOMAN,
        description=description
        or "واحد پول مقادیر نمایشی (تومان — TMN)",
        examples=[CURRENCY_TOMAN],
    )


def toman(value: Decimal | int | float | str | None) -> float:
    """Presentation helper: rial amount → toman, ``None`` → ``0.0``."""
    return rial_to_toman_float(value) or 0.0
