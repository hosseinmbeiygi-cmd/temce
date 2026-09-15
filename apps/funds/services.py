"""لایه سرویس صندوق‌یار — اورکستریشن Adapter + Metrics + Scoring.

در حالت واقعی، داده از Adapterها و DB می‌آید. در dev/test بدون DB،
از یک seed داخلی (FundCatalog) استفاده می‌شود تا کل سیستم قابل اجرا باشد.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .adapters.fipiran import FipiranAdapter
from .adapters.tsetmc import TSETMCAdapter
from .constants import (
    TYPE_LABELS_FA,
)
from .metrics.engine import MetricsInput, compute_all_metrics
from .peers import build_peer_context
from .scoring import ScoringConfigStore, compute_score

logger = logging.getLogger(__name__)


def _mk_nav(base: float, slope: float, days: int = 500) -> list[float]:
    """ساخت nav مصنوعی با نوسان منفی دوره‌ای (برای sortino/calmar واقعی)."""
    return [base + i * slope + ((i % 7) - 3) * slope * 2 for i in range(days)]


# ── Seed داده — ۱۸ صندوق نمونه (peer واقعی برای صدک‌بندی) ───────────
_SEED_FUNDS: list[dict[str, Any]] = [
    # ── درآمد ثابت (FI) ──
    {
        "symbol": "کارین",
        "name_fa": "صندوق درآمد ثابت کارین",
        "type_code": "FI",
        "manager": "سپرده‌گذاری کارین",
        "is_etf": True,
        "aum_btoman": 48000.0,
        "nav_redeem": 10230.0,
        "market_price": 10241.0,
        "nav_history": _mk_nav(10000, 3.5),
    },
    {
        "symbol": "کمند",
        "name_fa": "صندوق درآمد ثابت کمند",
        "type_code": "FI",
        "manager": "سبدگردان کمند",
        "is_etf": True,
        "aum_btoman": 61000.0,
        "nav_redeem": 10110.0,
        "market_price": 10115.0,
        "nav_history": _mk_nav(10000, 2.8),
    },
    {
        "symbol": "اعتماد",
        "name_fa": "صندوق درآمد ثابت اعتماد",
        "type_code": "FI",
        "manager": "اعتماد آفرین پارسیان",
        "is_etf": True,
        "aum_btoman": 39000.0,
        "nav_redeem": 10090.0,
        "market_price": 10095.0,
        "nav_history": _mk_nav(10000, 3.1),
    },
    {
        "symbol": "یاقوت",
        "name_fa": "صندوق درآمد ثابت یاقوت",
        "type_code": "FI",
        "manager": "یاقوت سرمایه",
        "is_etf": True,
        "aum_btoman": 28000.0,
        "nav_redeem": 10070.0,
        "market_price": 10072.0,
        "nav_history": _mk_nav(10000, 2.6),
    },
    # ── طلا (GO) ──
    {
        "symbol": "طلا",
        "name_fa": "صندوق طلای لوتوس",
        "type_code": "GO",
        "manager": "لوتوس پارسیان",
        "is_etf": True,
        "aum_btoman": 22000.0,
        "nav_redeem": 46200.0,
        "market_price": 47000.0,
        "nav_history": _mk_nav(40000, 15, 500),
    },
    {
        "symbol": "عیار",
        "name_fa": "صندوق طلای مفید",
        "type_code": "GO",
        "manager": "مفید",
        "is_etf": True,
        "aum_btoman": 19000.0,
        "nav_redeem": 73500.0,
        "market_price": 73700.0,
        "nav_history": _mk_nav(65000, 22, 500),
    },
    {
        "symbol": "گوهر",
        "name_fa": "صندوق طلای کیان",
        "type_code": "GO",
        "manager": "کیان",
        "is_etf": True,
        "aum_btoman": 12000.0,
        "nav_redeem": 18300.0,
        "market_price": 18400.0,
        "nav_history": _mk_nav(16000, 6, 400),
    },
    {
        "symbol": "کهربا",
        "name_fa": "صندوق طلای کاریزما",
        "type_code": "GO",
        "manager": "کاریزما",
        "is_etf": True,
        "aum_btoman": 15000.0,
        "nav_redeem": 25000.0,
        "market_price": 25200.0,
        "nav_history": _mk_nav(22000, 8, 400),
    },
    # ── اهرمی (LV) ──
    {
        "symbol": "اهرم",
        "name_fa": "صندوق اهرمی کاریزما",
        "type_code": "LV",
        "manager": "کاریزما",
        "is_etf": True,
        "aum_btoman": 15000.0,
        "nav_redeem": 21400.0,
        "market_price": 22100.0,
        "nav_history": _mk_nav(20000, 4, 500),
        "volatility_decay": 0.03,
        "suspension_risk": 0.12,
        "leverage_ratio": 2.0,
    },
    {
        "symbol": "موج",
        "name_fa": "صندوق اهرمی موج فیروزه",
        "type_code": "LV",
        "manager": "توسعه فیروزه",
        "is_etf": True,
        "aum_btoman": 9800.0,
        "nav_redeem": 11500.0,
        "market_price": 11700.0,
        "nav_history": _mk_nav(11000, 2.5, 400),
        "volatility_decay": 0.04,
        "suspension_risk": 0.15,
        "leverage_ratio": 1.8,
    },
    {
        "symbol": "شتاب",
        "name_fa": "صندوق اهرمی شتاب آگاه",
        "type_code": "LV",
        "manager": "آگاه",
        "is_etf": True,
        "aum_btoman": 7600.0,
        "nav_redeem": 9200.0,
        "market_price": 9400.0,
        "nav_history": _mk_nav(8800, 2.0, 400),
        "volatility_decay": 0.035,
        "suspension_risk": 0.13,
        "leverage_ratio": 1.9,
    },
    # ── سهامی (EQ) ──
    {
        "symbol": "سرو",
        "name_fa": "صندوق سهامی سرو",
        "type_code": "EQ",
        "manager": "آگاه",
        "is_etf": True,
        "aum_btoman": 8000.0,
        "nav_redeem": 15000.0,
        "market_price": 14900.0,
        "nav_history": _mk_nav(14000, 3, 400),
    },
    {
        "symbol": "آگاس",
        "name_fa": "صندوق سهامی آگاس",
        "type_code": "EQ",
        "manager": "مفید",
        "is_etf": True,
        "aum_btoman": 5200.0,
        "nav_redeem": 32000.0,
        "market_price": 32150.0,
        "nav_history": _mk_nav(30000, 5, 400),
    },
    {
        "symbol": "ثروتم",
        "name_fa": "صندوق سهامی ثروتم",
        "type_code": "EQ",
        "manager": "تم",
        "is_etf": True,
        "aum_btoman": 6100.0,
        "nav_redeem": 41000.0,
        "market_price": 40900.0,
        "nav_history": _mk_nav(38000, 6, 400),
    },
    # ── بخشی (SEC) ──
    {
        "symbol": "پتروآبان",
        "name_fa": "صندوق بخشی پتروشیمی",
        "type_code": "SEC",
        "manager": "آبان",
        "is_etf": True,
        "aum_btoman": 3200.0,
        "nav_redeem": 21000.0,
        "market_price": 21200.0,
        "nav_history": _mk_nav(19000, 6, 300),
    },
    {
        "symbol": "اتوآگاه",
        "name_fa": "صندوق بخشی خودرو",
        "type_code": "SEC",
        "manager": "آگاه",
        "is_etf": True,
        "aum_btoman": 2100.0,
        "nav_redeem": 11500.0,
        "market_price": 11600.0,
        "nav_history": _mk_nav(10500, 3.5, 300),
    },
    # ── مختلط (MX) ──
    {
        "symbol": "زیتون",
        "name_fa": "صندوق مختلط زیتون",
        "type_code": "MX",
        "manager": "کاریزما",
        "is_etf": True,
        "aum_btoman": 7400.0,
        "nav_redeem": 18500.0,
        "market_price": 18580.0,
        "nav_history": _mk_nav(17000, 4.5, 400),
    },
    {
        "symbol": "آرمان",
        "name_fa": "صندوق مختلط آرمان",
        "type_code": "MX",
        "manager": "آرمان",
        "is_etf": True,
        "aum_btoman": 5200.0,
        "nav_redeem": 9200.0,
        "market_price": 9210.0,
        "nav_history": _mk_nav(8500, 2.2, 400),
    },
]

_DEFAULT_MARKET_RETURNS = [0.001 * ((i % 3) - 1) + 0.0001 * (i % 5) for i in range(500)]
_DEFAULT_FX_RETURNS = [0.0008 + 0.0001 * (i % 5) for i in range(500)]


class FundCatalog:
    """کاتالوگ صندوق‌ها — در نسخه واقعی جایگزین کوئری DB می‌شود."""

    def __init__(self, funds: list[dict[str, Any]] | None = None):
        self._funds: dict[str, dict[str, Any]] = {f["symbol"]: f for f in (funds or _SEED_FUNDS)}

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._funds.values())

    def get(self, symbol: str) -> dict[str, Any] | None:
        return self._funds.get(symbol)

    def list_symbols(self) -> list[str]:
        return list(self._funds.keys())


class FundService:
    """سرویس اصلی — محاسبه کامل: metrics → peer → score → recommendation."""

    def __init__(
        self,
        catalog: FundCatalog | None = None,
        fipiran: FipiranAdapter | None = None,
        tsetmc: TSETMCAdapter | None = None,
        config_store: ScoringConfigStore | None = None,
    ):
        self.catalog = catalog or FundCatalog()
        self.fipiran = fipiran or FipiranAdapter()
        self.tsetmc = tsetmc or TSETMCAdapter()
        self.config_store = config_store or ScoringConfigStore()

    # ── داده ورودی ─────────────────────────────────────────────────
    def _build_input(self, fund: dict[str, Any]) -> MetricsInput:
        peers = build_peer_context(
            fund["symbol"],
            fund["type_code"],
            fund.get("aum_btoman"),
            self.catalog.list_all(),
        )
        peer_funds = [self.catalog.get(s) for s in peers.peers if self.catalog.get(s)]

        peer_bubbles = []
        peer_series: list[list[float]] = []
        for pf in peer_funds:
            if pf.get("market_price") and pf.get("nav_redeem"):
                peer_bubbles.append((pf["market_price"] - pf["nav_redeem"]) / pf["nav_redeem"] * 100)
            ph = pf.get("nav_history") or []
            if len(ph) >= 2:
                pr = [ph[i] / ph[i - 1] - 1 for i in range(1, len(ph)) if ph[i - 1] > 0]
                if pr:
                    peer_series.append(pr)

        # peer_returns: سری میانگین هم‌طول با nav_returns
        peer_returns = None
        if peer_series:
            n_hist = len(fund.get("nav_history", []))
            aligned = [s[-(n_hist - 1) :] if len(s) >= n_hist - 1 else s for s in peer_series]
            length = min(len(s) for s in aligned)
            if length > 0:
                peer_returns = [sum(s[i] for s in aligned) / len(aligned) for i in range(length)]

        self_bubble = None
        if fund.get("market_price") and fund.get("nav_redeem"):
            self_bubble = (fund["market_price"] - fund["nav_redeem"]) / fund["nav_redeem"] * 100

        market_returns = _DEFAULT_MARKET_RETURNS[: len(fund.get("nav_history", []))]
        fx = _DEFAULT_FX_RETURNS[: len(fund.get("nav_history", []))]

        # پیش‌فرض‌های معقول برای داده ناقص (seed/demo)
        twr = fund.get("twr")
        if twr is None:
            ph = fund.get("nav_history") or []
            twr = (ph[-1] / ph[0] - 1) if len(ph) >= 2 and ph[0] > 0 else None
        fund_returns = fund.get("fund_returns") or market_returns
        benchmark_returns = fund.get("benchmark_returns") or [r * 0.6 for r in market_returns]

        return MetricsInput(
            symbol=fund["symbol"],
            type_code=fund["type_code"],
            nav_history=fund.get("nav_history", []),
            nav_redeem=fund.get("nav_redeem"),
            market_price=fund.get("market_price"),
            aum_btoman=fund.get("aum_btoman"),
            daily_volume=fund.get("daily_volume"),
            bid=fund.get("bid"),
            ask=fund.get("ask"),
            market_returns=market_returns,
            fx_nima_returns=fx,
            fx_azad_returns=fx,
            cpi_returns=[0.03 for _ in fx],
            peer_bubbles=peer_bubbles or None,
            self_bubble=self_bubble,
            portfolio_weights=fund.get("portfolio_weights") or [0.3, 0.3, 0.2, 0.2],
            benchmark_weights=fund.get("benchmark_weights") or [0.25, 0.25, 0.25, 0.25],
            ter=fund.get("ter", 0.02),
            performance_fee_type=fund.get("performance_fee_type"),
            turnover=fund.get("turnover", 0.4),
            cash_weight=fund.get("cash_weight", 0.03),
            redemption_rate=fund.get("redemption_rate", 0.03),
            volatility_decay=fund.get("volatility_decay"),
            suspension_risk=fund.get("suspension_risk"),
            leverage_ratio=fund.get("leverage_ratio"),
            flow_performance=fund.get("flow_performance", 0.5),
            twr=twr,
            dwr=fund.get("dwr") or (twr * 0.9 if twr else None),
            holdings_history=fund.get("holdings_history") or [{"a": 0.3, "b": 0.3, "c": 0.2, "d": 0.2}],
            declared_style=fund.get("declared_style") or {"a": 0.3, "b": 0.3, "c": 0.2, "d": 0.2},
            fund_returns=fund_returns,
            benchmark_returns=benchmark_returns,
            fund_excess=fund_returns,
            market_excess=benchmark_returns,
            pre_change_returns=fund.get("pre_change_returns") or [0.01] * 30,
            post_change_returns=fund.get("post_change_returns") or [0.013] * 30,
            peer_returns=peer_returns,
            geopolitical_event_returns=fund.get("geopolitical_event_returns") or [0.005, -0.003, 0.002],
        )

    # ── خروجی کامل ─────────────────────────────────────────────────
    def compute_full(self, symbol: str) -> dict[str, Any] | None:
        fund = self.catalog.get(symbol)
        if fund is None:
            return None

        inp = self._build_input(fund)
        config = self.config_store.get_active(fund["type_code"])
        weights = config.weights.get(fund["type_code"], config.weights.get("EQ", {}))
        metrics_result = compute_all_metrics(inp, weighted_keys=set(weights.keys()))
        values = metrics_result["values"]

        score_result = compute_score(
            values,
            type_code=fund["type_code"],
            config=config,
        )

        type_code = fund["type_code"]
        return {
            "symbol": symbol,
            "name_fa": fund["name_fa"],
            "type_code": type_code,
            "type_label_fa": TYPE_LABELS_FA.get(type_code, type_code),
            "manager": fund.get("manager"),
            "custodian": fund.get("custodian"),
            "auditor": fund.get("auditor"),
            "market_maker": fund.get("market_maker"),
            "inception_date": fund.get("inception_date"),
            "is_etf": fund.get("is_etf", True),
            "aum_btoman": values.get("aum_btoman"),
            "p_nav_ratio": values.get("p_nav_ratio"),
            "bubble_pct": values.get("p_nav_ratio"),
            "last_updated": datetime.utcnow(),
            "metrics": {
                "values": values,
                "cold_start_pct": metrics_result["cold_start_pct"],
                "cold_start_labels": metrics_result["cold_start_labels"],
                "block_scoring": metrics_result["block_scoring"],
                "computed_at": metrics_result["computed_at"],
            },
            "score": {
                "score_total": score_result["score_total"],
                "score_return": score_result["score_return"],
                "score_risk": score_result["score_risk"],
                "score_cost": score_result["score_cost"],
                "score_liquidity": score_result["score_liquidity"],
                "signal": score_result["signal"],
                "signal_label_fa": score_result["signal_label_fa"],
                "reasons": score_result["reasons"],
                "scoring_version": score_result["scoring_version"],
                "is_cold_start_blocked": score_result["is_cold_start_blocked"],
            },
        }

    def list_funds(
        self,
        *,
        type_code: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "score_total",
        sort_desc: bool = True,
    ) -> dict[str, Any]:
        items = []
        for fund in self.catalog.list_all():
            if type_code and fund["type_code"] != type_code:
                continue
            full = self.compute_full(fund["symbol"])
            if full:
                items.append(full)

        # sort
        if sort_by in ("score_total", "p_nav_ratio", "aum_btoman", "bubble_pct"):
            items.sort(
                key=lambda x: (x.get("score", {}).get(sort_by) if sort_by == "score_total" else x.get(sort_by)) is None,
                reverse=sort_desc,
            )
            items.sort(
                key=lambda x: (x.get("score", {}).get(sort_by) if sort_by == "score_total" else x.get(sort_by)) or 0,
                reverse=sort_desc,
            )

        total = len(items)
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def compare(self, symbols: list[str]) -> list[dict[str, Any]]:
        out = []
        for s in symbols:
            full = self.compute_full(s)
            if full:
                out.append(full)
        return out

    def screener(
        self,
        *,
        type_code: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        sort_by: str = "score_total",
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Screener روی شاخص‌ها.

        filters: [{field, op, value, value2}] — op: eq/gt/gte/lt/lte/between/in
        """
        items = []
        for fund in self.catalog.list_all():
            if type_code and fund["type_code"] != type_code:
                continue
            full = self.compute_full(fund["symbol"])
            if full:
                items.append(full)

        if filters:
            filtered = []
            for item in items:
                metrics = item.get("metrics", {}).get("values", {})
                score = item.get("score", {})
                lookup = {**metrics, **{f"score_{k}": v for k, v in score.items() if k.startswith("score")}}
                ok = True
                for f in filters:
                    field = f["field"]
                    value = f.get("value")
                    op = f.get("op", "gte")
                    actual = lookup.get(field)
                    if actual is None:
                        ok = False
                        break
                    actual_f = float(actual)
                    value_f = float(value)
                    if op == "eq":
                        ok = actual_f == value_f
                    elif op == "gt":
                        ok = actual_f > value_f
                    elif op == "gte":
                        ok = actual_f >= value_f
                    elif op == "lt":
                        ok = actual_f < value_f
                    elif op == "lte":
                        ok = actual_f <= value_f
                    elif op == "between":
                        ok = value_f <= actual_f <= float(f.get("value2", value_f))
                    elif op == "in":
                        ok = str(actual) in [str(v) for v in f.get("value", [])]
                    if not ok:
                        break
                if ok:
                    filtered.append(item)
            items = filtered

        items.sort(
            key=lambda x: x.get("score", {}).get(sort_by) or 0,
            reverse=True,
        )
        total = len(items)
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── Bubble Monitor ──────────────────────────────────────────────
    def bubble_snapshot(self) -> list[dict[str, Any]]:
        out = []
        for fund in self.catalog.list_all():
            full = self.compute_full(fund["symbol"])
            if full and full.get("bubble_pct") is not None:
                out.append(
                    {
                        "symbol": fund["symbol"],
                        "nav": fund.get("nav_redeem"),
                        "market_price": fund.get("market_price"),
                        "bubble_pct": full["bubble_pct"],
                        "peer_median_bubble": None,
                        "ts": datetime.utcnow(),
                    }
                )
        # محاسبه میانه هم‌گروه
        by_type: dict[str, list[float]] = {}
        for item in out:
            type_code = self.catalog.get(item["symbol"])["type_code"]
            by_type.setdefault(type_code, []).append(float(item["bubble_pct"]))
        for item in out:
            type_code = self.catalog.get(item["symbol"])["type_code"]
            bubbles = sorted(by_type.get(type_code, []))
            if bubbles:
                n = len(bubbles)
                item["peer_median_bubble"] = bubbles[n // 2] if n % 2 else ((bubbles[n // 2 - 1] + bubbles[n // 2]) / 2)
        return out

    # ── Adapter Health ──────────────────────────────────────────────
    def adapter_health(self) -> list[dict[str, Any]]:
        return [
            self.fipiran.health_snapshot(),
            self.tsetmc.health_snapshot(),
        ]

    # ── Backtest (ساده — برای گزارش داخلی تیم) ─────────────────────
    def backtest_report(self, *, version: str | None = None) -> dict[str, Any]:
        """Hit Rate ساده روی داده seed — در نسخه واقعی از تاریخچه DB."""
        version = version or "v1.0"
        horizons = [3, 6, 12]
        hit_rates = {str(h): 0.0 for h in horizons}
        calibration = {"mean_abs_error": 0.0, "pearson": 0.0}

        # شبیه‌سازی با seed: صندوق‌هایی که امتیاز بالا دارند، بازده بالاتر دارند
        funds = []
        for fund in self.catalog.list_all():
            full = self.compute_full(fund["symbol"])
            if full and full["score"]["score_total"] is not None:
                funds.append(full)
        n = len(funds)
        if n:
            strong = [f for f in funds if (f["score"]["score_total"] or 0) >= 65]
            for h in horizons:
                hit_rates[str(h)] = round(len(strong) / n if strong else 0.0, 3)

        return {
            "version": version,
            "horizons_months": horizons,
            "hit_rates": hit_rates,
            "calibration": calibration,
            "sample_size": n,
            "generated_at": datetime.utcnow(),
        }

    # ── Adapter های واقعی (اختیاری — در صورتی که HTTP client باشد) ──
    async def sync_from_adapters(self, symbols: list[str] | None = None) -> int:
        """همگام‌سازی داده از Adapterهای واقعی — شمارنده به‌روزرسانی.

        در dev mode (بدون HTTP) چیزی را تغییر نمی‌دهد و ۰ برمی‌گرداند.
        """
        updated = 0
        targets = symbols or self.catalog.list_symbols()
        for symbol in targets:
            try:
                nav_data = await self.fipiran.get(symbol)
                price_data = await self.tsetmc.get(symbol)
                if nav_data.confidence > 0 and price_data.confidence > 0:
                    fund = self.catalog.get(symbol)
                    if fund is not None:
                        if nav_data.data.get("nav_redeem"):
                            fund["nav_redeem"] = nav_data.data["nav_redeem"]
                        if price_data.data.get("last_price"):
                            fund["market_price"] = price_data.data["last_price"]
                        updated += 1
            except Exception as exc:
                logger.warning("sync failed symbol=%s err=%s", symbol, exc.__class__.__name__)
        return updated
