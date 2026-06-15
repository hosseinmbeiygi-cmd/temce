from __future__ import annotations

from typing import Any

from services.smart_money.normalizer import MinMaxClipped

norm = MinMaxClipped()


class BreakoutLayer:
    def compute(
        self, quote: dict[str, Any], history: list[dict[str, Any]], layer_scores: dict[str, float]
    ) -> dict[str, float]:
        c = quote.get("price_close", 0.0)
        h = quote.get("price_high", 0.0)
        quote.get("price_low", 0.0)

        highs_20 = [q.get("price_high", 0.0) for q in history[-20:]] or [h]
        res20 = max(highs_20)

        rp = 1.0 - (res20 - c) / res20 if res20 else 0.0
        rp_n = norm(rp, 0.95, 1.0)

        bt_count = sum(1 for q in history[-10:] if q.get("price_close", 0.0) > 0.97 * res20)
        btf_n = norm(float(bt_count), 1.0, 5.0)

        last5_closes = [q.get("price_close", 0.0) for q in history[-5:]] + [c]
        min_last5 = min(last5_closes)
        ranges_20 = [q.get("price_high", 0.0) - q.get("price_low", 0.0) for q in history[-20:]] or [1]
        atr20 = sum(ranges_20) / len(ranges_20) if ranges_20 else 1.0
        pt = 1.0 - norm((res20 - min_last5) / atr20 if atr20 else 1.0, 0.5, 3.0)

        ess = layer_scores.get("ess", 0.0)
        rrs = layer_scores.get("rrs", 0.0)
        abs_score = layer_scores.get("abs", 0.0)
        layer_scores.get("fls", 0.0)
        bcp = (ess + rrs + abs_score) / 3

        brs = 0.20 * rp_n + 0.18 * btf_n + 0.18 * pt + 0.20 * (_ipe_n := self._ipe_n(quote, history)) + 0.24 * bcp

        return {
            "brs": min(1.0, max(0.0, brs)),
            "rp_n": rp_n,
            "btf_n": btf_n,
            "pt": pt,
            "bcp": bcp,
        }

    @staticmethod
    def _ipe_n(quote: dict[str, Any], history: list[dict[str, Any]]) -> float:
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
