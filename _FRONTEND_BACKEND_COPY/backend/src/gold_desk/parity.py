"""Parity check — شکاف درهم امارات با دلار تهران.

اگر دلار آزاد > درهم × 3.6725 → دلار گران‌تر (پتانسیل ریزش).
اگر دلار آزاد < درهم × 3.6725 → دلار ارزان‌تر (پتانسیل رشد).
"""

from __future__ import annotations

from .constants import AED_PEG


def aed_parity_usd(aed_irt: float) -> float:
    """دلار تعادلی بر اساس حواله درهم."""
    if aed_irt <= 0:
        raise ValueError(f"invalid aed_irt: {aed_irt}")
    return aed_irt * AED_PEG


def aed_gap_pct(usd_irt: float, aed_irt: float) -> float:
    """درصد شکاف دلار آزاد از درهم.

    مثبت = دلار آزاد گران‌تر.
    منفی = دلار آزاد ارزان‌تر.
    """
    parity = aed_parity_usd(aed_irt)
    return ((usd_irt - parity) / parity * 100.0) if parity else 0.0
