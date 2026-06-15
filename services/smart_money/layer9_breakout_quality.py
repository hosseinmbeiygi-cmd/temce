from __future__ import annotations

from typing import Any

from services.smart_money.normalizer import MinMaxClipped

norm = MinMaxClipped()


def _zscore(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    if n < 2:
        return 0.0, 1.0
    mu = sum(vals) / n
    var = sum((x - mu) ** 2 for x in vals) / (n - 1)
    std = var**0.5 or 1.0
    return mu, std


class BreakoutQualityLayer:
    def compute(
        self, quote: dict[str, Any], history: list[dict[str, Any]], layer_scores: dict[str, float]
    ) -> dict[str, float]:
        c = quote.get("price_close", 0.0)
        h = quote.get("price_high", 0.0)
        low = quote.get("price_low", 0.0)
        o = quote.get("price_open", 0.0)
        v = quote.get("volume", 0) or 1

        vols = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]
        avg_vol_20 = sum(vols) / len(vols)
        _, std_vol = _zscore(vols)
        z_vol = (v - avg_vol_20) / std_vol if std_vol else 0.0
        z_vol_n = norm(z_vol, 0.5, 3.0)

        [q.get("price_close", 0.0) for q in history[-20:]] + [c]
        highs_20 = [q.get("price_high", 0.0) for q in history[-20:]]
        res20 = max(highs_20) if highs_20 else h
        support20 = min(q.get("price_low", 0.0) for q in history[-20:]) if history[-20:] else low

        rng = h - low
        clv = ((c - low) - (h - c)) / rng if rng else 0.0
        clv_n = (clv + 1) / 2

        dist_res = (res20 - c) / max(res20, 1)
        rp_n = norm(1.0 - dist_res, 0.90, 1.0)

        ret = (c - o) / o if o else 0.0
        rv_ratio = abs(ret) / (v / max(avg_vol_20, 1)) if (v / max(avg_vol_20, 1)) else 0.0
        eff_n = 1.0 - norm(rv_ratio, 0.005, 0.03)

        touches = sum(1 for q in history[-10:] if q.get("price_high", 0.0) >= 0.97 * res20)
        btf_n = min(touches / 5.0, 1.0)

        close_vals = [q.get("price_close", 0.0) for q in history[-5:]]
        low_vals = [q.get("price_low", 0.0) for q in history[-5:]]
        pullback_pct = (max(close_vals) - min(low_vals)) / max(avg_vol_20 / max(c, 1), 1) if c else 0.0
        pt_n = 1.0 - norm(pullback_pct, 0.5, 3.0)

        rngs_20 = [q.get("price_high", 0.0) - q.get("price_low", 0.0) for q in history[-20:]] or [1]
        atr20 = sum(rngs_20) / len(rngs_20)
        dist_res_atr = (res20 - c) / max(atr20, 1) if atr20 else 1.0
        pt2_n = 1.0 - norm(dist_res_atr, 0.5, 3.0)

        acceptance = 1.0 if (c >= res20 * 0.995 and v > avg_vol_20 * 1.2) else 0.0
        post_accept = 1.0 if (len(history) >= 2 and history[-1].get("price_close", 0.0) >= res20 * 0.995) else 0.0
        accept_n = (acceptance + post_accept) / 2.0

        ess = layer_scores.get("ess", 0.0)
        rrs = layer_scores.get("rrs", 0.0)
        abs_ = layer_scores.get("abs", 0.0)
        fls = layer_scores.get("fls", 0.0)
        pvs = layer_scores.get("pvs", 0.0)
        bcp = (ess + rrs + abs_ + fls + pvs) / 5

        bqs = (
            0.18 * rp_n
            + 0.14 * z_vol_n
            + 0.12 * clv_n
            + 0.10 * eff_n
            + 0.10 * btf_n
            + 0.10 * pt_n
            + 0.08 * pt2_n
            + 0.08 * accept_n
            + 0.10 * bcp
        )

        dist_sup = (c - support20) / max(support20, 1) if support20 else 0.0
        lvr = dist_sup / max(dist_res + 0.001, 0.001)
        norm(lvr, 1.0, 10.0)

        return {
            "bqs": min(1.0, max(0.0, bqs)),
            "rp_n": rp_n,
            "z_vol_n": z_vol_n,
            "eff_n": eff_n,
            "btf_n": btf_n,
            "pt_n": pt_n,
            "accept_n": accept_n,
            "bcp": bcp,
        }
