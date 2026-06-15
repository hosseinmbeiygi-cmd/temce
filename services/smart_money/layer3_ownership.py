from __future__ import annotations

from typing import Any

from services.smart_money.normalizer import MinMaxClipped

norm = MinMaxClipped()


class OwnershipLayer:
    def compute(
        self, quote: dict[str, Any], history: list[dict[str, Any]], trades: list[dict[str, Any]] | None = None
    ) -> dict[str, float]:
        quote.get("volume", 0) or 1
        vt = quote.get("value", 0) or 1

        vols_20 = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]
        avg_vol_20 = sum(vols_20) / len(vols_20)
        vols_5 = [q.get("volume", 0) or 1 for q in history[-5:]] or [1]
        avg_vol_5 = sum(vols_5) / len(vols_5)

        avg_buy = quote.get("avg_buy", 0.0) or 0.0
        avg_sell = quote.get("avg_sell", 0.0) or 0.0
        real_buy = quote.get("real_buy_value", 0.0) or 0.0
        real_sell = quote.get("real_sell_value", 0.0) or 0.0
        quote.get("real_buy_count", 1) or 1
        sell_count = quote.get("real_sell_count", 1) or 1
        avg_buy_20 = self._avg_ma(history, "avg_buy", 20) or avg_buy or 1.0

        bp = avg_buy / avg_sell if avg_sell else 1.0
        bp_n = norm(bp, 0.8, 3.0)

        nrmf = real_buy - real_sell
        nrmf_r = nrmf / vt if vt else 0.0
        nrmf_n = norm(nrmf_r, -0.2, 0.4)

        bc = avg_buy / avg_buy_20 if avg_buy_20 else 1.0
        bc_n = norm(bc, 1.0, 3.0)

        se = sell_count / avg_sell if avg_sell else 1.0
        se_n = 1.0 - norm(se, 0.5, 2.0)

        fd = 1.0 - norm(avg_vol_5 / avg_vol_20 if avg_vol_20 else 1.0, 0.8, 1.5)

        fls = 0.20 * bp_n + 0.18 * nrmf_n + 0.14 * bc_n + 0.14 * se_n + 0.16 * fd + 0.18 * (bp_n + nrmf_n) / 2

        return {
            "fls": min(1.0, max(0.0, fls)),
            "bp_n": bp_n,
            "nrmf_n": nrmf_n,
            "bc_n": bc_n,
            "se_n": se_n,
            "fd": fd,
        }

    @staticmethod
    def _avg_ma(history: list[dict[str, Any]], key: str, period: int) -> float:
        vals = [q.get(key, 0.0) or 0.0 for q in history[-period:]]
        return sum(vals) / len(vals) if vals else 0.0
