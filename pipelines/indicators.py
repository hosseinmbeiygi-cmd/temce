from __future__ import annotations

import math


class IndicatorPipeline:
    """Pipeline for calculating technical indicators."""

    def sma(self, prices: list[float], period: int = 5) -> list[float | None]:
        result: list[float | None] = []
        for i in range(len(prices)):
            if i < period - 1:
                result.append(None)
            else:
                result.append(sum(prices[i - period + 1 : i + 1]) / period)
        return result

    def ema(self, prices: list[float], period: int = 5) -> list[float | None]:
        result: list[float | None] = []
        multiplier = 2 / (period + 1)
        for i in range(len(prices)):
            if i < period - 1:
                result.append(None)
            elif i == period - 1:
                result.append(sum(prices[:period]) / period)
            else:
                prev = result[-1]
                if prev is not None:
                    result.append((prices[i] - prev) * multiplier + prev)
                else:
                    result.append(None)
        return result

    def rsi(self, prices: list[float], period: int = 14) -> list[float | None]:
        result: list[float | None] = []
        for i in range(len(prices)):
            if i < period:
                result.append(None)
            else:
                gains = []
                losses = []
                for j in range(i - period, i):
                    diff = prices[j + 1] - prices[j]
                    if diff >= 0:
                        gains.append(diff)
                        losses.append(0)
                    else:
                        gains.append(0)
                        losses.append(-diff)
                avg_gain = sum(gains) / period if gains else 0
                avg_loss = sum(losses) / period if losses else 0
                if avg_loss == 0:
                    result.append(100.0)
                else:
                    rs = avg_gain / avg_loss
                    result.append(100 - (100 / (1 + rs)))
        return result

    def macd(self, prices: list[float]) -> tuple[list[float | None], list[float | None], list[float | None]]:
        ema12 = self.ema(prices, 12)
        ema26 = self.ema(prices, 26)
        macd_line: list[float | None] = []
        signal: list[float | None] = []
        histogram: list[float | None] = []
        for i in range(len(prices)):
            if ema12[i] is not None and ema26[i] is not None:
                macd_line.append(ema12[i] - ema26[i])  # type: ignore
            else:
                macd_line.append(None)
            signal.append(None)
            histogram.append(None)

        signal_values: list[float] = []
        for i, m in enumerate(macd_line):
            if m is not None:
                signal_values.append(m)
                if len(signal_values) >= 9:
                    sig = sum(signal_values[-9:]) / 9
                    signal[i] = sig
                    if macd_line[i] is not None:
                        histogram[i] = macd_line[i] - sig  # type: ignore
        return macd_line, signal, histogram

    def bollinger_bands(
        self, prices: list[float], period: int = 5, num_std: int = 2
    ) -> tuple[list[float | None], list[float | None], list[float | None]]:
        middle = self.sma(prices, period)
        upper: list[float | None] = []
        lower: list[float | None] = []
        for i in range(len(prices)):
            if middle[i] is None or i < period - 1:
                upper.append(None)
                lower.append(None)
            else:
                window = prices[i - period + 1 : i + 1]
                mean = sum(window) / period
                variance = sum((x - mean) ** 2 for x in window) / period
                std = math.sqrt(variance)
                upper.append(middle[i] + num_std * std)  # type: ignore
                lower.append(middle[i] - num_std * std)  # type: ignore
        return upper, middle, lower
