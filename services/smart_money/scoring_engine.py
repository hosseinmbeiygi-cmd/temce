from __future__ import annotations

import time
from typing import Any

from services.smart_money.confidence import ConfidenceEstimator
from services.smart_money.config_loader import (
    SmartMoneyConfig,
    classify_phase_from_config,
    compute_weighted_score,
    load_config,
)
from services.smart_money.data_quality import DataQualityGate, DataQualityReport
from services.smart_money.feature_store import FeatureStore
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
    """Config-driven Smart Money scoring engine with data quality, confidence, and versioning.

    Upgrades from v1:
    - Config-driven weights/thresholds (YAML)
    - Data Quality Gate (rejects bad data)
    - Feature Store (separates computation from scoring)
    - Confidence Score (uncertainty estimation)
    - Engine versioning in output
    - Phase Engine from config (not hard-coded)
    - Partial analysis mode for incomplete data
    """

    def __init__(self, config: SmartMoneyConfig | None = None) -> None:
        self._config = config or load_config()
        self.layer1 = PriceVolumeLayer()
        self.layer2 = AbsorptionLayer()
        self.layer3 = OwnershipLayer()
        self.layer4 = CompressionLayer()
        self.layer5 = RelativeStrengthLayer()
        self.layer6 = BreakoutLayer()
        self.layer7 = BuyerPowerLayer()
        self.layer8 = MicrostructureLayer()
        self.layer9 = BreakoutQualityLayer()

        self._feature_store = FeatureStore()
        self._data_quality_gate = DataQualityGate(self._config.data_quality)
        self._confidence_estimator = ConfidenceEstimator()

    @property
    def config(self) -> SmartMoneyConfig:
        return self._config

    def reload_config(self, path: str | None = None) -> None:
        """Hot-reload configuration from YAML.

        Clears all caches to ensure new weights are applied.
        """
        self._config = load_config(path)
        self._data_quality_gate = DataQualityGate(self._config.data_quality)
        # Clear all caches so old weights are not used
        from services.screener_service import ScreenerPipeline
        ScreenerPipeline._score_cache.clear()

    def analyze(
        self,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
        trades: list[dict[str, Any]] | None = None,
        index_history: list[float] | None = None,
        sector_history: list[float] | None = None,
    ) -> dict[str, Any]:
        cfg = self._config
        symbol = quote.get("symbol", "")

        # ---- Step 0: Data Quality Gate ----
        dq_report = self._data_quality_gate.validate(symbol, quote, history)

        # If quality is too low, return minimal result
        if dq_report.quality_score <= 0.3 and not dq_report.is_valid:
            return self._build_minimal_result(symbol, dq_report)

        # ---- Step 1: Layer computations ----
        index_ret = self._index_return(index_history)
        l1 = self.layer1.compute(quote, history)
        l2 = self.layer2.compute(quote, history, index_return=index_ret)
        l3 = self.layer3.compute(quote, history, trades)
        l4 = self.layer4.compute(quote, history)
        l5 = self.layer5.compute(quote, history, index_history, sector_history)
        l7 = self.layer7.compute(quote, history)
        l8 = self.layer8.compute(quote, history)

        all_layer = {**l1, **l2, **l3, **l4, **l5, **l7, **l8}

        # For partial mode, skip heavy layers (6, 9) if data is insufficient
        if dq_report.analysis_mode == "partial" and len(history) < 10:
            l6 = {"brs": 0.5, "rp_n": 0.5, "btf_n": 0.5, "pt": 0.5, "bcp": 0.5}
            l9 = {"bqs": 0.5}
        else:
            l6 = self.layer6.compute(quote, history, all_layer)
            l9 = self.layer9.compute(quote, history, all_layer)

        all_layer.update(l6)
        all_layer.update(l9)

        # ---- Step 2: Feature Store (cache features) ----
        feature_vector = self._feature_store.compute_all_features(
            quote=quote,
            history=history,
            layer_results={"l1": l1, "l2": l2, "l3": l3, "l4": l4, "l5": l5,
                           "l6": l6, "l7": l7, "l8": l8, "l9": l9},
            data_quality_score=dq_report.quality_score,
            analysis_mode=dq_report.analysis_mode,
            history_days=dq_report.history_days,
        )
        self._feature_store.put(symbol, feature_vector)

        # ---- Step 3: Composite Scores (config-driven) ----
        acc = compute_weighted_score(cfg, cfg.acc_weights, all_layer)
        abs_final = compute_weighted_score(cfg, cfg.abs_final_weights, all_layer)

        ahm_n = self._compute_ahm(history, index_history)
        fl_inputs = {**all_layer, "ahm_n": ahm_n}
        fl = compute_weighted_score(cfg, cfg.fl_weights, fl_inputs)

        br = compute_weighted_score(cfg, cfg.br_weights, all_layer)
        smc = compute_weighted_score(cfg, cfg.smc_weights, {"acc": acc, "abs_final": abs_final, "fl": fl, "br": br})

        # ---- Step 4: Penalties (config-driven) ----
        clv_n = l1.get("clv_n", 0.5)
        lf_n = l1.get("lf_n", 0.5)
        bp_n = l3.get("bp_n", 0.5)
        rvol_n = l1.get("rvol_n", 0.5)
        rrs = l5.get("rrs", 0.5)
        ess = l4.get("ess", 0.5)
        nrmf_n = l3.get("nrmf_n", 0.5)
        pt = l6.get("pt", 0.5)
        bcp_val = l6.get("bcp", 0.5)

        dr_inputs = {"clv_n": clv_n, "lf_n": lf_n, "bp_n": bp_n}
        dr = compute_weighted_score(cfg, cfg.penalty_dr_weights, dr_inputs)

        fbr_inputs = {"rvol_n": rvol_n, "rrs": rrs, "pt": pt, "bcp": bcp_val}
        fbr = compute_weighted_score(cfg, cfg.penalty_fbr_weights, fbr_inputs)

        dc_inputs = {"ess": ess, "rrs_inv": 1.0 - rrs, "nrmf_n_inv": 1.0 - nrmf_n}
        dc = compute_weighted_score(cfg, cfg.penalty_dc_weights, dc_inputs)

        # SMC adjustment
        adj = cfg.smc_adjustment
        smc_adj = smc - adj.get("dr", 0.15) * dr - adj.get("fbr", 0.10) * fbr - adj.get("dc", 0.08) * dc
        smc_final = min(1.0, max(0.0, smc_adj))

        # ---- Step 5: Phase Classification (config-driven) ----
        phase_scores = {
            "smc": smc_final, "acc": acc, "abs_final": abs_final, "fl": fl, "br": br,
            "ess": ess, "rrs": rrs, "rmr_n": l2.get("rmr_n", 0.0),
            "dps_n": l2.get("dps_n", 0.0), "rp_n": l6.get("rp_n", 0.0),
        }
        phase = classify_phase_from_config(cfg, phase_scores)

        # ---- Step 6: Confidence Score ----
        confidence = self._confidence_estimator.estimate(
            features=all_layer,
            history_days=dq_report.history_days,
            data_quality_score=dq_report.quality_score,
            analysis_mode=dq_report.analysis_mode,
        )

        # ---- Step 7: Build output ----
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
                "buyer_power": round(l7.get("bps", 0.0), 4),
                "microstructure": round(l8.get("mcs", 0.0), 4),
            },
            "penalties": {
                "distribution_risk": round(dr, 4),
                "fake_breakout_risk": round(fbr, 4),
                "dead_compression": round(dc, 4),
            },
            "features": features,
            "breakout_features": {k: round(v, 4) for k, v in l6.items() if isinstance(v, float)},
            "meta": {
                "engine_version": cfg.version,
                "config_profile": cfg.profile,
                "analysis_mode": dq_report.analysis_mode,
                "data_quality_score": round(dq_report.quality_score, 4),
                "confidence": {
                    "score": confidence.confidence,
                    "level": confidence.level,
                    "warnings": confidence.warnings,
                },
                "data_quality_issues": dq_report.issues,
                "data_quality_warnings": dq_report.warnings,
                "computed_at": time.time(),
            },
        }

    def _compute_ahm(self, history: list[dict[str, Any]], index_history: list[float] | None) -> float:
        """Compute Absorption History Memory (AHM)."""
        index_ret = self._index_return(index_history)
        ahm_window = self._config.lookback.get("ahm_window", 5)
        ahm_vals: list[float] = []
        for q in history[-ahm_window:]:
            try:
                ahm_vals.append(
                    self.layer2.compute(q, history, index_return=index_ret).get("abs", 0.0)
                )
            except Exception:
                ahm_vals.append(0.5)
        return sum(ahm_vals) / len(ahm_vals) if ahm_vals else 0.5

    def _build_minimal_result(self, symbol: str, dq_report: DataQualityReport) -> dict[str, Any]:
        """Build minimal result when data quality is too low."""
        return {
            "smart_money_score": 0.0,
            "phase": "neutral",
            "scores": dict.fromkeys(["accumulation", "absorption", "float_lock", "breakout_readiness", "buyer_power", "microstructure"], 0.0),
            "penalties": dict.fromkeys(["distribution_risk", "fake_breakout_risk", "dead_compression"], 0.0),
            "features": {},
            "breakout_features": {},
            "meta": {
                "engine_version": self._config.version,
                "config_profile": self._config.profile,
                "analysis_mode": "rejected",
                "data_quality_score": round(dq_report.quality_score, 4),
                "confidence": {"score": 0.0, "level": "none", "warnings": ["Data quality too low for analysis"]},
                "data_quality_issues": dq_report.issues,
                "data_quality_warnings": dq_report.warnings,
                "computed_at": time.time(),
            },
        }

    @staticmethod
    def _index_return(index_history: list[float] | None) -> float:
        if not index_history or len(index_history) < 2:
            return 0.0
        prev = index_history[-2]
        return (index_history[-1] - prev) / prev if prev else 0.0
