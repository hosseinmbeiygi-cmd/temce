"""ComparisonEngine — Advanced multi-symbol comparison (Level 17).

Provides:
- Tabular comparison of multiple symbols
- Strengths/weaknesses analysis
- Ranking and scoring
- Chart-ready data generation
- News context integration (async)
"""

from __future__ import annotations

from typing import Any

from services.chat.chart_generator import ChartGenerator
from services.chat.news_integration import NewsIntegration


class ComparisonEngine:
    """Advanced comparison engine for multiple symbols."""

    def __init__(self, news_integration: NewsIntegration | None = None):
        self._news = news_integration or NewsIntegration()
        self._chart_gen = ChartGenerator()

    async def compare(
        self,
        symbols: list[str],
        data_dict: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Compare multiple symbols (async).

        Args:
            symbols: List of 2-5 symbols
            data_dict: Symbol data from screener/analysis

        Returns:
            dict with: table, strengths_weaknesses, ranking, summary,
                      news_context, chart
        """
        if len(symbols) < 2:
            return {"error": "حداقل دو نماد برای مقایسه لازم است."}

        symbols = symbols[:5]  # Limit to 5

        # Build comparison table
        table = self._build_table(symbols, data_dict)

        # Analyze strengths and weaknesses
        sw = self._analyze_strengths_weaknesses(symbols, data_dict)

        # Rank symbols
        ranking = self._rank_symbols(symbols, data_dict)

        # Generate summary
        summary = self._generate_summary(symbols, data_dict, ranking)

        # Get news context (async)
        news_context = await self._get_news_context(symbols)

        # Generate chart data
        chart = self._generate_chart(symbols, data_dict)

        return {
            "table": table,
            "strengths_weaknesses": sw,
            "ranking": ranking,
            "summary": summary,
            "news_context": news_context,
            "chart": chart,
        }

    def _build_table(self, symbols: list[str], data_dict: dict[str, dict]) -> dict[str, Any]:
        """Build comparison table data."""
        columns = [
            "symbol",
            "price",
            "change_pct",
            "volume",
            "value",
            "smc_score",
            "phase",
            "pe_ratio",
            "eps",
        ]

        rows = []
        for sym in symbols:
            data = data_dict.get(sym, {})
            scores = data.get("scores", data)
            row = {
                "symbol": sym,
                "price": data.get("price", data.get("last_price", 0)),
                "change_pct": data.get("change_pct", 0),
                "volume": data.get("volume", 0),
                "value": data.get("value", 0),
                "smc_score": data.get("smc_score", scores.get("smc_score", 0)),
                "phase": self._translate_phase(data.get("phase", scores.get("phase", "neutral"))),
                "accumulation": scores.get("accumulation", 0),
                "absorption": scores.get("absorption", 0),
                "breakout_readiness": scores.get("breakout_readiness", 0),
                "float_lock": scores.get("float_lock", 0),
                "pe_ratio": data.get("pe_ratio", data.get("pe", 0)),
                "eps": data.get("eps", 0),
            }
            rows.append(row)

        # Find best in each column
        best = self._find_best_in_each(rows)

        return {
            "columns": columns,
            "rows": rows,
            "best_in_each": best,
        }

    def _find_best_in_each(self, rows: list[dict]) -> dict[str, str]:
        """Find which symbol is best in each numeric column."""
        best = {}
        numeric_cols = [
            "price",
            "change_pct",
            "volume",
            "value",
            "smc_score",
            "accumulation",
            "absorption",
            "breakout_readiness",
            "float_lock",
        ]
        higher_better = {
            "price": False,  # Lower price is better for value investing
            "change_pct": True,
            "volume": True,
            "value": True,
            "smc_score": True,
            "accumulation": True,
            "absorption": True,
            "breakout_readiness": True,
            "float_lock": True,
        }

        for col in numeric_cols:
            if higher_better.get(col, True):
                best_row = max(rows, key=lambda r: r.get(col, 0))
            else:
                valid = [r for r in rows if r.get(col, 0) > 0]
                best_row = min(valid, key=lambda r: r.get(col, 0)) if valid else rows[0]
            best[col] = best_row.get("symbol", "")

        return best

    def _analyze_strengths_weaknesses(self, symbols: list[str], data_dict: dict[str, dict]) -> dict[str, dict]:
        """Analyze strengths and weaknesses for each symbol."""
        result = {}

        layer_names = {
            "accumulation": "تجمع",
            "absorption": "جذب عرضه",
            "float_lock": "قفل شناوری",
            "breakout_readiness": "آمادگی شکست",
            "buyer_power": "قدرت خریدار",
            "microstructure": "ریزساختار",
            "liquidity": "نقدشوندگی",
            "liquidity_score": "نقدشوندگی",
            "power_score": "قدرت",
            "structure_score": "ساختار",
            "orderflow_score": "جریان سفارش",
            "trigger_score": "تریگر",
        }

        for sym in symbols:
            data = data_dict.get(sym, {})
            scores = data.get("scores", data)

            # Collect all score-like values
            all_scores = {}
            for k, v in scores.items():
                if isinstance(v, (int, float)) and 0 <= v <= 1:
                    all_scores[k] = v
            for k in [
                "smc_score",
                "liquidity_score",
                "power_score",
                "structure_score",
                "orderflow_score",
                "trigger_score",
            ]:
                if k in data and isinstance(data[k], (int, float)):
                    all_scores[k] = data[k]

            strengths = []
            weaknesses = []

            for key, value in all_scores.items():
                name = layer_names.get(key, key)
                if value >= 0.6:
                    strengths.append(f"{name} ({value:.2f})")
                elif value <= 0.4:
                    weaknesses.append(f"{name} ({value:.2f})")

            result[sym] = {
                "strengths": strengths[:3],
                "weaknesses": weaknesses[:3],
                "overall_score": data.get("smc_score", 0),
            }

        return result

    def _rank_symbols(self, symbols: list[str], data_dict: dict[str, dict]) -> list[dict[str, Any]]:
        """Rank symbols by composite score."""
        rankings = []
        for sym in symbols:
            data = data_dict.get(sym, {})
            smc = data.get("smc_score", 0)
            change = data.get("change_pct", 0)
            volume = data.get("volume", 0)

            composite = smc * 0.5 + min(1, max(0, change / 5)) * 0.3 + min(1, volume / 1e7) * 0.2
            rankings.append(
                {
                    "symbol": sym,
                    "composite_score": round(composite, 4),
                    "smc_score": smc,
                }
            )

        rankings.sort(key=lambda r: r["composite_score"], reverse=True)
        for i, r in enumerate(rankings, 1):
            r["rank"] = i

        return rankings

    def _generate_summary(self, symbols: list[str], data_dict: dict[str, dict], rankings: list[dict[str, Any]]) -> str:
        """Generate Persian comparison summary."""
        if not rankings:
            return "داده کافی برای مقایسه وجود ندارد."

        best = rankings[0]
        worst = rankings[-1]

        lines = [f"📊 **مقایسه {len(symbols)} نماد:**", "═" * 50]

        # Ranking
        lines.append("")
        lines.append("🏆 **رتبه‌بندی:**")
        for r in rankings:
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r["rank"], f"  {r['rank']}.")
            lines.append(f"  {medal} {r['symbol']} (SMC: {r['smc_score']:.3f})")

        # Best aspects
        lines.append("")
        lines.append(f"⭐ **بهترین SMC:** {best['symbol']} ({best['smc_score']:.3f})")

        # Worst
        if worst["symbol"] != best["symbol"]:
            lines.append(f"⚠️ **ضعیف‌ترین:** {worst['symbol']} ({worst['smc_score']:.3f})")

        return "\n".join(lines)

    async def _get_news_context(self, symbols: list[str]) -> dict[str, str]:
        """Get news summary for each symbol (async)."""
        result = {}
        for sym in symbols:
            try:
                analysis = await self._news.get_news_for_symbol(sym)
                if analysis.get("has_news"):
                    result[sym] = analysis.get("summary", "اخباری موجود نیست")[:150]
                else:
                    result[sym] = "بدون خبر جدید"
            except Exception:
                result[sym] = "خطا در دریافت خبر"
        return result

    def _generate_chart(self, symbols: list[str], data_dict: dict[str, dict]) -> dict[str, Any] | None:
        """Generate comparison chart data (sync — no I/O)."""
        try:
            scores_dict = {}
            for sym in symbols:
                data = data_dict.get(sym, {})
                scores = data.get("scores", data)
                scores_dict[sym] = {
                    "smc_score": data.get("smc_score", 0),
                    "accumulation": scores.get("accumulation", 0),
                    "absorption": scores.get("absorption", 0),
                    "breakout_readiness": scores.get("breakout_readiness", 0),
                    "float_lock": scores.get("float_lock", 0),
                }

            return self._chart_gen.generate_comparison_chart(symbols, scores_dict)
        except Exception:
            return None

    @staticmethod
    def _translate_phase(phase: str) -> str:
        """Translate phase name to Persian."""
        phases = {
            "confirmed_smart_money": "پول هوشمند تأیید",
            "breakout_ready": "آماده شکست",
            "breakout_ready_fast": "آماده شکست سریع",
            "float_lock": "قفل شناوری",
            "active_absorption": "جذب عرضه فعال",
            "early_accumulation": "تجمع اولیه",
            "distribution": "توزیع",
            "neutral": "خنثی",
            "weak": "ضعیف",
        }
        return phases.get(phase, phase)
