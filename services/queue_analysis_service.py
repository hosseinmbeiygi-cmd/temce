"""
📊 Queue Analysis Service — پلی بین داده‌های واقعی و موتور تحلیل صف

این سرویس:
  1. از BrsApiQueryService داده‌های real-time را می‌گیرد (tmin, tmax, bid/ask)
  2. تاریخچه روزانه را برای محاسبه تداوم صف (streak) می‌خواند
  3. `compute_queue_features()` را از `queue_analysis.py` صدا می‌زند
  4. قوانین تعدیل امتیاز (S_L, S_T, S_O) و Hard Rules را اعمال می‌کند
  5. نتیجه را به‌صورت ساختاریافته برمی‌گرداند
  6. (اختیاری) نتیجه را در جدول queue_analysis_results ذخیره می‌کند
"""

from __future__ import annotations

from datetime import date
from typing import Any

from core.logging import get_logger
from core.time import now_utc, utc_now_naive
from services.queue_analysis import (
    QueueFeatures,
    QueueHistoryEntry,
    QueueStatus,
    QueueTypeChange,
    adjust_penalty,
    adjust_score_liquidity,
    adjust_score_orderflow,
    adjust_score_technical,
    apply_hard_rules,
    compute_queue_features,
    detect_queue_status,
    get_price_limits,
)

logger = get_logger(__name__)

# ── Run ID generator ────────────────────────────────────────────
import uuid


def _generate_run_id() -> str:
    """تولید run_id منحصربه‌فرد مبتنی بر timestamp."""
    return f"queue-auto-{now_utc().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


