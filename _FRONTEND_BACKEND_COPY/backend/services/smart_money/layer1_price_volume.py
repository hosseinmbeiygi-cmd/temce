from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger
from services.smart_money.normalizer import MinMaxClipped

logger = get_logger(__name__)

norm = MinMaxClipped()

_DEFAULT_PVS_WEIGHTS = {
    "rvol_n": 0.20,
    "vtr_n": 0.20,
    "clv_n": 0.15,
    "rec_n": 0.15,
    "ipe_n": 0.15,
    "lf_n": 0.15,
}


def _load_pvs_weights() -> dict[str, float]:
    """Load PVS weights from config/smart_money.yaml, falling back to defaults."""
    try:
        import yaml

        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "smart_money.yaml")
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        weights = cfg.get("layer_weights", {}).get("price_volume", {}).get("pvs", {})
        if weights and isinstance(weights, dict):
            return {k: float(v) for k, v in weights.items()}
    except Exception as e:
        logger.debug("Could not load smart_money.yaml weights: %s", e)
    return dict(_DEFAULT_PVS_WEIGHTS)


class PriceVolumeLayer:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights if weights is not None else _load_pvs_weights()

    def compute(
        self, quote: dict[str, Any], history: list[dict[str, Any]], index_return: float = 0.0
    ) -> dict[str, float]:
        vt = quote.get("value", 0) or 1
        v = quote.get("volume", 0) or 1
        c = quote.get("price_close", 0.0)
        o = quote.get("price_open", 0.0)
        h = quote.get("price_high", 0.0)
        low = quote.get("price_low", 0.0)
        last = quote.get("price_last", c)

        values_20 = [q.get("value", 0) or 1 for q in history[-20:]] or [1]
        vols_20 = [q.get("volume", 0) or 1 for q in history[-20:]] or [1]

        avg_value = sum(values_20) / len(values_20)
        avg_vol = sum(vols_20) / len(vols_20)

        rvol = v / avg_vol if avg_vol else 1.0
        vtr = vt / avg_value if avg_value else 1.0

        rvol_n = norm(rvol, 0.8, 2.5)
        vtr_n = norm(vtr, 0.8, 2.5)

        clv = self._clv(c, h, low)
        clv_n = (clv + 1) / 2

        rec = self._recovery(c, low, h)
        rec_n = rec

        ret = (c - o) / o if o else 0.0
        pe = abs(ret) / vtr if vtr else 0.01
        ipe = 1.0 / pe if pe > 0.01 else 10.0
        ipe_n = 1.0 - norm(ipe, 1.0, 10.0)

        lf = (last - c) / c if c else 0.0
        lf_n = norm(lf, -0.01, 0.02)

        w = self.weights
        pvs = (
            w.get("rvol_n", 0.20) * rvol_n
            + w.get("vtr_n", 0.20) * vtr_n
            + w.get("clv_n", 0.15) * clv_n
            + w.get("rec_n", 0.15) * rec_n
            + w.get("ipe_n", 0.15) * ipe_n
            + w.get("lf_n", 0.15) * lf_n
        )

        return {
            "pvs": min(1.0, max(0.0, pvs)),
            "rvol_n": rvol_n,
            "vtr_n": vtr_n,
            "clv_n": clv_n,
            "rec_n": rec_n,
            "ipe_n": ipe_n,
            "lf_n": lf_n,
        }

    @staticmethod
    def _clv(c: float, h: float, low: float) -> float:
        r = h - low
        if r == 0:
            return 0.0
        return ((c - low) - (h - c)) / r

    @staticmethod
    def _recovery(c: float, low: float, h: float) -> float:
        r = h - low
        if r == 0:
            return 0.5
        return (c - low) / r
