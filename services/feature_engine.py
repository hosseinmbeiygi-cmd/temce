"""
🏛️ Feature Engine — موتور محاسبه ۱۱۵ ویژگی استاندارد در ۸ بلوک

معماری:
  - از json/features.json به‌عنوان سورس آف ترث (schema) استفاده می‌کند
  - هر بلوک یک متد collector مجزا دارد
  - از BrsApiQueryService برای داده‌های real-time و تاریخی استفاده می‌کند
  - از QueueAnalysisService برای تحلیل صف (بلوک F) استفاده می‌کند
  - خروجی: دیکشنری تخت با کلیدهای 115 ویژگی + متادیتا

Usage:
    engine = FeatureEngine(brsapi, queue_service)
    result = await engine.compute_all_features("فولاد")
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from core.indicators import (
    compute_atr,
    compute_macd_signal,
    compute_rsi,
)
from core.logging import get_logger
from core.time import now_utc, utc_now_naive

logger = get_logger(__name__)

# ── Default constants (loaded from config/macroeconomics.yaml at runtime) ──────
_DEFAULT_MACRO_ECONOMICS = {
    "base_fx_current": 28500.0,
    "base_fx_prior": 24500.0,
    "bank_interest_rate": 22.5,
    "bond_yield": 28.0,
    "inflation_rate": 35.0,
    "usd_nima": 44500.0,
    "usd_free": 59500.0,
}
_DEFAULT_PORTFOLIO = {
    "investable_capital": 500_000_000,
}


def _load_macroeconomics_config() -> tuple[dict[str, float], dict[str, float]]:
    """Load macroeconomics constants from config/macetheconomics.yaml.

    Returns (macro_economics, portfolio) dicts, falling back to hardcoded
    defaults if the file is missing or malformed.
    """
    try:
        import os

        import yaml
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config", "macroeconomics.yaml"
        )
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        macro = cfg.get("macroeconomics", {})
        portfolio = cfg.get("portfolio", {})
        if macro and isinstance(macro, dict):
            me = {k: float(v) for k, v in macro.items()}
        else:
            me = dict(_DEFAULT_MACRO_ECONOMICS)
        if portfolio and isinstance(portfolio, dict):
            pf = {k: float(v) for k, v in portfolio.items()}
        else:
            pf = dict(_DEFAULT_PORTFOLIO)
        return me, pf
    except Exception as e:
        logger.debug("Could not load macroeconomics.yaml: %s — using defaults", e)
        return dict(_DEFAULT_MACRO_ECONOMICS), dict(_DEFAULT_PORTFOLIO)


_macroeconomics, _portfolio_config = _load_macroeconomics_config()


class FeatureEngine:
    """
    موتور مرکزی محاسبه ۱۱۵ ویژگی استاندارد در ۸ بلوک.

    Args:
        brsapi: BrsApiQueryService instance
        queue_service: QueueAnalysisService instance (اختیاری — برای بلوک F)
    """

    def __init__(
        self,
        brsapi_query_service: Any,
        queue_analysis_service: Any | None = None,
    ) -> None:
        self._brsapi = brsapi_query_service
        self._queue_service = queue_analysis_service

        # بارگذاری JSON ویژگی‌ها
        self._features_schema: dict[str, Any] = {}
        self._load_schema()

    def _load_schema(self) -> None:
        """بارگذاری json/features.json به‌عنوان schema."""
        try:
            json_path = Path(__file__).resolve().parent.parent / "json" / "features.json"
            if json_path.exists():
                with open(json_path, encoding="utf-8") as f:
                    self._features_schema = json.load(f)
                logger.info(
                    "FeatureEngine: loaded %d features in %d blocks",
                    self._features_schema.get("meta", {}).get("total_features", 0),
                    self._features_schema.get("meta", {}).get("blocks", 0),
                )
            else:
                logger.warning("FeatureEngine: features.json not found at %s", json_path)
        except Exception:
            logger.exception("FeatureEngine: failed to load features.json")

    # ═══════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════

    async def compute_all_features(
        self,
        symbol: str,
        queue_service: Any | None = None,
    ) -> dict[str, Any]:
        """
        محاسبه تمام ۱۱۵ ویژگی برای یک نماد.

        Args:
            symbol: شناسه نماد (مثلاً "فولاد")
            queue_service: QueueAnalysisService (اختیاری)

        Returns:
            dict با کلیدهای feature key + value + metadata
        """
        start_time = now_utc()
        use_queue_service = queue_service or self._queue_service

        # ── 1. Gather raw data from DB ──
        enriched = await self._brsapi.get_enriched_symbol_detail(symbol) or {}
        historical = await self._brsapi.get_historical_daily(symbol, limit=100) or []
        candles = await self._brsapi.get_candlesticks(symbol, limit=100) or []

        # ── 2. Queue analysis (if available) ──
        queue_result: dict[str, Any] = {}
        if use_queue_service:
            try:
                queue_result = await use_queue_service.analyze_symbol(symbol)
            except Exception:
                logger.exception("Queue analysis failed for %s, continuing without queue", symbol)

        # ── 3. Compute each block ──
        block_a = self._compute_block_a(enriched)
        block_b = self._compute_block_b(enriched)
        block_c = self._compute_block_c(enriched, block_b)
        block_d = self._compute_block_d(enriched, historical)
        block_e = self._compute_block_e(enriched)
        block_f = self._compute_block_f(enriched, queue_result)
        block_g = self._compute_block_g()
        block_h = self._compute_block_h(
            enriched, block_a, block_b, block_c, block_d, block_e, block_f, block_g, queue_result,
        )

        # ── 4. Merge all features ──
        features: dict[str, Any] = {}
        features.update(block_a)
        features.update(block_b)
        features.update(block_c)
        features.update(block_d)
        features.update(block_e)
        features.update(block_f)
        features.update(block_g)
        features.update(block_h)

        elapsed = (now_utc() - start_time).total_seconds()

        return {
            "symbol": symbol,
            "name": enriched.get("name", ""),
            "computed_at": utc_now_naive().isoformat(),
            "computation_time_ms": round(elapsed * 1000, 1),
            "total_features": len(features),
            "version": self._features_schema.get("meta", {}).get("version", "unknown"),
            "features": features,
            "metadata": {
                "data_sources": {
                    "enriched_detail": bool(enriched),
                    "historical_daily": len(historical),
                    "candles": len(candles),
                    "queue_analysis": bool(queue_result),
                },
            },
        }

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK A: Identity & Data Quality (IDs 1-10)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_a(self, enriched: dict[str, Any]) -> dict[str, Any]:
        f: dict[str, Any] = {}

        f["ticker"] = enriched.get("symbol", "")
        f["isin"] = enriched.get("isin", "")
        f["market"] = self._determine_market(enriched)
        f["industry_id"] = enriched.get("sector_id", 0)
        f["industry_name"] = enriched.get("sector", "")

        # سهام شناور آزاد — از free_float_pct و shares_count
        free_float_pct = float(enriched.get("free_float_pct", 0) or 0)
        shares_count = float(enriched.get("shares_count", 0) or 0)
        f["float_shares"] = int(shares_count * free_float_pct / 100) if free_float_pct > 0 else 0

        f["update_timestamp"] = utc_now_naive().isoformat()
        f["data_freshness_quote"] = 0  # real-time (داده تازه است)
        f["data_freshness_candle"] = 0

        # کامل بودن داده — درصد ستون‌های غیرتهی
        non_null = sum(1 for v in enriched.values() if v is not None and v != 0 and v != "")
        total = max(len(enriched), 1)
        f["data_completeness"] = round(non_null / total * 100, 1)

        return f

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK B: Fundamental Data (IDs 11-25)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_b(self, enriched: dict[str, Any]) -> dict[str, Any]:
        f: dict[str, Any] = {}

        # EPS از snapshot یا detail
        eps_raw = float(enriched.get("eps", 0) or 0)
        f["eps_ttm"] = eps_raw * 4 if eps_raw > 0 else 0  # تعدیل به 12 ماه
        f["eps_last_year"] = eps_raw * 3 if eps_raw > 0 else 0  # تخمین سال قبل

        me = _macroeconomics
        # نرخ ارز مبنا
        f["base_fx_current"] = me["base_fx_current"]
        f["base_fx_prior"] = me["base_fx_prior"]

        # EPS دلاری
        f["eps_dollar_ttm"] = round(f["eps_ttm"] / me["base_fx_current"], 2) if me["base_fx_current"] > 0 else 0
        f["eps_dollar_last_year"] = round(f["eps_last_year"] / me["base_fx_prior"], 2) if me["base_fx_prior"] > 0 else 0

        # رشد دلاری سود
        if f["eps_dollar_last_year"] > 0:
            f["eps_dollar_growth"] = round((f["eps_dollar_ttm"] / f["eps_dollar_last_year"]) - 1, 4)
        else:
            f["eps_dollar_growth"] = 0.0

        me = _macroeconomics
        f["inflation_rate"] = me["inflation_rate"]

        # رشد اسمی EPS
        if f["eps_last_year"] > 0:
            f["eps_nominal_growth"] = round((f["eps_ttm"] / f["eps_last_year"]) - 1, 4)
        else:
            f["eps_nominal_growth"] = 0.0

        # رشد واقعی سود
        inflation_decimal = me["inflation_rate"] / 100.0
        f["eps_real_growth"] = round(
            (1 + f["eps_nominal_growth"]) / (1 + inflation_decimal) - 1, 4
        ) if inflation_decimal > 0 else f["eps_nominal_growth"]

        # سود خالص (تخمین از market_value / PE)
        market_value = float(enriched.get("market_value", 0) or 0)
        pe_ratio = float(enriched.get("pe_ratio", 0) or 0)
        f["net_profit"] = round(market_value / pe_ratio, 0) if pe_ratio > 0 else 0

        # زیان انباشته و سرمایه — معمولاً در snapshot موجود نیست
        f["accumulated_loss"] = 0.0
        f["registered_capital"] = float(enriched.get("shares_count", 0) or 0)
        if f["registered_capital"]:
            f["loss_to_capital_ratio"] = round(f["accumulated_loss"] / f["registered_capital"], 4)
        else:
            f["loss_to_capital_ratio"] = 0.0

        f["gross_margin"] = 0.0  # نیاز به صورت‌های مالی کدال

        return f

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK C: Valuation & Macro (IDs 26-35)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_c(
        self,
        enriched: dict[str, Any],
        block_b: dict[str, Any],
    ) -> dict[str, Any]:
        f: dict[str, Any] = {}

        f["last_price"] = float(enriched.get("price_last", 0) or 0)
        f["pe_ratio"] = float(enriched.get("pe_ratio", 0) or 0)
        f["industry_pe"] = float(enriched.get("group_pe_ratio", 0) or 0)

        # P/E نسبی
        if f["industry_pe"] > 0:
            f["pe_relative"] = round(f["pe_ratio"] / f["industry_pe"], 2)
        else:
            f["pe_relative"] = 0.0

        # بازده سود
        if f["last_price"] > 0 and block_b.get("eps_ttm", 0) > 0:
            f["earnings_yield"] = round((block_b["eps_ttm"] * 4 / f["last_price"]) * 100, 2)
        else:
            f["earnings_yield"] = 0.0

        me = _macroeconomics

        # متغیرهای کلان
        f["bank_interest_rate"] = me["bank_interest_rate"]
        f["bond_yield"] = me["bond_yield"]
        f["usd_nima"] = me["usd_nima"]
        f["usd_free"] = me["usd_free"]
        f["usd_spread"] = round(me["usd_free"] / me["usd_nima"], 2) if me["usd_nima"] > 0 else 0

        return f

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK D: Daily Trading & Technical (IDs 36-50)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_d(
        self,
        enriched: dict[str, Any],
        historical: list[dict[str, Any]],
    ) -> dict[str, Any]:
        f: dict[str, Any] = {}

        # ── Data from snapshot ──
        f["volume"] = int(enriched.get("trade_volume", 0) or 0)
        f["trade_value"] = float(enriched.get("trade_value", 0) or 0)
        f["price_change_pct"] = float(enriched.get("price_last_change_pct", 0) or 0)

        # ── استخراج سری‌های قیمت و حجم از historical ──
        closes = self._extract_series(historical, "price_close")
        volumes = self._extract_series(historical, "trade_volume")
        highs = self._extract_series(historical, "price_max")
        lows = self._extract_series(historical, "price_min")

        # ── میانگین حجم ۵۰ روزه ──
        vol_50 = volumes[-50:] if len(volumes) >= 50 else volumes
        avg_vol_50 = sum(vol_50) / max(len(vol_50), 1)
        f["avg_volume_50"] = int(avg_vol_50)

        # ── جهش حجمی ──
        if avg_vol_50 > 0:
            f["volume_spike"] = round(f["volume"] / avg_vol_50, 2)
        else:
            f["volume_spike"] = 1.0

        # ── گردش شناور ── (تعداد سهام شناور = shares_count * free_float_pct / 100)
        shares_count = float(enriched.get("shares_count", 0) or 0)
        free_float_pct = float(enriched.get("free_float_pct", 0) or 0)
        last_price = float(enriched.get("price_last", 0) or 0)
        # Safe guard: free_float_pct is a percent (0-100); clamp to avoid
        # inflated scale when bad data carries fractions >100 or negatives.
        _ff = min(max(free_float_pct, 0.0), 100.0)
        float_shares_count = shares_count * _ff / 100.0 if shares_count > 0 else 0
        _denom = float_shares_count * last_price
        if _denom > 1e-9:
            f["float_turnover_pct"] = round(100 * f["trade_value"] / _denom, 2)
        else:
            f["float_turnover_pct"] = 0.0

        # ── SMA 20 ──
        if len(closes) >= 20:
            f["sma_20"] = round(sum(closes[-20:]) / 20, 0)
        else:
            f["sma_20"] = closes[-1] if closes else 0

        # ── RSI 14 ──
        f["rsi_14"] = round(self._compute_rsi(closes, 14), 1)

        # ── MACD ──
        f["macd_signal"] = self._compute_macd_signal(closes)

        # ── ATR 14 ──
        f["atr_14"] = round(self._compute_atr(highs, lows, closes, 14), 0)

        # ── قیمت فرابورس ──
        f["farabourse_price"] = 0.0  # نیاز به منبع داده جداگانه
        f["farabourse_volume_ratio"] = 0.0

        # ── شکست مقاومت ──
        f["breakout_flag"] = 1.0 if self._detect_breakout(closes) else 0.0

        # ── نسبت حجم اولیه (placeholder) ──
        f["early_volume_ratio"] = 0.0  # نیاز به داده ریزمعاملات

        # ── روند ۲۰ روزه ──
        f["trend_20d"] = self._compute_trend(closes)

        return f

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK E: Money Flow (IDs 51-60)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_e(self, enriched: dict[str, Any]) -> dict[str, Any]:
        f: dict[str, Any] = {}

        f["inst_buy_volume"] = int(enriched.get("buy_legal_volume", 0) or 0)
        f["inst_sell_volume"] = int(enriched.get("sell_legal_volume", 0) or 0)
        f["net_inst_volume"] = f["inst_buy_volume"] - f["inst_sell_volume"]

        # نسبت خالص حقوقی به شناور (بر حسب تعداد سهام شناور، نه درصد)
        shares_count = float(enriched.get("shares_count", 0) or 0)
        free_float_pct = float(enriched.get("free_float_pct", 0) or 0)
        _ff2 = min(max(free_float_pct, 0.0), 100.0)
        float_shares_count = shares_count * _ff2 / 100.0 if shares_count > 0 else 0
        if float_shares_count > 1e-9:
            f["net_inst_ratio"] = round(f["net_inst_volume"] / float_shares_count * 100, 2)
        else:
            f["net_inst_ratio"] = 0.0

        f["inst_buy_count"] = int(enriched.get("buy_legal_count", 0) or 0)
        f["inst_sell_count"] = int(enriched.get("sell_legal_count", 0) or 0)
        f["retail_buy_volume"] = int(enriched.get("buy_real_volume", 0) or 0)
        f["retail_sell_volume"] = int(enriched.get("sell_real_volume", 0) or 0)
        f["retail_count_change"] = 0  # نیاز به داده ماهانه

        # نسبت حقیقی به حقوقی
        if f["inst_buy_volume"] > 0:
            f["retail_to_inst_ratio"] = round(f["retail_buy_volume"] / f["inst_buy_volume"], 2)
        else:
            f["retail_to_inst_ratio"] = 0.0

        return f

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK F: Microstructure & Queue (IDs 61-75)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_f(
        self,
        enriched: dict[str, Any],
        queue_result: dict[str, Any],
    ) -> dict[str, Any]:
        f: dict[str, Any] = {}

        # ── Microstructure (IDs 61-70) ──
        f["trade_count"] = int(enriched.get("trade_count", 0) or 0)

        volume = int(enriched.get("trade_volume", 0) or 0)
        trade_count = f["trade_count"]
        f["avg_trade_size"] = round(volume / trade_count, 0) if trade_count > 0 else 0

        # max_block_volume, block_trade_detected — نیاز به داده ریزمعاملات
        f["max_block_volume"] = int(volume * 0.1)  # تخمین
        f["block_trade_detected"] = 0.0

        # VWAP — تخمین از قیمت‌های روز
        last_price = float(enriched.get("price_last", 0) or 0)
        price_close = float(enriched.get("price_close", 0) or 0)
        price_first = float(enriched.get("price_first", 0) or 0)
        price_max = float(enriched.get("price_max", 0) or 0)
        price_min = float(enriched.get("price_min", 0) or 0)
        f["vwap"] = round((price_first + price_max + price_min + price_close) / 4, 0)
        f["last_vs_vwap"] = round(last_price - f["vwap"], 0) if f["vwap"] else 0

        # کد به کد — نیاز به الگوریتم خاص
        f["code2code_buy"] = 0.0
        f["code2code_sell"] = 0.0

        # توزیع معاملات
        real_ratio = self._compute_real_legal_ratio(enriched)
        if real_ratio > 0.6:
            f["trade_distribution"] = "retail"
        elif real_ratio < 0.3:
            f["trade_distribution"] = "institutional"
        else:
            f["trade_distribution"] = "mixed"

        # امتیاز میکروساختار
        f["microstructure_score"] = self._compute_micro_score(f)

        # ── Queue features (IDs 71-75) — از QueueAnalysisService ──
        f["queue_status"] = queue_result.get("queue_status", "NONE")
        f["queue_volume_ratio"] = queue_result.get("queue_volume_ratio", 0.0)
        f["queue_days_streak"] = queue_result.get("queue_days_streak", 0)
        f["queue_type_change"] = queue_result.get("queue_type_change", "NO_CHANGE")
        f["distance_to_limit"] = queue_result.get("distance_to_limit", 0.0)

        return f

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK G: Events & Qualitative Risk (IDs 76-95)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_g(self) -> dict[str, Any]:
        """
        بلوک رویدادها و ریسک‌های کیفی.

        ویژگی‌های تقویمی (بدون نیاز به داده خارجی) محاسبه می‌شوند.
        سایر ویژگی‌های رویدادی به منابع داده خارجی نیاز دارند
        (کدال، اخبار، پایش تلگرام) و در این نسخه پیاده‌سازی نشده‌اند.
        """
        f: dict[str, Any] = {}

        f["market_regime"] = 50.0

        today = date.today()

        f["end_of_month"] = 1.0 if today.month != (today + timedelta(days=1)).month else 0.0

        f["pre_holiday"] = 1.0 if today.weekday() == 4 else 0.0

        f["agm_proximity"] = 1.0 if (today.month == 12 and today.day >= 22) else (0.5 if today.day == 1 else 0.0)

        f["market_index_3m"] = 0.3 if today.weekday() == 5 else 0.0

        return f

    # ═══════════════════════════════════════════════════════════════
    #  BLOCK H: Scores, Penalty & Final Decision (IDs 96-115)
    # ═══════════════════════════════════════════════════════════════

    def _compute_block_h(
        self,
        enriched: dict[str, Any],
        block_a: dict[str, Any],
        block_b: dict[str, Any],
        block_c: dict[str, Any],
        block_d: dict[str, Any],
        block_e: dict[str, Any],
        block_f: dict[str, Any],
        block_g: dict[str, Any],
        queue_result: dict[str, Any],
    ) -> dict[str, Any]:
        f: dict[str, Any] = {}

        # ── 8 Sub-scores (هر کدام 0-100) ──

        # S_F: امتیاز بنیادی
        score_f = self._score_fundamental(block_b)
        f["score_fundamental"] = score_f

        # S_V: امتیاز ارزش‌گذاری
        score_v = self._score_valuation(block_c)
        f["score_valuation"] = score_v

        # S_T: امتیاز تکنیکال با پشتیبانی صف
        score_t = self._score_technical(block_d, block_f, queue_result)
        f["score_technical"] = score_t

        # S_L: امتیاز نقدشوندگی با پشتیبانی صف
        score_l = self._score_liquidity(block_a, block_d, block_f, queue_result)
        f["score_liquidity"] = score_l

        # S_O: امتیاز جریان پول با پشتیبانی صف
        score_o = self._score_orderflow(block_e, block_f, queue_result)
        f["score_orderflow"] = score_o

        # S_M: امتیاز میکروساختار
        score_m = block_f.get("microstructure_score", 50.0)
        f["score_micro"] = score_m

        # S_K: امتیاز کلان
        score_k = self._score_macro(block_c, block_g)
        f["score_macro"] = score_k

        # S_E: امتیاز رویدادی
        score_e = self._score_event(block_g)
        f["score_event"] = score_e

        # ── اوزان پیش‌فرض ──
        weights = {
            "score_fundamental": 0.22,
            "score_valuation": 0.12,
            "score_technical": 0.18,
            "score_liquidity": 0.12,
            "score_orderflow": 0.14,
            "score_micro": 0.08,
            "score_macro": 0.08,
            "score_event": 0.06,
        }

        # ── Raw Score (مجموع وزنی) ──
        raw_score = sum(
            score * weights[key]
            for key, score in [
                ("score_fundamental", score_f),
                ("score_valuation", score_v),
                ("score_technical", score_t),
                ("score_liquidity", score_l),
                ("score_orderflow", score_o),
                ("score_micro", score_m),
                ("score_macro", score_k),
                ("score_event", score_e),
            ]
        )
        f["raw_score"] = round(raw_score, 2)

        # ── Penalty (ضریب جریمه با پشتیبانی صف) ──
        penalty = self._compute_penalty(block_f, block_g)
        f["penalty"] = penalty

        # ── Final Score ──
        final_score = round(raw_score * (1 - penalty), 2)
        f["final_score"] = final_score

        # ── تعداد رویدادهای منفی ──
        neg_events = self._count_neg_events(block_g)
        f["neg_events_count"] = neg_events

        # ── قانون 50-30 ──
        f["rule_50_30"] = 1.0 if neg_events >= 3 else 0.0  # 1 = REJECT

        # ── تصمیم نهایی با Hard Rules ──
        decision, override = self._compute_final_decision(final_score, block_f, queue_result)
        f["final_decision"] = decision
        f["decision_override"] = override

        # ── حد ضرر و هدف ──
        last_price = float(enriched.get("price_last", 0) or 0)
        atr_14 = block_d.get("atr_14", 0)

        f["stop_loss_7"] = round(last_price * 0.93, 0) if last_price else 0
        f["stop_loss_atr"] = round(last_price - 2 * atr_14, 0) if last_price and atr_14 else 0
        f["stop_loss"] = max(f["stop_loss_7"], f["stop_loss_atr"])
        f["target_profit"] = round(last_price * 1.20, 0) if last_price else 0

        # حجم معامله
        risk_per_trade = last_price - f["stop_loss"]
        f["position_size"] = round(
            (0.01 * _portfolio_config["investable_capital"]) / max(risk_per_trade, 1), 0
        ) if risk_per_trade > 0 else 0

        # ── خلاصه تصمیم ──
        f["verdict_summary_with_queue"] = self._build_verdict(
            final_score, decision, override, block_f,
        )

        return f

    # ═══════════════════════════════════════════════════════════════
    #  SCORING HELPER METHODS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _score_fundamental(b: dict[str, Any]) -> float:
        """S_F: ترکیب EPS_real_growth, net_profit, loss_to_capital_ratio, gross_margin."""
        score = 50.0

        eps_growth = float(b.get("eps_real_growth", 0))
        if eps_growth > 0.2:
            score += 25
        elif eps_growth > 0.1:
            score += 15
        elif eps_growth > 0:
            score += 5
        elif eps_growth < -0.1:
            score -= 20

        net_profit = float(b.get("net_profit", 0))
        if net_profit > 10_000:
            score += 10
        elif net_profit > 1_000:
            score += 5

        loss_ratio = float(b.get("loss_to_capital_ratio", 0))
        if loss_ratio > 1:
            score -= 30
        elif loss_ratio > 0.5:
            score -= 10

        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _score_valuation(c: dict[str, Any]) -> float:
        """S_V: ترکیب PE_relative و earnings_yield."""
        score = 50.0

        pe_rel = float(c.get("pe_relative", 0))
        if 0 < pe_rel < 0.8:
            score += 25
        elif pe_rel < 1.2:
            score += 10
        elif pe_rel > 2:
            score -= 20
        elif pe_rel > 1.5:
            score -= 5

        earnings_yield = float(c.get("earnings_yield", 0))
        bank_rate = float(c.get("bank_interest_rate", _macroeconomics["bank_interest_rate"]))
        if earnings_yield > bank_rate:
            score += 20
        elif earnings_yield > bank_rate * 0.7:
            score += 5
        else:
            score -= 10

        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _score_technical(
        d: dict[str, Any],
        f_block: dict[str, Any],
        queue_result: dict[str, Any],
    ) -> float:
        """S_T: ترکیب volume_spike, RSI, MACD, breakout, trend + پشتیبانی صف."""
        queue_streak = int(f_block.get("queue_days_streak", 0))

        # اگر تداوم صف >= 2 روز باشد، RSI/MACD نادیده گرفته می‌شود
        if queue_streak >= 2:
            # نادیده گرفتن RSI/MACD — استفاده از شدت صف و فاصله تا دامنه
            volume_ratio = float(f_block.get("queue_volume_ratio", 0))
            distance = float(f_block.get("distance_to_limit", 0))
            return round(
                (volume_ratio * 50) + ((100 - min(distance, 100)) * 50), 1
            )

        score = 50.0
        volume_spike = float(d.get("volume_spike", 1))
        if volume_spike > 3:
            score += 20
        elif volume_spike > 2:
            score += 10

        rsi = float(d.get("rsi_14", 50))
        if 30 < rsi < 70:
            score += 10
        elif rsi <= 30:
            score += 5  # oversold
        elif rsi >= 80:
            score -= 10  # overbought extreme

        macd = float(d.get("macd_signal", 0))
        if macd > 0:
            score += 10
        elif macd < 0:
            score -= 10

        if d.get("breakout_flag", 0):
            score += 15

        trend = d.get("trend_20d", "neutral")
        if trend == "bullish":
            score += 10
        elif trend == "bearish":
            score -= 10

        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _score_liquidity(
        a: dict[str, Any],
        d: dict[str, Any],
        f_block: dict[str, Any],
        queue_result: dict[str, Any],
    ) -> float:
        """S_L: float_turnover + volume + پشتیبانی صف."""
        score = 50.0

        turnover = float(d.get("float_turnover_pct", 0))
        if turnover > 5:
            score += 20
        elif turnover > 2:
            score += 10
        elif turnover < 0.5:
            score -= 15

        volume = int(d.get("volume", 0))
        if volume > 10_000_000:
            score += 15
        elif volume > 1_000_000:
            score += 5
        elif volume < 100_000:
            score -= 10

        # پشتیبانی صف
        queue_status = f_block.get("queue_status", "NONE")
        if queue_status == "BUY_QUEUE":
            score += 15
        elif queue_status == "SELL_QUEUE":
            score *= 0.5

        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _score_orderflow(
        e: dict[str, Any],
        f_block: dict[str, Any],
        queue_result: dict[str, Any],
    ) -> float:
        """S_O: net_inst_ratio + retail_ratio + پشتیبانی صف."""
        score = 50.0

        net_ratio = float(e.get("net_inst_ratio", 0))
        if net_ratio > 5:
            score += 25
        elif net_ratio > 1:
            score += 10
        elif net_ratio < -5:
            score -= 25
        elif net_ratio < -1:
            score -= 10

        retail_ratio = float(e.get("retail_to_inst_ratio", 0))
        if retail_ratio > 1.5:
            score -= 15  # احتمال کد به کد
        elif retail_ratio < 0.5:
            score += 10  # نهادهای بزرگ خریدارند

        # پشتیبانی صف
        queue_type_change = f_block.get("queue_type_change", "NO_CHANGE")
        if queue_type_change == "NEW_BUY_QUEUE":
            score += 20
        elif queue_type_change == "NEW_SELL_QUEUE":
            score -= 20

        queue_ratio = float(f_block.get("queue_volume_ratio", 0))
        score = score * (1 + queue_ratio)

        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _score_macro(c: dict[str, Any], g: dict[str, Any]) -> float:
        """S_K: تورم، شکاف ارز، رژیم بازار."""
        score = 50.0

        usd_spread = float(c.get("usd_spread", 1))
        if usd_spread > 1.3:
            score -= 20
        elif usd_spread > 1.1:
            score -= 5
        else:
            score += 5

        market_regime = float(g.get("market_regime", 50))
        if market_regime >= 70:
            score += 15
        elif market_regime <= 30:
            score -= 15

        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _score_event(g: dict[str, Any]) -> float:
        """S_E: رویدادهای تقویمی فعال."""
        calendar_features = sum(float(g.get(k, 0)) for k in [
            "end_of_month", "pre_holiday", "agm_proximity", "market_index_3m",
        ])
        score = 50 + (calendar_features * 10)
        return max(0, min(100, round(score, 1)))

    # ═══════════════════════════════════════════════════════════════
    #  PENALTY & DECISION HELPERS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _compute_penalty(f_block: dict[str, Any], g: dict[str, Any]) -> float:
        """محاسبه ضریب جریمه (۰ تا ۰.۳۵)."""
        penalty = 0.0

        queue_status = f_block.get("queue_status", "NONE")
        queue_streak = int(f_block.get("queue_days_streak", 0))

        if queue_status == "SELL_QUEUE" and queue_streak >= 3:
            penalty = min(penalty + 0.25, 0.50)

        neg_count = sum(1 for k in [
            "end_of_month", "pre_holiday", "agm_proximity", "market_index_3m",
        ] if float(g.get(k, 0)) > 0)
        penalty += neg_count * 0.04

        volatility = float(f_block.get("distance_to_limit", 0))
        if volatility > 2:
            penalty += 0.10

        return round(min(penalty, 0.35), 2)

    @staticmethod
    def _count_neg_events(g: dict[str, Any]) -> int:
        """تعداد رویدادهای منفی فعال (تقویمی)."""
        return sum(1 for k in [
            "end_of_month", "pre_holiday", "agm_proximity", "market_index_3m",
        ] if float(g.get(k, 0)) > 0)

    @staticmethod
    def _compute_final_decision(
        final_score: float,
        f_block: dict[str, Any],
        queue_result: dict[str, Any],
    ) -> tuple[str, str]:
        """تصمیم نهایی با Hard Rules صف."""
        queue_status = f_block.get("queue_status", "NONE")
        queue_ratio = float(f_block.get("queue_volume_ratio", 0))
        queue_streak = int(f_block.get("queue_days_streak", 0))
        queue_type_change = f_block.get("queue_type_change", "NO_CHANGE")

        # قانون 1 (بحرانی): NEW_SELL_QUEUE + ratio > 0.6 → REJECT
        if queue_type_change == "NEW_SELL_QUEUE" and queue_ratio > 0.6:
            return "REJECT", f"Hard Rule 1: NEW_SELL_QUEUE با شدت {queue_ratio:.0%} — override مطلق"

        # قانون 2: BUY_QUEUE + streak < 3 + ratio > 0.7 → BUY
        if queue_status == "BUY_QUEUE" and queue_streak < 3 and queue_ratio > 0.7:
            return "BUY", f"Hard Rule 2: BUY_QUEUE قوی با شدت {queue_ratio:.0%}"

        # قانون 3: SELL_QUEUE + streak > 1 → REJECT
        if queue_status == "SELL_QUEUE" and queue_streak > 1:
            return "REJECT", f"Hard Rule 3: SELL_QUEUE پایدار برای {queue_streak} روز"

        # قانون 4: عادی
        if final_score >= 75:
            return "BUY", ""
        elif final_score >= 60:
            return "WATCHLIST", ""
        elif final_score >= 40:
            return "HOLD", ""
        elif final_score >= 25:
            return "REDUCE", ""
        else:
            return "REJECT", ""

    @staticmethod
    def _build_verdict(
        final_score: float,
        decision: str,
        override: str,
        f_block: dict[str, Any],
    ) -> str:
        """خلاصه انسانی تصمیم."""
        parts = [f"امتیاز نهایی: {final_score}", f"تصمیم: {decision}"]

        queue_status = f_block.get("queue_status", "NONE")
        if queue_status == "BUY_QUEUE":
            parts.append("صف خرید فعال")
        elif queue_status == "SELL_QUEUE":
            parts.append("⚠️ صف فروش فعال")

        queue_ratio = float(f_block.get("queue_volume_ratio", 0))
        if queue_ratio > 0.7:
            parts.append(f"شدت صف: {queue_ratio:.0%}")

        if override:
            parts.append(f"⚠️ {override}")

        return " | ".join(parts)

    # ═══════════════════════════════════════════════════════════════
    #  TECHNICAL ANALYSIS HELPERS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_series(
        historical: list[dict[str, Any]],
        field: str,
    ) -> list[float]:
        """استخراج یک سری زمانی از data تاریخی (از قدیم به جدید)."""
        values = []
        for row in reversed(historical):
            val = row.get(field, 0)
            if val is not None:
                values.append(float(val))
        return values

    @staticmethod
    def _compute_rsi(closes: list[float], period: int = 14) -> float:
        """محاسبه RSI (تفبه به core.indicators)."""
        return compute_rsi(closes, period)

    @staticmethod
    def _compute_macd_signal(closes: list[float]) -> float:
        """MACD signal: 1 = bullish, -1 = bearish, 0 = neutral."""
        return compute_macd_signal(closes)

    @staticmethod
    def _compute_atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> float:
        """محاسبه ATR."""
        result = compute_atr(highs, lows, closes, period)
        return result if result is not None else 0.0

    @staticmethod
    def _detect_breakout(closes: list[float], lookback: int = 20) -> bool:
        """تشخیص شکست resistance ساده."""
        if len(closes) < lookback + 1:
            return False
        recent_high = max(closes[-(lookback + 1):-1])
        return closes[-1] > recent_high and closes[-2] <= recent_high

    @staticmethod
    def _compute_trend(closes: list[float]) -> str:
        """تشخیص روند ۲۰ روزه."""
        if len(closes) < 20:
            return "neutral"
        sma5 = sum(closes[-5:]) / 5
        sma20 = sum(closes[-20:]) / 20
        roc = (closes[-1] - closes[-20]) / max(closes[-20], 1)
        if sma5 > sma20 and roc > 0.02:
            return "bullish"
        elif sma5 < sma20 and roc < -0.02:
            return "bearish"
        return "neutral"

    @staticmethod
    def _compute_real_legal_ratio(enriched: dict[str, Any]) -> float:
        """نسبت خرید حقیقی به کل خرید."""
        real = float(enriched.get("buy_real_volume", 0) or 0)
        legal = float(enriched.get("buy_legal_volume", 0) or 0)
        total = real + legal
        return real / total if total > 0 else 0.5

    @staticmethod
    def _compute_micro_score(f: dict[str, Any]) -> float:
        """امتیاز میکروساختار (ترکیبی از trade_count, avg_trade_size, block_trade)."""
        score = 50.0
        if f.get("block_trade_detected", 0):
            score += 20
        avg_size = float(f.get("avg_trade_size", 0))
        if avg_size > 100_000:
            score += 15
        elif avg_size < 1_000:
            score -= 10
        return max(0, min(100, round(score, 1)))

    @staticmethod
    def _determine_market(enriched: dict[str, Any]) -> str:
        """تشخیص نوع بازار."""
        isin = (enriched.get("isin") or "").upper()
        board = (enriched.get("board") or "").lower()
        if isin.startswith("IROF"):
            return "farabourse"
        if isin.startswith("IRO"):
            return "bourse"
        if "پایه" in board:
            return "base"
        if "فرابورس" in board:
            return "farabourse"
        return "bourse"
