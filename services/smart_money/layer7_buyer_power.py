from __future__ import annotations

from typing import Any

import numpy as np

from services.smart_money.normalizer import MinMaxClipped
from services.smart_money.stats import extract_columns, nz_or_one, open_return, zscore

norm = MinMaxClipped()


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

        n = len(history)
        if n:
            # ── Single extraction pass over history (all columns at once) ──
            col = extract_columns(history, {
                "avg_buy": 0.0, "avg_sell": 0.0,
                "real_buy_value": 0.0, "real_sell_value": 0.0,
                "real_buy_count": 1, "real_sell_count": 1,
                "value": 0, "price_close": 0.0, "price_open": 0.0,
            })
            ab_h, as_h = col["avg_buy"], col["avg_sell"]
            rbv_h, rsv_h = col["real_buy_value"], col["real_sell_value"]
            rbc_h, rsc_h = col["real_buy_count"], col["real_sell_count"]
            val_h = col["value"]

            # ── Vectorized derived series (legacy `or` semantics preserved;
            #    one stacked where instead of per-array calls) ──
            Z = np.vstack([ab_h, as_h, rbv_h, rsv_h, rbc_h, rsc_h, val_h])
            Z = np.where(Z != 0.0, Z, 1.0)
            ab1, as1, rbv1, rsv1, rbc1, rsc1, val1 = Z
            hvr = ab1 / as1
            hvar = rbv1 / rsv1
            hcr = rbc1 / rsc1
            hist_rbp = (hvr + hvar + hcr) / 3.0

            hist_pc = rbv_h / np.maximum(rbc_h, 1.0)          # legacy max(count, 1) — raw numerator
            hist_nrmf = (rbv_h - rsv_h) / val1                # raw numerators, `or 1` denominator
            hist_amihud = np.abs(open_return(col["price_close"], col["price_open"])) / val1

            if n >= 2:
                # Stacked stats: all five series in one (5, n) matrix →
                # two NumPy reductions total instead of ten.
                S = np.vstack([hist_rbp, hvar, hist_pc, hist_nrmf, hist_amihud])
                mus = S.mean(axis=1)
                stds = S.std(axis=1, ddof=1)
                stds = np.where(stds != 0.0, stds, 1.0)
                mu_rbp, mu_vr, mu_pc, mu_nrmf, mu_am = (float(x) for x in mus)
                std_rbp, std_vr, std_pc, std_nrmf, std_am = (float(x) for x in stds)
            else:
                mu_rbp, std_rbp = zscore(hist_rbp)
                mu_vr, std_vr = zscore(hvar)
                mu_pc, std_pc = zscore(hist_pc)
                mu_nrmf, std_nrmf = zscore(hist_nrmf)
                mu_am, std_am = zscore(hist_amihud)
        else:
            # Legacy empty-history defaults (mu=1.0 for rbp/vr z-scores)
            mu_rbp, std_rbp = 1.0, 1.0
            mu_vr, std_vr = 1.0, 1.0
            mu_pc, std_pc = 0.0, 1.0
            mu_nrmf, std_nrmf = 0.0, 1.0
            mu_am, std_am = 0.0, 1.0

        z_rbp = (rbp_val - mu_rbp) / std_rbp if std_rbp else 0.0
        z_rbp_n = norm(z_rbp, 1.5, 4.0)

        z_vr = (val_ratio - mu_vr) / std_vr if std_vr else 0.0
        z_vr_n = norm(z_vr, 1.5, 4.0)

        pc_today = rbv / rbc if rbc else 0.0
        z_pc = (pc_today - mu_pc) / std_pc if std_pc else 0.0
        z_pc_n = norm(z_pc, 1.5, 4.0)

        nrmf_today = (rbv - rsv) / val if val else 0.0
        z_nrmf = (nrmf_today - mu_nrmf) / std_nrmf if std_nrmf else 0.0
        z_nrmf_n = norm(z_nrmf, 1.0, 3.0)

        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        rt = (c - o) / o if o else 0.0
        amihud = abs(rt) / val if val else 0.0
        z_am = (amihud - mu_am) / std_am if std_am else 0.0
        z_am_n = 1.0 - norm(z_am, -0.5, 2.0)

        bp_score = 0.25 * rbp_n + 0.20 * z_rbp_n + 0.15 * z_vr_n + 0.15 * z_pc_n + 0.15 * z_nrmf_n + 0.10 * z_am_n

        return {
            "bps": float(min(1.0, max(0.0, bp_score))),
            "rbp_n": float(rbp_n),
            "z_rbp_n": float(z_rbp_n),
            "z_vr_n": float(z_vr_n),
            "z_pc_n": float(z_pc_n),
            "z_nrmf_n": float(z_nrmf_n),
            "z_am_n": float(z_am_n),
        }
