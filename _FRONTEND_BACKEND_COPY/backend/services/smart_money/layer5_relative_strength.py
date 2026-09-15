from __future__ import annotations

from typing import Any

from services.smart_money.normalizer import MinMaxClipped

norm = MinMaxClipped()


class RelativeStrengthLayer:
    def compute(
        self,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
        index_history: list[float] | None = None,
        sector_history: list[float] | None = None,
    ) -> dict[str, float]:
        c = quote.get("price_close", 0.0)

        closes = [q.get("price_close", 0.0) or 0.0 for q in history[-11:]]
        closes_full = [c] + closes if closes else [c]

        rsi3 = self._returns(closes_full, 3)
        rsi5 = self._returns(closes_full, 5)
        rsi10 = self._returns(closes_full, 10)

        rsi3_n = norm(rsi3, -0.03, 0.05)
        rsi5_n = norm(rsi5, -0.05, 0.08)
        rsi10_n = norm(rsi10, -0.08, 0.12)

        rss_n = 0.0
        rds_n = 0.0
        if index_history and len(index_history) >= 11:
            ri3 = self._difference(index_history, 3)
            ri5 = self._difference(index_history, 5)
            ri10 = self._difference(index_history, 10)
            rss3 = rsi3 - ri3
            rss5 = rsi5 - ri5
            rss10 = rsi10 - ri10
            rss_n = (norm(rss3, -0.03, 0.05) + norm(rss5, -0.05, 0.08) + norm(rss10, -0.08, 0.12)) / 3
            rds = self._red_day_strength(closes_full, index_history[: len(closes_full)])
            rds_n = norm(rds, -0.02, 0.03)

        rrs = 0.22 * rsi3_n + 0.22 * rsi5_n + 0.18 * rsi10_n + 0.18 * rss_n + 0.10 * rds_n + 0.10 * rsi3_n

        return {
            "rrs": min(1.0, max(0.0, rrs)),
            "rsi3_n": rsi3_n,
            "rsi5_n": rsi5_n,
            "rsi10_n": rsi10_n,
            "rss_n": rss_n,
            "rds_n": rds_n,
        }

    @staticmethod
    def _returns(closes: list[float], days: int) -> float:
        if len(closes) <= days:
            return 0.0
        prev = closes[-days - 1]
        return (closes[-1] - prev) / prev if prev else 0.0

    @staticmethod
    def _difference(index_vals: list[float], days: int) -> float:
        if len(index_vals) <= days:
            return 0.0
        prev = index_vals[-days - 1]
        return (index_vals[-1] - prev) / prev if prev else 0.0

    @staticmethod
    def _red_day_strength(stock: list[float], index: list[float]) -> float:
        diffs = []
        n = min(len(stock), len(index))
        for i in range(1, n):
            s_ret = (stock[i] - stock[i - 1]) / stock[i - 1] if stock[i - 1] else 0.0
            i_ret = (index[i] - index[i - 1]) / index[i - 1] if index[i - 1] else 0.0
            if i_ret < 0:
                diffs.append(s_ret - i_ret)
        return sum(diffs) / len(diffs) if diffs else 0.0
