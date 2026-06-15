from __future__ import annotations

from typing import Any

from services.smart_money.normalizer import MinMaxClipped

norm = MinMaxClipped()


class CompressionLayer:
    def compute(self, quote: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, float]:
        h = quote.get("price_high", 0.0)
        low = quote.get("price_low", 0.0)
        quote.get("price_close", 0.0)
        v = quote.get("volume", 0) or 1

        ranges = [q.get("price_high", 0.0) - q.get("price_low", 0.0) for q in history[-20:]] or [1]
        avg_range = sum(ranges) / len(ranges)
        rc = 1.0 - norm((h - low) / avg_range if avg_range else 1.0, 0.8, 1.4)

        atr5 = self._atr(history[-5:])
        atr20 = self._atr(history[-20:]) or atr5 or 1.0
        atrc = 1.0 - norm(atr5 / atr20 if atr20 else 1.0, 0.8, 1.3)

        vols_5 = [q.get("volume", 0) or 1 for q in history[-5:]] or [1]
        vols_20 = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]
        sum(vols_5) / len(vols_5)
        avg_v20 = sum(vols_20) / len(vols_20)
        vtr_n = norm(v / avg_v20 if avg_v20 else 1.0, 0.8, 2.5)
        ipe_n = self._ipe(quote, history)

        vvd = (vtr_n + ipe_n + rc) / 3

        ess = 0.22 * rc + 0.22 * atrc + 0.20 * rc + 0.20 * vvd + 0.16 * rc

        return {
            "ess": min(1.0, max(0.0, ess)),
            "rc": rc,
            "atrc": atrc,
            "vvd": vvd,
        }

    @staticmethod
    def _atr(bars: list[dict[str, Any]]) -> float:
        if not bars:
            return 0.0
        trs = []
        for i, b in enumerate(bars):
            h = b.get("price_high", 0.0)
            low = b.get("price_low", 0.0)
            if i == 0:
                tr = h - low
            else:
                prev_c = bars[i - 1].get("price_close", 0.0)
                tr = max(h - low, abs(h - prev_c), abs(low - prev_c))
            trs.append(tr)
        return sum(trs) / len(trs) if trs else 0.0

    @staticmethod
    def _ipe(quote: dict[str, Any], history: list[dict[str, Any]]) -> float:
        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        vt = quote.get("value", 0) or 1
        ret = (c - o) / o if o else 0.0
        vals_20 = [q.get("value", 0) or 1 for q in history[-20:]] or [1]
        avg_val = sum(vals_20) / len(vals_20)
        vtr = vt / avg_val if avg_val else 1.0
        pe = abs(ret) / vtr if vtr else 0.01
        ipe = 1.0 / pe if pe > 0.01 else 10.0
        return 1.0 - norm(ipe, 1.0, 10.0)
