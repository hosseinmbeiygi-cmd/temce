from __future__ import annotations

from typing import Any

import numpy as np

from services.smart_money.normalizer import MinMaxClipped
from services.smart_money.stats import extract_columns, nz_or_one, open_return

norm = MinMaxClipped()


class MicrostructureLayer:
    def compute(self, quote: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, float]:
        ab = quote.get("avg_buy", 0.0) or 1.0
        as_ = quote.get("avg_sell", 0.0) or 1.0
        v = quote.get("volume", 0) or 1
        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        h = quote.get("price_high", 0.0)
        low = quote.get("price_low", 0.0)

        n = len(history)
        if n:
            # ── Single extraction pass over history (all columns at once) ──
            col = extract_columns(history, {
                "avg_buy": 0.0, "avg_sell": 0.0, "volume": 0,
                "price_close": 0.0, "price_open": 0.0,
            })
            ab_h, as_h = col["avg_buy"], col["avg_sell"]
            vol_h = col["volume"]

            # ── VPIN: imbalance mean over the last 10 rows ──
            # (legacy built imbalances for the FULL history but consumed only [-10:])
            win = slice(max(n - 10, 0), None)
            hab = nz_or_one(ab_h[win])
            has_ = nz_or_one(as_h[win])
            denom = hab + has_
            imb = np.where(denom != 0.0, np.abs(hab - has_) / np.where(denom != 0.0, denom, 1.0), 0.0)
            vpin = float(imb.sum() / imb.size)

            # ── Up/down volume split over the last 5 rows ──
            qc5 = col["price_close"][-5:]
            qo5 = col["price_open"][-5:]
            qv5 = vol_h[-5:]
            up_mask5 = qc5 >= qo5
            up_vol_5 = float(qv5[up_mask5].sum())
            dn_vol_5 = float(qv5[~up_mask5].sum())

            # ── Down/up volume magnitudes (parity-safe branch semantics) ──
            qrt = open_return(col["price_close"], col["price_open"])
            vol_safe = nz_or_one(vol_h)
            down_mask = qrt < 0
            # Down rows (qrt<0): legacy qv/abs(qrt) — no clamp (abs>0 guaranteed there).
            # Up rows: qrt>0 → qv/max(qrt, 0.001); qrt==0 → legacy qv*100.
            qrt_abs = np.abs(qrt)
            mag_down = vol_safe / np.where(qrt_abs > 0.0, qrt_abs, 1.0)
            mag_up = np.where(qrt > 0.0, vol_safe / np.maximum(qrt, 0.001), vol_safe * 100.0)
            mag = np.where(down_mask, mag_down, mag_up)
            n_dn = int(down_mask.sum())
            n_up = n - n_dn
            avg_dpv = float(mag[down_mask].sum() / n_dn) if n_dn else 0.0
            avg_upv = float(mag[~down_mask].sum() / n_up) if n_up else 1.0

            vols_20 = nz_or_one(vol_h[-20:])
            avg_vol_20 = float(vols_20.sum() / vols_20.size)
        else:
            # Legacy empty-history defaults
            vpin = 0.0
            avg_dpv = 0.0
            avg_upv = 1.0
            up_vol_5 = 0.0
            dn_vol_5 = 0.0
            avg_vol_20 = 1.0

        abs_refined = avg_dpv / avg_upv if avg_upv else 0.0
        abs_n = norm(abs_refined, 0.8, 3.0)
        vpin_n = norm(vpin, 0.1, 0.6)

        rt = (c - o) / o if o else 0.0
        dps = (v / avg_vol_20 / abs(rt) if abs(rt) > 0 else 0.0) if rt < 0 else 0.0
        dps_n = norm(dps, 20.0, 300.0)

        dry_ratio = up_vol_5 / max(dn_vol_5, 1)
        dry_n = norm(dry_ratio, 0.5, 3.0)

        ratio = v / avg_vol_20 if avg_vol_20 else 1.0
        sell_shock = ratio if rt < 0 else 0.0
        shock_absorption = sell_shock / (abs(rt) + 0.0001) if rt < 0 else 0.0
        sa_n = norm(shock_absorption, 20.0, 300.0)

        mcs = 0.25 * vpin_n + 0.22 * abs_n + 0.18 * dps_n + 0.18 * dry_n + 0.17 * sa_n

        return {
            "mcs": float(min(1.0, max(0.0, mcs))),
            "vpin_n": float(vpin_n),
            "abs_n": float(abs_n),
            "dpsv_n": float(dps_n),
            "dry_n": float(dry_n),
            "sa_n": float(sa_n),
        }
