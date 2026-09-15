from __future__ import annotations


class PositionSizer:
    """Position sizer for backtesting position sizing calculations.

    Supports roadmap v1:99 volatility-based sizing:
      size = (capital * risk_pct) / (ATR * stop_multiplier)
    where ATR is in price units.
    """

    def __init__(self, method: str = "fixed", value: float = 0.0, atr_multiplier: float = 2.0) -> None:
        self.method = method
        self.value = value
        self.atr_multiplier = atr_multiplier

    @staticmethod
    def compute_atr(bars: list[dict], period: int = 14) -> float:
        """Compute ATR from OHLC bars (Wilder's). Returns 0 if insufficient data."""
        if len(bars) < 2:
            return 0.0
        trs: list[float] = []
        for i in range(1, len(bars)):
            high = float(bars[i].get("high", bars[i].get("close", 0)))
            low = float(bars[i].get("low", bars[i].get("close", 0)))
            prev_close = float(bars[i - 1].get("close", 0))
            if high <= 0 or low <= 0 or prev_close <= 0:
                continue
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        if not trs:
            return 0.0
        if len(trs) < period:
            return sum(trs) / len(trs)
        # Wilder smoothing
        atr = sum(trs[:period]) / period
        for tr in trs[period:]:
            atr = (atr * (period - 1) + tr) / period
        return atr

    def calculate(
        self,
        capital: float,
        price: float,
        win_rate: float = 0.5,
        avg_win: float = 0.1,
        avg_loss: float = 0.05,
        stop_loss_pct: float = 1.0,
        atr: float | None = None,
        atr_bars: list[dict] | None = None,
    ) -> float:
        if self.method == "fixed":
            return self.value / price if price > 0 else 0.0
        elif self.method == "percent":
            return (capital * self.value / 100.0) / price if price > 0 else 0.0
        elif self.method == "kelly":
            kelly_pct = (win_rate * avg_win - (1 - win_rate) * avg_loss) / max(avg_win * avg_loss, 1e-12)
            kelly_pct = max(0, min(kelly_pct, self.value))
            return (capital * kelly_pct) / price if price > 0 else 0.0
        elif self.method == "risk_based":
            risk_amount = capital * (self.value / 100.0)
            risk_per_share = price * (stop_loss_pct / 100.0)
            if risk_per_share <= 0:
                return 0.0
            return risk_amount / risk_per_share
        elif self.method == "atr":
            # Volatility-based: v1:101  size = (capital * risk_pct) / (ATR * multiplier)
            risk_pct = self.value / 100.0  # value is risk% per trade (e.g. 1.0 = 1%)
            if atr is None and atr_bars is not None:
                atr = self.compute_atr(atr_bars)
            if not atr or atr <= 0:
                # fallback to percent-of-capital if ATR unavailable
                return (capital * risk_pct) / price if price > 0 else 0.0
            risk_amount = capital * risk_pct
            risk_per_share = atr * self.atr_multiplier
            if risk_per_share <= 0:
                return 0.0
            qty = risk_amount / risk_per_share
            # cap by available capital (no leverage)
            max_by_capital = capital / price if price > 0 else 0
            return min(qty, max_by_capital)
        return 0.0

    def calculate_with_confidence(
        self,
        capital: float,
        price: float,
        confidence: float = 1.0,
        atr: float | None = None,
        atr_bars: list[dict] | None = None,
    ) -> float:
        """Scale position by confidence score (v2:79 - explicit choice: affects sizing)."""
        base = self.calculate(capital, price, atr=atr, atr_bars=atr_bars)
        # confidence in [0,1], linear scaling; 0.5 = half size
        conf = max(0.0, min(1.0, float(confidence)))
        return base * conf
