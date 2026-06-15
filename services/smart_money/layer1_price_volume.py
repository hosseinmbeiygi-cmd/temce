from __future__ import annotations

from typing import Any

from services.smart_money.normalizer import MinMaxClipped

norm = MinMaxClipped()


class PriceVolumeLayer:
    def compute(
        self, quote: dict[str, Any], history: list[dict[str, Any]], index_return: float = 0.0
    ) -> dict[str, float]:
        vt = quote.get("value", 0) or 1
        v = quote.get("volume", 0) or 1
        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        h = quote.get("price_high", 0.0)
        low = quote.get("price_low", 0.0)
        last = quote.get("price_last", c)

        values_20 = [q.get("value", 0) or 1 for q in history[-20:]] or [1]
        vols_20 = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]

        avg_value = sum(values_20) / len(values_20)
        avg_vol = sum(vols_20) / len(vols_20)

        rvol = v / avg_vol if avg_vol else 1.0
        vtr = vt / avg_value if avg_value else 1.0

        rvol_n = norm(rvol, 0.8, 2.5)
        vtr_n = norm(vtr, 0.8, 2.5)

        clv = self._clv(c, h, low)
        clv_n = (clv + 1) / 2

        rec = self._recovery(c, low, h)
        rec_n = rec

        ret = (c - o) / o if o else 0.0
        pe = abs(ret) / vtr if vtr else 0.01
        ipe = 1.0 / pe if pe > 0.01 else 10.0
        ipe_n = 1.0 - norm(ipe, 1.0, 10.0)

        lf = (last - c) / c if c else 0.0
        lf_n = norm(lf, -0.01, 0.02)

        pvs = 0.20 * rvol_n + 0.20 * vtr_n + 0.15 * clv_n + 0.15 * rec_n + 0.15 * ipe_n + 0.15 * lf_n

        return {
            "pvs": min(1.0, max(0.0, pvs)),
            "rvol_n": rvol_n,
            "vtr_n": vtr_n,
            "clv_n": clv_n,
            "rec_n": rec_n,
            "ipe_n": ipe_n,
            "lf_n": lf_n,
        }

    @staticmethod
    def _clv(c: float, h: float, low: float) -> float:
        r = h - low
        if r == 0:
            return 0.0
        return ((c - low) - (h - c)) / r

    @staticmethod
    def _recovery(c: float, low: float, h: float) -> float:
        r = h - low
        if r == 0:
            return 0.5
        return (c - low) / r
