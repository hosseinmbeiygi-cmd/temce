from __future__ import annotations

from typing import Any

from services.smart_money.layer1_price_volume import PriceVolumeLayer
from services.smart_money.layer2_absorption import AbsorptionLayer
from services.smart_money.layer3_ownership import OwnershipLayer
from services.smart_money.layer4_compression import CompressionLayer
from services.smart_money.layer5_relative_strength import RelativeStrengthLayer
from services.smart_money.layer6_breakout import BreakoutLayer
from services.smart_money.layer7_buyer_power import BuyerPowerLayer
from services.smart_money.layer8_microstructure import MicrostructureLayer
from services.smart_money.layer9_breakout_quality import BreakoutQualityLayer


class ScoringEngine:
    def __init__(self) -> None:
        self.layer1 = PriceVolumeLayer()
        self.layer2 = AbsorptionLayer()
        self.layer3 = OwnershipLayer()
        self.layer4 = CompressionLayer()
        self.layer5 = RelativeStrengthLayer()
        self.layer6 = BreakoutLayer()
        self.layer7 = BuyerPowerLayer()
        self.layer8 = MicrostructureLayer()
        self.layer9 = BreakoutQualityLayer()

    def analyze(
        self,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
        trades: list[dict[str, Any]] | None = None,
        index_history: list[float] | None = None,
        sector_history: list[float] | None = None,
    ) -> dict[str, Any]:
        # ---- Layer computations ----
        l1 = self.layer1.compute(quote, history)
        l2 = self.layer2.compute(quote, history, index_return=self._index_return(index_history))
        l3 = self.layer3.compute(quote, history, trades)
        l4 = self.layer4.compute(quote, history)
        l5 = self.layer5.compute(quote, history, index_history, sector_history)
        l7 = self.layer7.compute(quote, history)
        l8 = self.layer8.compute(quote, history)

        all_layer = {**l1, **l2, **l3, **l4, **l5, **l7, **l8}
        l6 = self.layer6.compute(quote, history, all_layer)
        l9 = self.layer9.compute(quote, history, all_layer)

        # ----  Layer scores ----
        pvs = l1["pvs"]
        abs_score = l2["abs"]
        fls = l3["fls"]
        ess = l4["ess"]
        rrs = l5["rrs"]
        brs = l6["brs"]
        bps = l7["bps"]
        mcs = l8["mcs"]

        # ---- Individual normalized features ----
        bp_n = l3.get("bp_n", 0.0)
        nrmf_n = l3.get("nrmf_n", 0.0)
        bc_n = l3.get("bc_n", 0.0)
        dps_n = l2.get("dps_n", 0.0)
        rmr_n = l2.get("rmr_n", 0.0)
        lss_n = l2.get("lss_n", 0.0)
        rec_n = l1.get("rec_n", 0.0)

        # ============================================================
        # AHM — Absorption History Memory: avg of recent ABS scores
        # AHM = 1/k * sum(ABS_t-i)
        # ============================================================
        ahm_vals: list[float] = []
        for q in history[-5:]:
            try:
                ahm_vals.append(
                    self.layer2.compute(q, history, index_return=self._index_return(index_history)).get("abs", 0.0)
                )
            except Exception:
                ahm_vals.append(0.5)
        ahm_n = sum(ahm_vals) / len(ahm_vals) if ahm_vals else 0.5

        # ============================================================
        #  1) Accumulation Score (ACC)
        #  ACC = 0.22*PVS + 0.18*BPn + 0.16*NRMFn + 0.12*BCn
        #        + 0.12*DPSn + 0.10*RMRn + 0.10*RRS
        # ============================================================
        acc = 0.22 * pvs + 0.18 * bp_n + 0.16 * nrmf_n + 0.12 * bc_n + 0.12 * dps_n + 0.10 * rmr_n + 0.10 * rrs

        # ============================================================
        #  2) Absorption Score (ABS_final)
        #  ABSfinal = 0.45*ABS + 0.20*PVS + 0.15*RMRn
        #             + 0.10*LSSn + 0.10*RECn
        # ============================================================
        abs_final = 0.45 * abs_score + 0.20 * pvs + 0.15 * rmr_n + 0.10 * lss_n + 0.10 * rec_n

        # ============================================================
        #  3) Float Lock Score (FL)
        #  FL = 0.40*FLS + 0.25*ESS + 0.20*AHMn + 0.15*RRS
        # ============================================================
        fl = 0.40 * fls + 0.25 * ess + 0.20 * ahm_n + 0.15 * rrs

        # ============================================================
        #  4) Breakout Readiness (BR)
        #  BR = 0.45*BRS + 0.20*ESS + 0.15*RRS
        #       + 0.10*ABS + 0.10*FLS
        # ============================================================
        br = 0.45 * brs + 0.20 * ess + 0.15 * rrs + 0.10 * abs_score + 0.10 * fls

        # ============================================================
        #  5) Smart Money Composite (SMC)
        #  SMC = 0.28*ACC + 0.27*ABSfinal + 0.20*FL + 0.25*BR
        # ============================================================
        smc = 0.28 * acc + 0.27 * abs_final + 0.20 * fl + 0.25 * br

        # ============================================================
        #  Penalties
        # ============================================================

        # DR = 0.40*(1-CLVn) + 0.30*(1-LFn) + 0.30*(1-BPn)
        clv_n = l1.get("clv_n", 0.5)
        lf_n = l1.get("lf_n", 0.5)
        dr = 0.40 * (1.0 - clv_n) + 0.30 * (1.0 - lf_n) + 0.30 * (1.0 - bp_n)

        # FBR = 0.35*(1-RVOLn) + 0.25*(1-RRS) + 0.20*(1-PT) + 0.20*(1-BCP)
        rvol_n = l1.get("rvol_n", 0.5)
        pt = l6.get("pt", 0.5)
        bcp = l6.get("bcp", 0.5)
        fbr = 0.35 * (1.0 - rvol_n) + 0.25 * (1.0 - rrs) + 0.20 * (1.0 - pt) + 0.20 * (1.0 - bcp)

        # DC = 0.40*ESS + 0.30*(1-RRS) + 0.30*(1-NRMFn)
        dc = 0.40 * ess + 0.30 * (1.0 - rrs) + 0.30 * (1.0 - nrmf_n)

        # SMC_adj = SMC - 0.15*DR - 0.10*FBR - 0.10*DC
        smc_adj = smc - 0.15 * dr - 0.10 * fbr - 0.10 * dc
        smc_final = min(1.0, max(0.0, smc_adj))

        # ---- Phase classification (multi-condition) ----
        phase = self._classify_phase(
            acc=acc,
            abs_final=abs_final,
            fl=fl,
            br=br,
            smc=smc_final,
            l2=l2,
            l6=l6,
            ess=ess,
            rrs=rrs,
        )

        # ---- Features dictionary ----
        features: dict[str, float] = {}
        for d in [l1, l2, l3, l4, l5, l6, l7, l8, l9]:
            for k, v in d.items():
                if isinstance(v, float):
                    features[k] = round(v, 4)

        return {
            "smart_money_score": round(smc_final, 4),
            "phase": phase,
            "scores": {
                "accumulation": round(acc, 4),
                "absorption": round(abs_final, 4),
                "float_lock": round(fl, 4),
                "breakout_readiness": round(br, 4),
                "buyer_power": round(bps, 4),
                "microstructure": round(mcs, 4),
            },
            "penalties": {
                "distribution_risk": round(dr, 4),
                "fake_breakout_risk": round(fbr, 4),
                "dead_compression": round(dc, 4),
            },
            "features": features,
            "breakout_features": {k: round(v, 4) for k, v in l6.items() if isinstance(v, float)},
        }

    @staticmethod
    def _classify_phase(
        acc: float,
        abs_final: float,
        fl: float,
        br: float,
        smc: float,
        l2: dict[str, Any],
        l6: dict[str, Any],
        ess: float,
        rrs: float,
    ) -> str:
        """
        Multi-condition phase classification from the mathematical spec.

        Phases (priority order — most advanced checked first):
          1. Confirmed Smart Money   SMC > 0.75, ABSfinal > 0.65, FL > 0.60, BR > 0.65
          2. Breakout Ready          BR > 0.72, RPn > 0.75, ESS > 0.60
          3. Float Lock              FL > 0.70, ESS > 0.65, RRS > 0.55
          4. Active Absorption       ABSfinal > 0.70, RMRn > 0.60, DPSn > 0.65
          5. Early Accumulation      ACC > 0.65, ABSfinal > 0.55, FL < 0.55, BR < 0.55
          6. Neutral                 otherwise
        """
        # 1) Confirmed Smart Money
        if smc > 0.75 and abs_final > 0.65 and fl > 0.60 and br > 0.65:
            return "confirmed_smart_money"

        # 2) Breakout Ready
        rp_n = l6.get("rp_n", 0.0)
        if br > 0.72 and rp_n > 0.75 and ess > 0.60:
            return "breakout_ready"

        # 3) Float Lock Phase
        if fl > 0.70 and ess > 0.65 and rrs > 0.55:
            return "float_lock"

        # 4) Active Absorption
        rmr_n = l2.get("rmr_n", 0.0)
        dps_n = l2.get("dps_n", 0.0)
        if abs_final > 0.70 and rmr_n > 0.60 and dps_n > 0.65:
            return "active_absorption"

        # 5) Early Accumulation
        if acc > 0.65 and abs_final > 0.55 and fl < 0.55 and br < 0.55:
            return "early_accumulation"

        return "neutral"

    @staticmethod
    def _index_return(index_history: list[float] | None) -> float:
        if not index_history or len(index_history) < 2:
            return 0.0
        prev = index_history[-2]
        return (index_history[-1] - prev) / prev if prev else 0.0
