"""تعریف هم‌گروه (Peer Group).

محور اول — نوع صندوق (اجباری): EQ/FI/GO/MX/LV/RE/IDX/FOF/SEC/GUA/VC/PE
محور دوم — باند AUM (اختیاری): S/M/L

قانون: صدک‌بندی ابتدا بر اساس نوع. اگر تعداد هم‌نوع در یک باند AUM کمتر از ۱۰
باشد، باندبندی نادیده گرفته شده و صدک روی کل هم‌نوع‌ها محاسبه می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import AUM_BAND_THRESHOLDS_BTOMAN
from .metrics.helpers import percentile_rank


def aum_band(aum_btoman: float | None) -> str | None:
    """تعیین باند AUM از روی دارایی (میلیارد تومان)."""
    if aum_btoman is None:
        return None
    for band, (lo, hi) in AUM_BAND_THRESHOLDS_BTOMAN.items():
        if (lo is None or aum_btoman >= lo) and (hi is None or aum_btoman < hi):
            return band
    return None


@dataclass
class PeerContext:
    """هم‌گروه‌بندی یک صندوق."""

    symbol: str
    type_code: str
    aum_band: str | None
    peers: list[str]  # نمادهای هم‌گروه
    peer_count: int
    used_aum_band: bool  # آیا باند AUM اعمال شد؟


def build_peer_context(
    symbol: str,
    type_code: str,
    aum_btoman: float | None,
    all_funds: list[dict[str, Any]],
    min_peers_for_band: int = 10,
) -> PeerContext:
    """ساخت هم‌گروه برای یک صندوق.

    all_funds: [{symbol, type_code, aum_btoman}, ...]
    """
    same_type = [f for f in all_funds if f["type_code"] == type_code]
    band = aum_band(aum_btoman)

    # محور دوم (AUM band) اختیاری — اگر هم‌نوع‌های این باند کمتر از حد بودند،
    # باند نادیده گرفته می‌شود
    used_band = False
    if band is not None:
        band_peers = [f for f in same_type if aum_band(f.get("aum_btoman")) == band]
        if len(band_peers) >= min_peers_for_band:
            same_type = band_peers
            used_band = True

    peers = [f["symbol"] for f in same_type if f["symbol"] != symbol]
    return PeerContext(
        symbol=symbol,
        type_code=type_code,
        aum_band=band if used_band else None,
        peers=peers,
        peer_count=len(peers),
        used_aum_band=used_band,
    )


def peer_percentiles(
    self_value: float | None,
    peer_values: list[float],
    *,
    min_peers: int = 3,
) -> float | None:
    """صدک مقدار در بین هم‌گروه.

    اگر peer_values کمتر از min_peers باشد → None (هم‌گروه ناکافی).
    """
    if self_value is None:
        return None
    if len(peer_values) < min_peers:
        return None
    return percentile_rank(self_value, peer_values)


def sufficient_peers(peer_values: list[float], *, min_peers: int = 3) -> bool:
    return len(peer_values) >= min_peers
