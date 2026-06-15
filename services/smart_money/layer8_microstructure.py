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


class MicrostructureLayer:
    def compute(self, quote: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, float]:
        ab = quote.get("avg_buy", 0.0) or 1.0
        as_ = quote.get("avg_sell", 0.0) or 1.0
        v = quote.get("volume", 0) or 1
        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        h = quote.get("price_high", 0.0)
        low = quote.get("price_low", 0.0)
        quote.get("value", 0) or 1

        vols_20 = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]
        avg_vol_20 = sum(vols_20) / len(vols_20)

        abs(ab - as_) / (ab + as_) if (ab + as_) else 0.0
        hist_imb: list[float] = []
        for q in history:
            hab = q.get("avg_buy", 0.0) or 1.0
            has_ = q.get("avg_sell", 0.0) or 1.0
            hist_imb.append(abs(hab - has_) / (hab + has_) if (hab + has_) else 0.0)
        vpin = sum(hist_imb[-10:]) / max(len(hist_imb[-10:]), 1) if hist_imb else 0.0
        vpin_n = norm(vpin, 0.1, 0.6)

        rt = (c - o) / o if o else 0.0
        dpv: list[float] = []
        upv: list[float] = []
        for q in history:
            qc = q.get("price_close", 0.0)
            qo = q.get("price_open", 0.0)
            qrt = (qc - qo) / qo if qo else 0.0
            qv = q.get("volume", 0) or 1
            if qrt < 0:
                dpv.append(qv / abs(qrt) if abs(qrt) > 0 else qv * 100)
            else:
                upv.append(qv / max(qrt, 0.001) if qrt > 0 else qv * 100)
        avg_dpv = sum(dpv) / len(dpv) if dpv else 0.0
        avg_upv = sum(upv) / len(upv) if upv else 1.0
        abs_refined = avg_dpv / avg_upv if avg_upv else 0.0
        abs_n = norm(abs_refined, 0.8, 3.0)

        dps = (v / avg_vol_20 / abs(rt) if abs(rt) > 0 else 0.0) if rt < 0 else 0.0
        dps_n = norm(dps, 20.0, 300.0)

        up_vol_5 = sum(
            q.get("volume", 0) or 0
            for q in history[-5:]
            if (q.get("price_close", 0) or 0) >= (q.get("price_open", 0) or 0)
        )
        dn_vol_5 = sum(
            q.get("volume", 0) or 0
            for q in history[-5:]
            if (q.get("price_close", 0) or 0) < (q.get("price_open", 0) or 0)
        )
        dry_ratio = up_vol_5 / max(dn_vol_5, 1)
        dry_n = norm(dry_ratio, 0.5, 3.0)

        rng = h - low
        ((c - low) - (h - c)) / rng if rng else 0.0

        ratio = v / avg_vol_20 if avg_vol_20 else 1.0
        sell_shock = ratio if rt < 0 else 0.0
        shock_absorption = sell_shock / (abs(rt) + 0.0001) if rt < 0 else 0.0
        sa_n = norm(shock_absorption, 20.0, 300.0)

        mcs = 0.25 * vpin_n + 0.22 * abs_n + 0.18 * dps_n + 0.18 * dry_n + 0.17 * sa_n

        return {
            "mcs": min(1.0, max(0.0, mcs)),
            "vpin_n": vpin_n,
            "abs_n": abs_n,
            "dpsv_n": dps_n,
            "dry_n": dry_n,
            "sa_n": sa_n,
        }
