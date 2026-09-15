from __future__ import annotations

from typing import Any

from services.smart_money.normalizer import MinMaxClipped

norm = MinMaxClipped()


class AbsorptionLayer:
    def compute(
        self, quote: dict[str, Any], history: list[dict[str, Any]], index_return: float = 0.0
    ) -> dict[str, float]:
        v = quote.get("volume", 0) or 1
        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        h = quote.get("price_high", 0.0)
        low = quote.get("price_low", 0.0)
        ret = (c - o) / o if o else 0.0

        vols_20 = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]
        avg_vol = sum(vols_20) / len(vols_20)
        rvol = v / avg_vol if avg_vol else 1.0

        ret_neg = min(0.0, ret)
        dps = rvol / (abs(ret_neg) + 1e-6) if ret_neg < 0 else 0.0
        dps_n = norm(dps, 20.0, 300.0)

        lss = (min(o, c) - low) / (h - low) if (h - low) else 0.5
        lss_n = lss

        rmr = ret - index_return
        rmr_n = norm(rmr, -0.02, 0.03)

        rec = (c - low) / (h - low) if (h - low) else 0.5

        abs_score = 0.35 * dps_n + 0.20 * lss_n + 0.25 * rmr_n + 0.20 * rec

        return {
            "abs": min(1.0, max(0.0, abs_score)),
            "dps_n": dps_n,
            "lss_n": lss_n,
            "rmr_n": rmr_n,
        }