class QueueAnalysisService:
    """
    سرویس تحلیل صف — پل بین داده‌های واقعی و موتور محاسبه.

    Args:
        brsapi_query_service: BrsApiQueryService instance
        db_session: SQLAlchemy AsyncSession (اختیاری — برای ذخیره خودکار نتایج)

    Usage:
        # بدون ذخیره در دیتابیس
        service = QueueAnalysisService(brsapi)
        result = await service.analyze_symbol("فولاد")

        # با ذخیره خودکار در دیتابیس
        service = QueueAnalysisService(brsapi, db_session=session)
        result = await service.analyze_symbol("فولاد")
    """

    def __init__(
        self,
        brsapi_query_service: Any,
        db_session: Any | None = None,
    ) -> None:
        self._brsapi = brsapi_query_service
        self._db_session = db_session
        self._run_id: str = ""

    @property
    def run_id(self) -> str:
        """شناسه اجرای جاری — هر بار analyse_symbol یک run_id جدید تولید می‌کند."""
        if not self._run_id:
            self._run_id = _generate_run_id()
        return self._run_id

    # ── Public API ───────────────────────────────────────────────

    async def analyze_symbol(
        self,
        symbol: str,
        base_liquidity_score: float | None = None,
        base_technical_score: float | None = None,
        base_orderflow_score: float | None = None,
        base_penalty: float | None = None,
        base_decision: str = "NEUTRAL",
        base_score: float = 50.0,
    ) -> dict[str, Any]:
        """
        تحلیل کامل صف برای یک نماد.

        Args:
            symbol: نماد بورسی (مثلاً "فولاد")
            base_liquidity_score: امتیاز نقدشوندگی پایه (برای S_L adjustment)
            base_technical_score: امتیاز تکنیکال پایه (برای S_T adjustment)
            base_orderflow_score: امتیاز جریان پول پایه (برای S_O adjustment)
            base_penalty: جریمه پایه (برای penalty adjustment)
            base_decision: تصمیم پایه (برای hard rules)
            base_score: امتیاز پایه (برای hard rules)

        Returns:
            dict با 5 ویژگی صف + تعدیل امتیازها + hard rules
        """
        try:
            # 1. دریافت داده‌های غنی‌شده نماد (tmin, tmax, قیمت، سفارشات)
            enriched = await self._brsapi.get_enriched_symbol_detail(symbol)
            if not enriched:
                return {"symbol": symbol, "error": f"نماد {symbol} یافت نشد", "queue_status": "NONE"}

            # 2. استخراج داده‌های مورد نیاز
            last_price = float(enriched.get("price_last") or 0)
            last_close = float(enriched.get("price_yesterday") or 0)

            # tmin/tmax از SymbolDetail (اگر نباشه از snapshot یا محاسبه دستی)
            tmin = float(enriched.get("price_lowest_allowed") or 0)
            tmax = float(enriched.get("price_highest_allowed") or 0)

            # تعیین نوع بازار
            market_type = self._determine_market_type(enriched)

            # اگر tmin/tmax موجود نباشه، از get_price_limits محاسبه کن
            if tmin == 0 or tmax == 0:
                limit_up, limit_down = get_price_limits(last_close, market_type)
            else:
                limit_up = tmax
                limit_down = tmin

            # 3. حجم سفارشات از order book (سطح 1 snapshot)
            bid_volume_1 = int(enriched.get("bid_volume_1") or 0)
            ask_volume_1 = int(enriched.get("ask_volume_1") or 0)

            # حجم کل خرید/فروش (مختص snapshot)
            total_buy_volume = int(enriched.get("buy_real_volume") or 0) + int(enriched.get("buy_legal_volume") or 0)
            total_sell_volume = int(enriched.get("sell_real_volume") or 0) + int(enriched.get("sell_legal_volume") or 0)

            # 4. تشخیص وضعیت صف از روی قیمت
            queue_status = detect_queue_status(last_price, limit_up, limit_down)

            # 5. محاسبه تاریخچه صف از داده‌های تاریخی
            history = await self._build_queue_history(symbol, queue_status, limit_up, limit_down)

            # 6. محاسبه 5 ویژگی صف
            queue_features = compute_queue_features(
                last_price=last_price,
                last_close=last_close,
                queue_buy_volume=float(bid_volume_1),
                queue_sell_volume=float(ask_volume_1),
                total_buy_volume=float(total_buy_volume),
                total_sell_volume=float(total_sell_volume),
                history=history,
                market_type=market_type,
            )

            # 7. محاسبه تعدیل امتیازها
            adjustments = self._compute_adjustments(
                queue_features=queue_features,
                base_liquidity_score=base_liquidity_score,
                base_technical_score=base_technical_score,
                base_orderflow_score=base_orderflow_score,
                base_penalty=base_penalty,
            )

            # 8. اعمال Hard Rules
            final_decision, override_reason = apply_hard_rules(
                queue=queue_features,
                base_decision=base_decision,
                base_score=base_score,
            )

            # 9. ساخت خروجی
            result = self._build_result(
                symbol=symbol,
                enriched=enriched,
                queue_features=queue_features,
                adjustments=adjustments,
                final_decision=final_decision,
                override_reason=override_reason,
                market_type=market_type,
            )

            # 10. ذخیره در دیتابیس (در صورت وجود session)
            await self._save_result(result, queue_features, adjustments)

            return result

        except Exception as exc:
            logger.exception("Queue analysis failed for %s", symbol)
            return {
                "symbol": symbol,
                "error": str(exc),
                "queue_status": "NONE",
            }

    async def analyze_market(
        self,
        limit: int = 500,
    ) -> dict[str, Any]:
        """
        تحلیل صف کل بازار — آمار تعداد صف‌ها، سنگین‌ترین صف‌ها و ...

        Args:
            limit: تعداد نمادهای بررسی‌شده

        Returns:
            dict با آمار کلی بازار
        """
        snapshots = await self._brsapi.get_latest_snapshots(limit=limit)
        if not snapshots:
            return {"total_symbols": 0, "error": "داده‌ای موجود نیست"}

        queue_results = []
        buy_queue_count = 0
        sell_queue_count = 0
        no_queue_count = 0
        heavy_buy_queues = []
        heavy_sell_queues = []
        new_buy_queues = []
        new_sell_queues = []
        new_broken_queues = []

        for snap in snapshots[:limit]:
            symbol = snap.get("symbol", "")
            if not symbol:
                continue

            try:
                result = await self.analyze_symbol(symbol)
                qs = result.get("queue_status", "NONE")

                if qs == "BUY_QUEUE":
                    buy_queue_count += 1
                    ratio = result.get("queue_volume_ratio", 0)
                    if ratio > 0.7:
                        heavy_buy_queues.append({
                            "symbol": symbol,
                            "ratio": ratio,
                            "streak": result.get("queue_days_streak", 0),
                        })
                    if result.get("queue_type_change") == "NEW_BUY_QUEUE":
                        new_buy_queues.append(symbol)

                elif qs == "SELL_QUEUE":
                    sell_queue_count += 1
                    ratio = result.get("queue_volume_ratio", 0)
                    if ratio > 0.7:
                        heavy_sell_queues.append({
                            "symbol": symbol,
                            "ratio": ratio,
                            "streak": result.get("queue_days_streak", 0),
                        })
                    if result.get("queue_type_change") == "NEW_SELL_QUEUE":
                        new_sell_queues.append(symbol)

                else:
                    no_queue_count += 1

                if result.get("queue_type_change") == "QUEUE_BROKEN":
                    new_broken_queues.append(symbol)

                queue_results.append({
                    "symbol": symbol,
                    "name": snap.get("name", ""),
                    "queue_status": qs,
                    "queue_volume_ratio": result.get("queue_volume_ratio", 0),
                    "queue_days_streak": result.get("queue_days_streak", 0),
                    "queue_type_change": result.get("queue_type_change", "NO_CHANGE"),
                    "distance_to_limit": result.get("distance_to_limit", 0),
                    "last_price": result.get("last_price", 0),
                    "price_change_pct": snap.get("price_last_change_pct", 0),
                })

            except Exception:
                continue

        return {
            "total_symbols": len(queue_results),
            "analyzed_at": utc_now_naive().isoformat(),
            "summary": {
                "buy_queues": buy_queue_count,
                "sell_queues": sell_queue_count,
                "no_queues": no_queue_count,
                "buy_queue_pct": round(buy_queue_count / max(len(queue_results), 1) * 100, 1),
                "sell_queue_pct": round(sell_queue_count / max(len(queue_results), 1) * 100, 1),
            },
            "signals": {
                "new_buy_queues": new_buy_queues[:20],
                "new_sell_queues": new_sell_queues[:20],
                "broken_queues": new_broken_queues[:20],
                "heavy_buy_queues": sorted(heavy_buy_queues, key=lambda x: x["ratio"], reverse=True)[:10],
                "heavy_sell_queues": sorted(heavy_sell_queues, key=lambda x: x["ratio"], reverse=True)[:10],
            },
            "details": queue_results,
        }

    # ── Internal Helpers ─────────────────────────────────────────

    async def _build_queue_history(
        self,
        symbol: str,
        current_status: QueueStatus,
        limit_up: float,
        limit_down: float,
        days: int = 30,
    ) -> list[QueueHistoryEntry]:
        """ساخت تاریخچه صف از داده‌های historical_daily."""
        history: list[QueueHistoryEntry] = []

        try:
            historical = await self._brsapi.get_historical_daily(symbol, limit=days)
            if not historical:
                return history

            # historical از جدیدترین به قدیمی‌ترین مرتب شده
            for row in historical:
                row_date_str = row.get("trade_date") or row.get("date", "")
                try:
                    row_date = date.fromisoformat(row_date_str)
                except (ValueError, TypeError):
                    continue

                close_price = float(row.get("price_close") or row.get("price_last", 0))
                if close_price == 0:
                    continue

                # تشخیص وضعیت صف در آن روز تاریخی — با استفاده از تابع اصلی
                row_queue_status = detect_queue_status(close_price, limit_up, limit_down)

                # حجم خرید/فروش در آن روز (از HistoricalRealLegal در دسترس نیست،
                # پس از trade_volume تخمین می‌زنیم)
                trade_volume = float(row.get("trade_volume", 0))

                history.append(QueueHistoryEntry(
                    date=row_date,
                    queue_status=row_queue_status,
                    queue_buy_volume=trade_volume * 0.5 if row_queue_status == QueueStatus.BUY_QUEUE else 0,
                    queue_sell_volume=trade_volume * 0.5 if row_queue_status == QueueStatus.SELL_QUEUE else 0,
                    total_buy_volume=trade_volume,
                    total_sell_volume=trade_volume,
                ))

        except Exception:
            logger.exception("Failed to build queue history for %s", symbol)

        return history

    def _compute_adjustments(
        self,
        queue_features: QueueFeatures,
        base_liquidity_score: float | None,
        base_technical_score: float | None,
        base_orderflow_score: float | None,
        base_penalty: float | None,
    ) -> dict[str, Any]:
        """محاسبه تمام تعدیل امتیازها."""
        adjustments: dict[str, Any] = {}

        if base_liquidity_score is not None:
            adjustments["adjusted_liquidity"] = adjust_score_liquidity(base_liquidity_score, queue_features)
            adjustments["liquidity_delta"] = round(adjustments["adjusted_liquidity"] - base_liquidity_score, 1)

        if base_technical_score is not None:
            adjustments["adjusted_technical"] = adjust_score_technical(base_technical_score, queue_features)
            adjustments["technical_delta"] = round(adjustments["adjusted_technical"] - base_technical_score, 1)

        if base_orderflow_score is not None:
            adjustments["adjusted_orderflow"] = adjust_score_orderflow(base_orderflow_score, queue_features)
            adjustments["orderflow_delta"] = round(adjustments["adjusted_orderflow"] - base_orderflow_score, 1)

        if base_penalty is not None:
            adjusted_penalty, risk_info = adjust_penalty(base_penalty, queue_features)
            adjustments["adjusted_penalty"] = adjusted_penalty
            adjustments["penalty_delta"] = round(adjusted_penalty - base_penalty, 2)
            adjustments["risk_info"] = risk_info

        return adjustments

    def _determine_market_type(self, enriched: dict[str, Any]) -> str:
        """تشخیص نوع بازار از on ISIN / board."""
        isin = (enriched.get("isin") or "").upper()
        board = (enriched.get("board") or "").lower()
        market = (enriched.get("market") or "").lower()

        if isin.startswith("IROF"):
            return "farabours"
        if isin.startswith("IRO"):
            return "bours"
        if "پایه" in board or "base" in market:
            return "base_market"
        if "فرابورس" in board or "فرابورس" in market:
            return "farabours"
        return "bours"

    async def _save_result(
        self,
        result: dict[str, Any],
        queue_features: QueueFeatures,
        adjustments: dict[str, Any],
    ) -> None:
        """ذخیره خودکار نتیجه تحلیل صف در جدول queue_analysis_results."""
        if not self._db_session:
            return

        # اگر خطا رخ داده باشد، ذخیره نمی‌کنیم
        if "error" in result:
            return

        run_id = self.run_id

        try:
            from models.queue_analysis import QueueAnalysisResult

            db_row = QueueAnalysisResult(
                symbol=result.get("symbol", ""),
                run_id=run_id,
                market_type=result.get("market_type", "bours"),

                # ── 5 Queue Features ──
                queue_status=result.get("queue_status", "NONE"),
                queue_volume_ratio=result.get("queue_volume_ratio", 0.0),
                queue_days_streak=result.get("queue_days_streak", 0),
                queue_type_change=result.get("queue_type_change", "NO_CHANGE"),
                distance_to_limit=result.get("distance_to_limit", 0.0),

                # ── Metadata ──
                last_price=result.get("last_price"),
                limit_up=result.get("limit_up"),
                limit_down=result.get("limit_down"),
                queue_buy_volume=int(result["queue_buy_volume"]) if result.get("queue_buy_volume") is not None else None,
                queue_sell_volume=int(result["queue_sell_volume"]) if result.get("queue_sell_volume") is not None else None,

                # ── Adjusted Scores ──
                adjusted_liquidity=adjustments.get("adjusted_liquidity"),
                adjusted_technical=adjustments.get("adjusted_technical"),
                adjusted_orderflow=adjustments.get("adjusted_orderflow"),
                adjusted_penalty=adjustments.get("adjusted_penalty"),
                liquidity_delta=adjustments.get("liquidity_delta"),
                technical_delta=adjustments.get("technical_delta"),
                orderflow_delta=adjustments.get("orderflow_delta"),
                penalty_delta=adjustments.get("penalty_delta"),

                # ── Decision ──
                final_decision=result.get("final_decision"),
                overridden=result.get("overridden", False),
                override_reason=result.get("override_reason"),

                # ── Interpretation ──
                interpretation=result.get("interpretation"),

                # ── Timing ──
                analyzed_at=utc_now_naive(),
            )

            self._db_session.add(db_row)
            await self._db_session.commit()
            logger.debug("Saved queue result for %s (run_id=%s)", result.get("symbol"), run_id)

        except Exception:
            logger.exception("Failed to save queue result for %s", result.get("symbol"))
            await self._db_session.rollback()

    def _build_result(
        self,
        symbol: str,
        enriched: dict[str, Any],
        queue_features: QueueFeatures,
        adjustments: dict[str, Any],
        final_decision: str,
        override_reason: str,
        market_type: str,
    ) -> dict[str, Any]:
        """ساخت خروجی نهایی ساختاریافته."""
        result: dict[str, Any] = {
            "symbol": symbol,
            "name": enriched.get("name", ""),
            "market_type": market_type,
            "analyzed_at": utc_now_naive().isoformat(),

            # ── 5 ویژگی صف ──
            "queue_status": queue_features.queue_status.value,
            "queue_volume_ratio": queue_features.queue_volume_ratio,
            "queue_days_streak": queue_features.queue_days_streak,
            "queue_type_change": queue_features.queue_type_change.value,
            "distance_to_limit": queue_features.distance_to_limit,

            # ── متادیتا ──
            "last_price": queue_features.last_price,
            "limit_up": queue_features.limit_up,
            "limit_down": queue_features.limit_down,
            "queue_buy_volume": queue_features.queue_buy_volume,
            "queue_sell_volume": queue_features.queue_sell_volume,

            # ── تفسیر ──
            "interpretation": self._interpret_queue(queue_features),

            # ── تعدیل امتیازها ──
            "adjustments": adjustments,

            # ── Hard Rules ──
            "final_decision": final_decision,
            "override_reason": override_reason,
            "overridden": bool(override_reason),
        }
        return result

    @staticmethod
    def _interpret_queue(q: QueueFeatures) -> dict[str, str]:
        """تولید تفسیر انسانی از وضعیت صف."""
        interpretations: dict[str, str] = {}

        if q.queue_status == QueueStatus.BUY_QUEUE:
            interpretations["status_fa"] = "🟢 صف خرید"
            if q.queue_volume_ratio > 0.7:
                interpretations["volume_fa"] = f"فشار خرید بسیار سنگین ({q.queue_volume_ratio:.0%})"
            elif q.queue_volume_ratio > 0.4:
                interpretations["volume_fa"] = f"فشار خرید متوسط ({q.queue_volume_ratio:.0%})"
            else:
                interpretations["volume_fa"] = f"فشار خرید خفیف ({q.queue_volume_ratio:.0%})"

            if q.queue_days_streak >= 3:
                interpretations["streak_fa"] = f"تداوم صف خرید به مدت {q.queue_days_streak} روز — قدرت فوق‌العاده"
            elif q.queue_days_streak >= 1:
                interpretations["streak_fa"] = f"روز {q.queue_days_streak} صف خرید — احتمال تداوم"

            if q.distance_to_limit < 0.5:
                interpretations["limit_fa"] = "فاصله تا سقف کمتر از ۰.۵٪ — احتمال تداوم صف در روز بعد بالا"

        elif q.queue_status == QueueStatus.SELL_QUEUE:
            interpretations["status_fa"] = "🔴 صف فروش"
            if q.queue_volume_ratio > 0.7:
                interpretations["volume_fa"] = f"فشار فروش بسیار سنگین ({q.queue_volume_ratio:.0%})"
            elif q.queue_volume_ratio > 0.4:
                interpretations["volume_fa"] = f"فشار فروش متوسط ({q.queue_volume_ratio:.0%})"
            else:
                interpretations["volume_fa"] = f"فشار فروش خفیف ({q.queue_volume_ratio:.0%})"

            if q.queue_days_streak >= 3:
                interpretations["streak_fa"] = f"تداوم صف فروش به مدت {q.queue_days_streak} روز — ریسک شدید"
            elif q.queue_days_streak >= 1:
                interpretations["streak_fa"] = f"روز {q.queue_days_streak} صف فروش"

            if q.distance_to_limit < 0.5:
                interpretations["limit_fa"] = "فاصله تا کف کمتر از ۰.۵٪ — احتمال تداوم صف در روز بعد بالا"

        else:
            interpretations["status_fa"] = "⚪ بدون صف"

        # تفسیر تغییر وضعیت
        if q.queue_type_change == QueueTypeChange.NEW_BUY_QUEUE:
            interpretations["change_fa"] = "🟢 صف خرید جدید تشکیل شده — سیگنال قوی صعودی"
        elif q.queue_type_change == QueueTypeChange.NEW_SELL_QUEUE:
            interpretations["change_fa"] = "🔴 صف فروش جدید تشکیل شده — سیگنال قوی نزولی"
        elif q.queue_type_change == QueueTypeChange.QUEUE_BROKEN:
            interpretations["change_fa"] = "🟡 صف شکسته شده — احتمال بازگشت به تعادل"

        return interpretations
