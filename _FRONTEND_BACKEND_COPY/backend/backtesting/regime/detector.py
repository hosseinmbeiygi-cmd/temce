"""Market regime detector (roadmap v2:90, v1:198).

Explicit, pre-defined rules (not fitted post-hoc):
  - Trend vs range via SMA200 deviation and ADX
  - Must be fixed BEFORE backtest to avoid overfitting
"""

from __future__ import annotations


class RegimeDetector:
    """Classify market regime for filtering (v1:198, v2:90)."""

    def __init__(
        self, sma_period: int = 200, adx_period: int = 14, adx_threshold: float = 25.0, deviation_pct: float = 5.0
    ):
        self.sma_period = sma_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.deviation_pct = deviation_pct

    @staticmethod
    def sma(prices: list[float], period: int) -> list[float | None]:
        out: list[float | None] = []
        for i in range(len(prices)):
            if i + 1 < period:
                out.append(None)
            else:
                out.append(sum(prices[i + 1 - period : i + 1]) / period)
        return out

    @staticmethod
    def adx(bars: list[dict], period: int = 14) -> list[float | None]:
        """Simplified ADX (Wilder). Returns None where not computable."""
        if len(bars) < period * 2:
            return [None] * len(bars)
        highs = [float(b.get("high", b.get("close", 0))) for b in bars]
        lows = [float(b.get("low", b.get("close", 0))) for b in bars]
        closes = [float(b.get("close", 0)) for b in bars]
        # TR and DM
        trs, plus_dm, minus_dm = [], [], []
        for i in range(1, len(bars)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            up = highs[i] - highs[i - 1]
            down = lows[i - 1] - lows[i]
            pdm = up if up > down and up > 0 else 0
            mdm = down if down > up and down > 0 else 0
            trs.append(tr)
            plus_dm.append(pdm)
            minus_dm.append(mdm)

        # Wilder smoothing helper
        def wilder(arr: list[float], p: int) -> list[float]:
            out = []
            if len(arr) < p:
                return []
            val = sum(arr[:p]) / p
            out.append(val)
            for v in arr[p:]:
                val = (val * (p - 1) + v) / p
                out.append(val)
            return out

        str_vals = wilder(trs, period)
        pdi_vals = []
        mdi_vals = []
        # Need ATR from str
        atr_vals = str_vals
        # For simplicity DX via smoothed DM/ATR
        sp_dm = wilder(plus_dm, period)
        sm_dm = wilder(minus_dm, period)
        # align lengths
        n = min(len(atr_vals), len(sp_dm), len(sm_dm))
        dx = []
        for i in range(n):
            atr = atr_vals[-n + i] if len(atr_vals) >= n else atr_vals[i]
            pdi = sp_dm[-n + i] / atr * 100 if atr else 0
            mdi = sm_dm[-n + i] / atr * 100 if atr else 0
            pdi_vals.append(pdi)
            mdi_vals.append(mdi)
            denom = pdi + mdi
            dx.append(abs(pdi - mdi) / denom * 100 if denom else 0)
        adx_vals = wilder(dx, period)
        # pad to bars length
        pad = len(bars) - len(adx_vals)
        return [None] * pad + adx_vals

    def classify(self, bars: list[dict]) -> list[str]:
        """Return regime per bar: 'bull' | 'bear' | 'sideways' | 'unknown'."""
        closes = [float(b.get("close", 0)) for b in bars]
        smas = self.sma(closes, self.sma_period)
        adxs = self.adx(bars, self.adx_period)
        regimes: list[str] = []
        for i, c in enumerate(closes):
            sma = smas[i]
            adx = adxs[i] if i < len(adxs) else None
            if sma is None or c <= 0:
                regimes.append("unknown")
                continue
            dev = (c - sma) / sma * 100
            # ADX confirms trend strength
            is_trending = adx is not None and adx >= self.adx_threshold
            if dev > self.deviation_pct and is_trending:
                regimes.append("bull")
            elif dev < -self.deviation_pct and is_trending:
                regimes.append("bear")
            elif abs(dev) <= self.deviation_pct or not is_trending:
                regimes.append("sideways")
            else:
                regimes.append("sideways")
        return regimes

    def regime_of(self, bars: list[dict]) -> str:
        """Regime of the latest bar."""
        return self.classify(bars)[-1] if bars else "unknown"
