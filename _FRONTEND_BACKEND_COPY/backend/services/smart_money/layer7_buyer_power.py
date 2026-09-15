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


class BuyerPowerLayer:
    def compute(self, quote: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, float]:
        ab = quote.get("avg_buy", 0.0) or 1.0
        as_ = quote.get("avg_sell", 0.0) or 1.0
        rbv = quote.get("real_buy_value", 0.0) or 0.0
        rsv = quote.get("real_sell_value", 0.0) or 0.0
        rbc = quote.get("real_buy_count", 1) or 1
        rsc = quote.get("real_sell_count", 1) or 1
        val = quote.get("value", 0) or 1

        vol_ratio = ab / as_ if as_ else 1.0
        val_ratio = rbv / rsv if rsv else 1.0
        count_ratio = rbc / rsc if rsc else 1.0

        rbp_val = (val_ratio + vol_ratio + count_ratio) / 3.0
        rbp_n = norm(rbp_val, 0.8, 3.0)

        hist_rbp: list[float] = []
        hist_val_ratio: list[float] = []
        for q in history:
            hab = q.get("avg_buy", 0.0) or 1.0
            has_ = q.get("avg_sell", 0.0) or 1.0
            hrbv = q.get("real_buy_value", 0.0) or 1.0
            hrsv = q.get("real_sell_value", 0.0) or 1.0
            hrbc = q.get("real_buy_count", 1) or 1
            hrsc = q.get("real_sell_count", 1) or 1
            hvr = hab / has_ if has_ else 1.0
            hvar = hrbv / hrsv if hrsv else 1.0
            hcr = hrbc / hrsc if hrsc else 1.0
            hist_rbp.append((hvr + hvar + hcr) / 3.0)
            hist_val_ratio.append(hvar)

        mu_rbp, std_rbp = _zscore(hist_rbp) if hist_rbp else (1.0, 1.0)
        z_rbp = (rbp_val - mu_rbp) / std_rbp if std_rbp else 0.0
        z_rbp_n = norm(z_rbp, 1.5, 4.0)

        mu_vr, std_vr = _zscore(hist_val_ratio) if hist_val_ratio else (1.0, 1.0)
        z_vr = (val_ratio - mu_vr) / std_vr if std_vr else 0.0
        z_vr_n = norm(z_vr, 1.5, 4.0)

        hist_pc: list[float] = (
            [q.get("real_buy_value", 0.0) / max(q.get("real_buy_count", 1), 1) for q in history] if history else [0.0]
        )
        mu_pc, std_pc = _zscore(hist_pc)
        pc_today = rbv / rbc if rbc else 0.0
        z_pc = (pc_today - mu_pc) / std_pc if std_pc else 0.0
        z_pc_n = norm(z_pc, 1.5, 4.0)

        hist_nrmf: list[float] = []
        for q in history:
            hrbv = q.get("real_buy_value", 0.0) or 0.0
            hrsv = q.get("real_sell_value", 0.0) or 0.0
            hval = q.get("value", 0) or 1
            hist_nrmf.append((hrbv - hrsv) / hval if hval else 0.0)
        nrmf_today = (rbv - rsv) / val if val else 0.0
        mu_nrmf, std_nrmf = _zscore(hist_nrmf) if hist_nrmf else (0.0, 1.0)
        z_nrmf = (nrmf_today - mu_nrmf) / std_nrmf if std_nrmf else 0.0
        z_nrmf_n = norm(z_nrmf, 1.0, 3.0)

        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        rt = (c - o) / o if o else 0.0
        amihud = abs(rt) / val if val else 0.0
        hist_amihud: list[float] = []
        for q in history:
            hc = q.get("price_close", 0.0)
            ho = q.get("price_open", 0.0)
            hv = q.get("value", 0) or 1
            hrt = (hc - ho) / ho if ho else 0.0
            hist_amihud.append(abs(hrt) / hv if hv else 0.0)
        mu_am, std_am = _zscore(hist_amihud) if hist_amihud else (0.0, 1.0)
        z_am = (amihud - mu_am) / std_am if std_am else 0.0
        z_am_n = 1.0 - norm(z_am, -0.5, 2.0)

        bp_score = 0.25 * rbp_n + 0.20 * z_rbp_n + 0.15 * z_vr_n + 0.15 * z_pc_n + 0.15 * z_nrmf_n + 0.10 * z_am_n

        return {
            "bps": min(1.0, max(0.0, bp_score)),
            "rbp_n": rbp_n,
            "z_rbp_n": z_rbp_n,
            "z_vr_n": z_vr_n,
            "z_pc_n": z_pc_n,
            "z_nrmf_n": z_nrmf_n,
            "z_am_n": z_am_n,
        }
