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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# ── Default constants ────────────────────────────────────────────
_BASE_FX_CURRENT = 28500.0   # نرخ ارز مبنا (قابل تنظیم)
_BASE_FX_PRIOR = 24500.0     # نرخ ارز مبنا سال قبل
_BANK_INTEREST_RATE = 22.5   # نرخ سود بانکی (%)
_BOND_YIELD = 28.0           # بازده اوراق (%)
_INFLATION_RATE = 35.0       # نرخ تورم (%)
_USD_NIMA = 44500.0          # دلار نیما
_USD_FREE = 59500.0          # دلار آزاد
_INVESTABLE_CAPITAL = 500_000_000  # سرمایه کل برای position sizing (تومان)


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
        start_time = datetime.now()
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

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "symbol": symbol,
            "name": enriched.get("name", ""),
            "computed_at": datetime.now().isoformat(),
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

        f["update_timestamp"] = datetime.now().isoformat()
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

        # نرخ ارز مبنا
        f["base_fx_current"] = _BASE_FX_CURRENT
        f["base_fx_prior"] = _BASE_FX_PRIOR

        # EPS دلاری
        f["eps_dollar_ttm"] = round(f["eps_ttm"] / _BASE_FX_CURRENT, 2) if _BASE_FX_CURRENT > 0 else 0
        f["eps_dollar_last_year"] = round(f["eps_last_year"] / _BASE_FX_PRIOR, 2) if _BASE_FX_PRIOR > 0 else 0

        # رشد دلاری سود
        if f["eps_dollar_last_year"] > 0:
            f["eps_dollar_growth"] = round((f["eps_dollar_ttm"] / f["eps_dollar_last_year"]) - 1, 4)
        else:
            f["eps_dollar_growth"] = 0.0

        f["inflation_rate"] = _INFLATION_RATE

        # رشد اسمی EPS
        if f["eps_last_year"] > 0:
            f["eps_nominal_growth"] = round((f["eps_ttm"] / f["eps_last_year"]) - 1, 4)
        else:
            f["eps_nominal_growth"] = 0.0

        # رشد واقعی سود
        inflation_decimal = _INFLATION_RATE / 100.0
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

        # متغیرهای کلان
        f["bank_interest_rate"] = _BANK_INTEREST_RATE
        f["bond_yield"] = _BOND_YIELD
        f["usd_nima"] = _USD_NIMA
        f["usd_free"] = _USD_FREE
        f["usd_spread"] = round(_USD_FREE / _USD_NIMA, 2) if _USD_NIMA > 0 else 0

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

        # ── گردش شناور ──
        float_shares = enriched.get("free_float_pct", 0) or 0
        last_price = float(enriched.get("price_last", 0) or 0)
        if float_shares > 0 and last_price > 0:
            f["float_turnover_pct"] = round(
                100 * f["trade_value"] / (float(float_shares) * last_price), 2
            )
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

        # نسبت خالص حقوقی به شناور
        float_shares = int(enriched.get("free_float_pct", 0) or 0)
        if float_shares > 0:
            f["net_inst_ratio"] = round(f["net_inst_volume"] / float_shares * 100, 2)
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

        توجه: این بلوک به شدت به منابع داده خارجی وابسته است
        (کدال، اخبار، پایش تلگرام، تحلیل سیاسی).
        در این نسخه، مقادیر پیش‌فرض (صفر) برگردانده می‌شوند.
        """
        f: dict[str, Any] = {}

        for key in [
            "ceo_change_success", "ceo_change_fail",
            "agm_proximity", "agm_risk",
            "capital_inc_cash", "capital_inc_reval",
            "price_liberation", "gov_support",
            "heavy_legal_case", "telegram_hype",
            "end_of_month", "pre_holiday",
            "political_tension", "political_relief",
            "feedstock_meeting", "big_ipo",
            "sector_outflow", "sector_inflow",
            "market_index_3m",
        ]:
            f[key] = 0.0
        f["market_regime"] = 50.0  # پیش‌فرض خنثی

        # تشخیص تقویمی
        today = date.today()
        # روز پایانی ماه
        if today.month != (today + timedelta(days=1)).month:
            f["end_of_month"] = 1.0
        # روز قبل از تعطیلات (جمعه)
        if today.weekday() == 4:  # پنجشنبه
            f["pre_holiday"] = 1.0

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
            (0.01 * _INVESTABLE_CAPITAL) / max(risk_per_trade, 1), 0
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
        bank_rate = float(c.get("bank_interest_rate", 22.5))
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
        """S_E: رویدادهای مثبت و منفی."""
        positive = sum(float(g.get(k, 0)) for k in [
            "ceo_change_success", "capital_inc_cash", "capital_inc_reval",
            "price_liberation", "gov_support", "political_relief", "sector_inflow",
        ])
        negative = sum(float(g.get(k, 0)) for k in [
            "ceo_change_fail", "agm_risk", "heavy_legal_case", "telegram_hype",
            "political_tension", "feedstock_meeting",
        ])
        score = 50 + (positive * 15) - (negative * 20)
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
            "ceo_change_fail", "agm_risk", "heavy_legal_case", "telegram_hype",
            "end_of_month", "pre_holiday", "political_tension",
            "feedstock_meeting", "big_ipo", "sector_outflow", "market_index_3m",
        ] if float(g.get(k, 0)) > 0)
        penalty += neg_count * 0.04

        volatility = float(f_block.get("distance_to_limit", 0))
        if volatility > 2:
            penalty += 0.10

        return round(min(penalty, 0.35), 2)

    @staticmethod
    def _count_neg_events(g: dict[str, Any]) -> int:
        """تعداد رویدادهای منفی فعال."""
        return sum(1 for k in [
            "ceo_change_fail", "agm_risk", "heavy_legal_case", "telegram_hype",
            "end_of_month", "pre_holiday", "political_tension",
            "feedstock_meeting", "big_ipo", "sector_outflow", "market_index_3m",
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
        """محاسبه RSI."""
        if len(closes) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss < 1e-10:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _compute_macd_signal(closes: list[float]) -> float:
        """MACD signal: 1 = bullish, -1 = bearish, 0 = neutral."""
        if len(closes) < 26:
            return 0.0
        ema12 = sum(closes[-12:]) / 12
        ema26 = sum(closes[-26:]) / 26
        macd = ema12 - ema26
        signal = sum(closes[-9:]) / 9  # simplified
        if macd > signal:
            return 1.0
        elif macd < signal:
            return -1.0
        return 0.0

    @staticmethod
    def _compute_atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> float:
        """محاسبه ATR."""
        if len(closes) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        return sum(trs[-period:]) / period if trs else 0.0

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
