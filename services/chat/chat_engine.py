"""ChatEngine — Central orchestrator for the 20-Level Conversational System.

Integrates all components:
  Level  1-5: Base NLP pipeline
  Level  7:   Slot filling (EntityExtractor)
  Level  8:   Context (DialogManager)
  Level  9:   Compound splitter (CompoundSplitter)
  Level 10:   Dynamic filter (in screener_service)
  Level 11:   Explanations (Explainer)
  Level 12:   Charts (ChartGenerator)
  Level 13:   Speech (handled at frontend level)
  Level 14:   Sentiment analysis (SentimentAnalyzer)
  Level 15:   Personalization (Personalizer)
  Level 16:   News integration (NewsIntegration)
  Level 17:   Advanced comparison (ComparisonEngine)
  Level 18:   Active suggestions (SuggestionEngine)
  Level 19:   Learning (LearningEngine)
  Level 20:   Complex mixed queries
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from services.chat.chart_generator import ChartGenerator
from services.chat.comparison_engine import ComparisonEngine
from services.chat.compound_splitter import CompoundSplitter
from services.chat.dialog_manager import DialogManager
from services.chat.entity_extractor import EntityExtractor
from services.chat.intent_classifier import DEFAULT_TRAINING_DATA, IntentClassifier
from services.chat.learning_engine import LearningEngine
from services.chat.news_integration import NewsIntegration
from services.chat.personalizer import Personalizer, ProfileStore
from services.chat.sentiment_analyzer import SentimentAnalyzer
from services.chat.suggestion_engine import SuggestionEngine

logger = get_logger(__name__)


class ChatEngine:
    """Central conversational engine orchestrating all 20 levels.

    Integrates with existing services (StockAssistantService,
    UnifiedAssistantService, ScreenerService) via dependency injection.
    """

    def __init__(
        self,
        stock_assistant: Any = None,
        unified_assistant: Any = None,
        screener_service: Any = None,
        smart_money_service: Any = None,
        market_service: Any = None,
        news_service: Any = None,
        watchlist_service: Any = None,
        alert_service: Any = None,
        portfolio_service: Any = None,
        brsapi_service: Any = None,
        brsapi_key: str | None = None,
    ):
        # ── Level 7: Intent Classification ──
        self._intent_clf = IntentClassifier()
        texts, intents = zip(*DEFAULT_TRAINING_DATA, strict=False) if DEFAULT_TRAINING_DATA else ([], [])
        self._intent_clf.train(list(texts), list(intents))

        # ── Level 7: Entity Extraction ──
        self._entity_extractor = EntityExtractor()

        # ── Level 8: Dialog Context ──
        self._dialog = DialogManager()

        # ── Level 9: Compound Splitter ──
        self._compound_splitter = CompoundSplitter()

        # ── Level 14: Sentiment ──
        self._sentiment = SentimentAnalyzer()

        # ── Level 15: Personalization ──
        self._profile_store = ProfileStore()
        self._personalizer = Personalizer(store=self._profile_store)

        # ── Level 16: News ──
        self._news = NewsIntegration(brsapi_key=brsapi_key)

        # ── Level 17: Comparison ──
        self._comparison = ComparisonEngine(news_integration=self._news)

        # ── Level 12: Charts ──
        self._chart_gen = ChartGenerator()

        # ── Level 18: Suggestions ──
        self._suggestions = SuggestionEngine(
            personalizer=self._personalizer,
            dialog_manager=self._dialog,
        )

        # ── Level 19: Learning ──
        self._learning = LearningEngine()

        # ── External services ──
        self._stock_assistant = stock_assistant
        self._unified_assistant = unified_assistant
        self._screener_service = screener_service
        self._smart_money_service = smart_money_service
        self._market_service = market_service
        self._news_service = news_service
        self._watchlist_service = watchlist_service
        self._alert_service = alert_service
        self._portfolio_service = portfolio_service
        self._brsapi_service = brsapi_service

    async def process(
        self,
        user_id: str,
        message: str,
    ) -> dict[str, Any]:
        """Process a user message through all 20 levels.

        Returns structured response with:
        - text: response text
        - type: response type
        - suggestions: follow-up suggestions
        - data: optional structured data
        - actions: actionable items
        - sentiment: detected sentiment
        """
        message = message.strip()
        if not message:
            return self._greeting_response(user_id)

        # ═══ Level 14: Sentiment Analysis ═══
        sentiment_result = self._sentiment.analyze(message)

        # ═══ Level 7: Intent Classification ═══
        intent, confidence = self._intent_clf.predict(message)

        # ═══ Level 7: Entity Extraction ═══
        entities = self._entity_extractor.extract(message)
        entities["raw_text"] = message
        entities["sentiment"] = sentiment_result

        # ═══ Level 8: Context Resolution ═══
        # Resolve symbols from context if not in current message
        symbols = entities.get("symbols", [])
        if not symbols:
            context_symbols = self._dialog.resolve_symbol(
                user_id, message, symbols
            )
            if context_symbols:
                entities["symbols"] = context_symbols
                entities["resolved_from_context"] = True

        # ═══ Level 15: Personalization Update ═══
        self._personalizer.update_from_intent(user_id, intent, entities, message)

        # ═══ Level 19: Learning ═══
        self._learning.record_successful_intent(message, intent)

        # ═══ Level 9: Compound Splitter ═══
        if self._compound_splitter.is_compound(message):
            parts = self._compound_splitter.split(message)
            if len(parts) > 1:
                response = await self._handle_compound(
                    user_id, parts, intent, entities
                )
                self._dialog.add_turn(
                    user_id, message, intent, entities, response, confidence
                )
                return response

        # ═══ Route to single intent handler ═══
        response = await self._route_intent(user_id, intent, entities, message)

        # ═══ Level 18: Suggestions ═══
        if "suggestions" not in response or not response["suggestions"]:
            response["suggestions"] = self._suggestions.get_suggestions(
                user_id, intent, entities, max_suggestions=4
            )

        # ═══ Level 8: Store in dialog history ═══
        self._dialog.add_turn(
            user_id, message, intent, entities, response, confidence
        )

        # Add sentiment to response
        response["sentiment"] = sentiment_result

        return response

    async def _handle_compound(
        self,
        user_id: str,
        parts: list[str],
        primary_intent: str,
        entities: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle compound/mixed queries (Level 20)."""
        responses = []

        for part in parts[:3]:  # Max 3 sub-queries
            part_intent, part_conf = self._intent_clf.predict(part)
            part_entities = self._entity_extractor.extract(part)

            part_response = await self._route_intent(
                user_id, part_intent, part_entities, part
            )
            if part_response.get("text"):
                responses.append(part_response["text"])

        if not responses:
            return self._unknown_response()

        combined = "\n\n".join(responses)

        return {
            "text": combined,
            "type": "compound",
            "suggestions": self._suggestions.get_suggestions(
                user_id, primary_intent, entities, max_suggestions=3
            ),
        }

    async def _route_intent(
        self,
        user_id: str,
        intent: str,
        entities: dict[str, Any],
        text: str,
    ) -> dict[str, Any]:
        """Route intent to appropriate handler."""
        # ── Greeting & Farewell ──
        if intent == "greeting":
            return self._greeting_response(user_id)
        if intent == "farewell":
            return self._farewell_response()

        # ── Help ──
        if intent == "help":
            return self._help_response()

        # ── Market ──
        if intent == "market_overview":
            return await self._handle_market_overview()
        if intent == "top_gainers":
            return await self._handle_top_gainers()
        if intent == "top_losers":
            return await self._handle_top_losers()

        # ── Analysis ──
        if intent == "analyze_symbol":
            return await self._handle_analyze(entities)
        if intent == "analyze_all":
            return await self._handle_analyze_all()

        # ── Best / Cheap Stocks ──
        if intent == "find_best":
            return await self._handle_find_best(user_id)
        if intent == "find_cheap":
            return await self._handle_find_cheap()

        # ── Screener & Filter ──
        if intent == "screener":
            return await self._handle_screener(entities)
        if intent == "dynamic_filter":
            return await self._handle_dynamic_filter(entities)

        # ── Compare ──
        if intent == "compare_symbols":
            return await self._handle_compare(entities)

        # ── News ──
        if intent == "get_news":
            return await self._handle_news(entities)
        if intent == "get_codal":
            return self._handle_codal(entities)

        # ── Watchlist ──
        if intent == "add_watchlist":
            return await self._handle_watchlist_add(entities)
        if intent == "remove_watchlist":
            return await self._handle_watchlist_remove(entities)
        if intent == "list_watchlist":
            return await self._handle_watchlist_list()

        # ── Alerts ──
        if intent == "add_alert":
            return await self._handle_alert_add(entities)
        if intent == "list_alerts":
            return await self._handle_alerts_list()
        if intent == "remove_alert":
            return self._handle_alert_remove()

        # ── Portfolio ──
        if intent == "portfolio_add":
            return await self._handle_portfolio_add(entities)
        if intent == "portfolio_remove":
            return await self._handle_portfolio_remove(entities)
        if intent == "portfolio_summary":
            return await self._handle_portfolio_summary()

        # ── Macro / Gold / Crypto ──
        if intent == "gold_currency":
            return self._handle_gold_currency()
        if intent == "macro_data":
            return self._handle_macro()
        if intent == "crypto_prices":
            return self._handle_crypto()

        # ── ML ──
        if intent == "ml_predict":
            return await self._handle_ml_predict(entities)
        if intent == "ml_train":
            return self._handle_ml_train()
        if intent == "ml_list_models":
            return self._handle_ml_list()

        # ── Backtest ──
        if intent == "run_backtest":
            return await self._handle_backtest(entities)
        if intent == "list_backtests":
            return self._handle_backtest_list()

        # ── Charts ──
        if intent == "get_chart":
            return await self._handle_chart(entities)

        # ── Other ──
        if intent == "heatmap":
            return self._handle_heatmap()
        if intent == "risk_overview":
            return self._handle_risk()
        if intent == "signals":
            return self._handle_signals()
        if intent == "anomalies":
            return self._handle_anomalies()
        if intent == "navigate":
            return self._handle_navigate(entities)
        if intent == "recommendation":
            return await self._handle_recommendation(user_id)

        # ── Unknown / Fallback ──
        return self._unknown_response()

    # ════════════════════════════════════════════
    # Intent Handlers
    # ════════════════════════════════════════════

    def _greeting_response(self, user_id: str) -> dict[str, Any]:
        """Level 15: Personalized greeting."""
        profile_snippet = ""
        if self._personalizer:
            suggestion_text = self._personalizer.get_suggestion_text(user_id)
            if suggestion_text:
                profile_snippet = f"\n\n🔹 {suggestion_text}"

        return {
            "text": (
                "سلام! 👋 من دستیار هوشمند بازار سرمایه هستم.\n\n"
                "📊 می‌توانم:\n"
                "• تحلیل نمادهای بورسی\n"
                "• مقایسه چند سهم\n"
                "• غربال‌گری پیشرفته با SMC\n"
                "• مدیریت پرتفوی و دیده‌بان\n"
                "• اخبار و تحلیل احساسات\n"
                "• پیش‌بینی قیمت با AI\n"
                "• داده‌های طلا، ارز و رمزارز"
                f"{profile_snippet}"
            ),
            "type": "greeting",
            "suggestions": self._suggestions.get_intro_suggestions(user_id),
        }

    def _farewell_response(self) -> dict[str, Any]:
        return {
            "text": "خداحافظ! موفق باشید و پیروز 🙏",
            "type": "farewell",
        }

    def _help_response(self) -> dict[str, Any]:
        return {
            "text": (
                "🤖 **راهنمای دستیار هوشمند**\n\n"
                "**تحلیل:** «تحلیل فولاد»، «فولاد چطوره؟»\n"
                "**مقایسه:** «مقایسه فولاد و خودرو»\n"
                "**بهترین:** «بهترین سهم‌ها»، «سهام ارزنده»\n"
                "**غربال:** «غربال‌گری»، «SMC بالا»\n"
                "**فیلتر:** «فیلتر RSI<30 ROE>20»\n"
                "**بازار:** «خلاصه بازار»، «پرمتقاضی‌ترین‌ها»\n"
                "**اخبار:** «اخبار فولاد»، «آخرین اخبار بازار»\n"
                "**دیده‌بان:** «اضافه فولاد به دیده‌بان»\n"
                "**هشدار:** «هشدار فولاد rsi above 70»\n"
                "**پرتفوی:** «خرید فولاد 100 50000»، «پرتفوی من»\n"
                "**طلا و ارز:** «قیمت طلا»، «قیمت دلار»\n"
                "**پیش‌بینی:** «پیش‌بینی فولاد»\n"
                "**نمودار:** «نمودار فولاد»\n"
                "**بک‌تست:** «بک‌تست فولاد»\n"
                "**سیگنال:** «سیگنال خرید»\n"
                "**نقشه:** «نقشه بازار»\n"
                "**ناهنجاری:** «ناهنجاری قیمت»\n"
                "**ناوبری:** «برو به غربالگر»\n"
                "**گزارش:** «گزارش بازار»\n"
            ),
            "type": "help",
            "suggestions": [
                "تحلیل فولاد", "بهترین سهم‌ها", "خلاصه بازار",
                "قیمت طلا", "help",
            ],
        }

    async def _handle_market_overview(self) -> dict[str, Any]:
        """Level 1-5: Market summary."""
        try:
            if self._market_service:
                overview = await self._market_service.get_overview()
                if hasattr(overview, 'success') and overview.success and overview.value:
                    d = overview.value
                    return {
                        "text": (
                            f"📊 **خلاصه بازار**\n\n"
                            f"تعداد نمادها: {d.get('total_instruments', 0):,}\n"
                            f"🟢 مثبت: {d.get('gainers', 0):,}\n"
                            f"🔴 منفی: {d.get('losers', 0):,}\n"
                            f"📈 میانگین تغییر: {d.get('avg_change_pct', 0):+.2f}%\n"
                            f"💰 ارزش کل: {d.get('total_value', 0):,.0f} ریال\n"
                        ),
                        "type": "market",
                        "actions": [{"type": "link", "label": "📊 بازار", "url": "/markets"}],
                    }
        except Exception as e:
            logger.warning("Market overview error: %s", e)

        return {"text": "داده‌ای برای نمایش موجود نیست.", "type": "error"}

    async def _handle_top_gainers(self) -> dict[str, Any]:
        return {"text": "در حال توسعه...", "type": "info"}

    async def _handle_top_losers(self) -> dict[str, Any]:
        return {"text": "در حال توسعه...", "type": "info"}

    async def _handle_analyze(self, entities: dict[str, Any]) -> dict[str, Any]:
        """Level 11: Comprehensive symbol analysis with explanation."""
        symbols = entities.get("symbols", [])
        if not symbols:
            return {"text": "لطفاً نام نماد را بگویید.", "type": "error"}

        symbol = symbols[0]

        # ── Priority 1: Full AI report from the 110-column model ──
        # The report service opens its own DB session, so no DI needed here.
        try:
            from services.screener_ai_report_service import ScreenerAIReportService

            report = await ScreenerAIReportService().generate_symbol_report(symbol)
            report_text = report.get("text", "")
            if report_text and (report.get("model") or report.get("signal") or report.get("profile")):
                return {
                    "text": report_text,
                    "type": "analysis",
                    "data": {
                        "symbol": symbol,
                        "model": report.get("model"),
                        "signal": report.get("signal"),
                        "profile": report.get("profile"),
                    },
                    "actions": [
                        {"type": "link", "label": f"📈 {symbol}", "url": f"/symbol/{symbol}"},
                        {"type": "link", "label": "📊 تحلیل", "url": "/analysis"},
                    ],
                    "suggestions": [
                        f"مقایسه {symbol} و فولاد",
                        f"اخبار {symbol}",
                        f"پیش‌بینی {symbol}",
                    ],
                }
        except Exception as e:
            logger.warning("AI report unavailable for %s, falling back: %s", symbol, e)

        # Use stock assistant if available
        if self._stock_assistant:
            try:
                result = await self._stock_assistant.process_message(
                    f"تحلیل {symbol}"
                )
                if result and result.get("type") != "error":
                    return {
                        "text": result.get("text", ""),
                        "type": "analysis",
                        "data": result.get("data"),
                        "actions": [
                            {"type": "link", "label": f"📈 {symbol}", "url": f"/symbol/{symbol}"},
                            {"type": "link", "label": "📊 تحلیل", "url": "/analysis"},
                        ],
                        "suggestions": [
                            f"مقایسه {symbol} و فولاد",
                            f"اخبار {symbol}",
                            f"پیش‌بینی {symbol}",
                        ],
                    }
            except Exception as e:
                logger.warning("Analysis error: %s", e)

        return {
            "text": f"📊 **تحلیل {symbol}**\n\nبرای تحلیل کامل به صفحه نماد مراجعه کنید.",
            "type": "analysis",
            "actions": [{"type": "link", "label": f"📈 {symbol}", "url": f"/symbol/{symbol}"}],
        }

    async def _handle_analyze_all(self) -> dict[str, Any]:
        if self._stock_assistant:
            try:
                result = await self._stock_assistant.process_message("تحلیل همه")
                if result and result.get("type") != "error":
                    return {
                        "text": result.get("text", ""),
                        "type": "analysis",
                        "data": result.get("data"),
                    }
            except Exception:
                pass
        return {"text": "امکان تحلیل همه نمادها در حال حاضر وجود ندارد.", "type": "error"}

    async def _handle_find_best(self, user_id: str) -> dict[str, Any]:
        """Level 15: Personalized best stocks."""
        if self._stock_assistant:
            try:
                result = await self._stock_assistant.process_message("بهترین سهام")
                if result and result.get("type") != "error":
                    text = result.get("text", "")

                    # Personalize
                    if self._personalizer:
                        favs = self._personalizer.store.get_favorite_symbols(user_id)
                        if favs:
                            fav_text = "⭐ ".join(favs[:3])
                            text += f"\n\n🔹 نمادهای محبوب شما: {fav_text}"

                    return {
                        "text": text,
                        "type": "screener",
                        "data": result.get("data"),
                        "actions": [{"type": "link", "label": "🔍 غربال‌گر", "url": "/screener"}],
                    }
            except Exception as e:
                logger.warning("Best stocks error: %s", e)

        return {"text": "در حال دریافت بهترین سهم‌ها...", "type": "info"}

    async def _handle_find_cheap(self) -> dict[str, Any]:
        if self._stock_assistant:
            try:
                result = await self._stock_assistant.process_message("سهام ارزنده")
                if result and result.get("type") != "error":
                    return {
                        "text": result.get("text", ""),
                        "type": "screener",
                        "data": result.get("data"),
                    }
            except Exception:
                pass
        return {"text": "در حال جستجوی سهام ارزنده...", "type": "info"}

    async def _handle_screener(self, entities: dict[str, Any]) -> dict[str, Any]:
        return {
            "text": "🔍 **غربال‌گر هوشمند**\n\nبرای غربال‌گری پیشرفته به صفحه مربوطه بروید.",
            "type": "screener",
            "actions": [{"type": "link", "label": "🔍 غربال‌گر", "url": "/screener"}],
        }

    async def _handle_dynamic_filter(self, entities: dict[str, Any]) -> dict[str, Any]:
        """Level 10: Dynamic filter execution."""
        conditions = entities.get("conditions", [])
        if not conditions:
            return {
                "text": "لطفاً شرط فیلتر را مشخص کنید.\nمثال: فیلتر RSI<30 ROE>20",
                "type": "error",
                "suggestions": [
                    "فیلتر RSI<30",
                    "فیلتر P/E<8 ROE>20",
                    "فیلتر SMC>0.6",
                ],
            }

        if self._stock_assistant:
            filter_text = " ".join(
                f"{c['field'].upper()}{c['operator']}{c['value']}"
                for c in conditions
            )
            try:
                result = await self._stock_assistant.process_message(
                    f"فیلتر {filter_text}"
                )
                if result and result.get("type") != "error":
                    return {
                        "text": result.get("text", ""),
                        "type": "filter",
                        "data": result.get("data"),
                    }
            except Exception:
                pass

        return {"text": "در حال اعمال فیلتر...", "type": "info"}

    async def _handle_compare(self, entities: dict[str, Any]) -> dict[str, Any]:
        """Level 17: Advanced comparison."""
        symbols = entities.get("symbols", [])
        comparison_targets = entities.get("comparison_targets", [])

        all_symbols = list(set(symbols + comparison_targets))
        if len(all_symbols) < 2:
            return {
                "text": "لطفاً دو نماد را برای مقایسه مشخص کنید.\nمثال: مقایسه فولاد و خودرو",
                "type": "error",
            }

        # Get data for each symbol from stock assistant
        data_dict = {}
        if self._stock_assistant:
            for sym in all_symbols[:5]:
                try:
                    result = await self._stock_assistant.process_message(
                        f"تحلیل {sym}"
                    )
                    if result:
                        data_dict[sym] = result.get("data", {})
                except Exception:
                    data_dict[sym] = {"symbol": sym, "smc_score": 0}

        # Run comparison engine (async)
        comparison = await self._comparison.compare(all_symbols, data_dict)

        if "error" in comparison:
            return {"text": comparison["error"], "type": "error"}

        # Build response
        lines = []
        table = comparison.get("table", {})
        rows = table.get("rows", [])

        if rows:
            lines.append(f"⚖️ **مقایسه {' و '.join(all_symbols)}**")
            lines.append("═" * 50)

            for row in rows:
                lines.append(
                    f"• {row['symbol']}: SMC={row['smc_score']:.3f} | "
                    f"{row['phase']} | "
                    f"قیمت: {row['price']:,.0f} | "
                    f"تغییر: {row['change_pct']:+.2f}%"
                )

        # Ranking
        ranking = comparison.get("ranking", [])
        if ranking:
            lines.append("")
            lines.append("🏆 **رتبه‌بندی:**")
            for r in ranking:
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r["rank"], "")
                lines.append(f"  {medal} {r['symbol']}: SMC {r['smc_score']:.3f}")

        # Strengths/weaknesses
        sw = comparison.get("strengths_weaknesses", {})
        for sym, analysis in sw.items():
            strengths = analysis.get("strengths", [])
            weaknesses = analysis.get("weaknesses", [])
            if strengths or weaknesses:
                lines.append("")
                lines.append(f"**{sym}:**")
                if strengths:
                    lines.append(f"  ✅ نقاط قوت: {', '.join(strengths)}")
                if weaknesses:
                    lines.append(f"  ⚠️ نقاط ضعف: {', '.join(weaknesses)}")

        return {
            "text": "\n".join(lines),
            "type": "comparison",
            "data": comparison,
            "actions": [
                {"type": "link", "label": "📊 تحلیل", "url": "/analysis"},
            ],
        }

    async def _handle_news(self, entities: dict[str, Any]) -> dict[str, Any]:
        """Level 16: News integration."""
        symbols = entities.get("symbols", [])

        if symbols:
            symbol = symbols[0]
            analysis = await self._news.get_news_for_symbol(symbol)
            text = await self._news.format_news_response(symbol, analysis)
        else:
            text = await self._news.format_market_news_response()

        return {
            "text": text,
            "type": "news",
            "actions": [{"type": "link", "label": "📰 اخبار", "url": "/news"}],
        }

    def _handle_codal(self, entities: dict[str, Any]) -> dict[str, Any]:
        symbols = entities.get("symbols", [])
        symbol_text = f" {symbols[0]}" if symbols else ""
        return {
            "text": f"🏢 **اطلاعیه‌های کدال{symbol_text}**\n\nبرای مشاهده به صفحه کدال بروید.",
            "type": "codal",
            "actions": [{"type": "link", "label": "🏢 کدال", "url": "/codal"}],
        }

    async def _handle_watchlist_add(self, entities: dict[str, Any]) -> dict[str, Any]:
        symbols = entities.get("symbols", [])
        if not symbols:
            return {"text": "لطفاً نماد را مشخص کنید.", "type": "error"}

        symbol = symbols[0]
        if self._watchlist_service:
            try:
                result = await self._watchlist_service.add_symbol(symbol)
                if hasattr(result, 'success') and result.success:
                    return {
                        "text": f"✅ **{symbol}** به دیده‌بان اضافه شد.",
                        "type": "action",
                        "actions": [{"type": "link", "label": "👁️ دیده‌بان", "url": "/watchlist"}],
                    }
            except Exception:
                pass

        return {"text": f"⚠️ خطا در افزودن {symbol} به دیده‌بان.", "type": "error"}

    async def _handle_watchlist_remove(self, entities: dict[str, Any]) -> dict[str, Any]:
        symbols = entities.get("symbols", [])
        if not symbols:
            return {"text": "لطفاً نماد را مشخص کنید.", "type": "error"}

        symbol = symbols[0]
        if self._watchlist_service:
            try:
                result = await self._watchlist_service.remove_symbol(symbol)
                if hasattr(result, 'success') and result.success:
                    return {
                        "text": f"✅ **{symbol}** از دیده‌بان حذف شد.",
                        "type": "action",
                    }
            except Exception:
                pass

        return {"text": f"⚠️ خطا در حذف {symbol}.", "type": "error"}

    async def _handle_watchlist_list(self) -> dict[str, Any]:
        if self._watchlist_service:
            try:
                result = await self._watchlist_service.list_items()
                if hasattr(result, 'success') and result.success and result.value:
                    items = result.value
                    lines = ["👁️ **دیده‌بان شما:**", "═" * 40]
                    for item in items[:20]:
                        sym = item.get("symbol", "")
                        price = item.get("price", "")
                        price_str = f" — {price:,}" if price else ""
                        lines.append(f"  • {sym}{price_str}")
                    return {
                        "text": "\n".join(lines),
                        "type": "watchlist",
                        "actions": [{"type": "link", "label": "👁️ دیده‌بان", "url": "/watchlist"}],
                    }
            except Exception:
                pass

        return {
            "text": "دیده‌بان شما خالی است.\nبا «اضافه فولاد به دیده‌بان» شروع کنید.",
            "type": "info",
        }

    async def _handle_alert_add(self, entities: dict[str, Any]) -> dict[str, Any]:
        alert = entities.get("alert_condition") or {}
        symbol = alert.get("symbol") or ""
        field = str(alert.get("field") or "price").lower()
        condition = str(alert.get("operator") or "above").lower()
        threshold = alert.get("threshold")

        if not symbol or threshold is None:
            return {"text": "فرمت صحیح: «هشدار فولاد rsi above 70»", "type": "error"}

        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            return {"text": "مقدار آستانه معتبر نیست.", "type": "error"}

        operator = "gte" if condition == "above" else "lte"
        # Alert type must match schema values (price_above, rsi_oversold, ...).
        if field == "rsi":
            alert_type = "rsi_oversold" if operator == "lte" else "rsi_overbought"
        elif field == "volume":
            alert_type = "volume_above" if operator == "gte" else "volume_below"
        else:
            alert_type = "price_above" if operator == "gte" else "price_below"

        condition_dict: dict[str, Any] = {
            "field": field,
            "operator": operator,
            "threshold": threshold,
            "cooldown_minutes": 30,
        }

        if self._alert_service:
            try:
                result = await self._alert_service.create_alert(
                    user_id="assistant",
                    # instrument_id is a UUID resolved server-side — never the ticker.
                    instrument_id="",
                    symbol=symbol,
                    alert_type=alert_type,
                    condition=condition_dict,
                    channels=["telegram", "console"],
                    description=f"هشدار {field} {condition} {threshold} برای {symbol}",
                )
                if result.success:
                    return {
                        "text": (
                            f"✅ هشدار ثبت شد:\n"
                            f"**{symbol}** — {'قیمت' if field == 'price' else field.upper()} "
                            f"{'بالای' if operator == 'gte' else 'پایین‌تر از'} "
                            f"{threshold:,.0f}"
                        ),
                        "type": "alert",
                        "actions": [{"type": "link", "label": "🔔 هشدارها", "url": "/alerts"}],
                    }
            except Exception as e:
                logger.warning("Alert add error: %s", e)
                return {"text": "⚠️ خطا در ثبت هشدار. لطفاً دوباره تلاش کنید.", "type": "error"}

        # No alert service wired — fall back to a link-only hint.
        return {
            "text": f"برای ثبت هشدار {symbol} به صفحه هشدارها بروید.",
            "type": "alert",
            "actions": [{"type": "link", "label": "🔔 هشدارها", "url": "/alerts"}],
        }

    async def _handle_alerts_list(self) -> dict[str, Any]:
        return {
            "text": "🔔 **هشدارهای فعال**\n\nبرای مدیریت به صفحه هشدارها بروید.",
            "type": "alerts",
            "actions": [{"type": "link", "label": "🔔 هشدارها", "url": "/alerts"}],
        }

    def _handle_alert_remove(self) -> dict[str, Any]:
        return {
            "text": "برای حذف هشدار به صفحه مدیریت هشدارها مراجعه کنید.",
            "type": "info",
            "actions": [{"type": "link", "label": "🔔 هشدارها", "url": "/alerts"}],
        }

    async def _handle_portfolio_add(self, entities: dict[str, Any]) -> dict[str, Any]:
        if self._stock_assistant:
            text = entities.get("raw_text", "")
            result = await self._stock_assistant.process_message(text)
            return {
                "text": result.get("text", "✅ سهم به پرتفوی اضافه شد."),
                "type": "portfolio",
            }
        return {"text": "برای افزودن به پرتفوی: «خرید فولاد 100 50000»", "type": "error"}

    async def _handle_portfolio_remove(self, entities: dict[str, Any]) -> dict[str, Any]:
        if self._stock_assistant:
            text = entities.get("raw_text", "")
            result = await self._stock_assistant.process_message(text)
            return {"text": result.get("text", "✅ سهم از پرتفوی حذف شد."), "type": "portfolio"}
        return {"text": "برای حذف از پرتفوی: «فروش فولاد»", "type": "error"}

    async def _handle_portfolio_summary(self) -> dict[str, Any]:
        if self._stock_assistant:
            result = await self._stock_assistant.process_message("خلاصه پرتفوی")
            return {
                "text": result.get("text", "پرتفوی شما خالی است."),
                "type": "portfolio",
                "data": result.get("data"),
            }
        return {"text": "پرتفوی شما خالی است.", "type": "info"}

    def _handle_gold_currency(self) -> dict[str, Any]:
        return {
            "text": "🏅 **طلا و ارز**\n\nبرای مشاهده قیمت‌های لحظه‌ای به صفحه داده‌های کلان بروید.",
            "type": "macro",
            "actions": [{"type": "link", "label": "🏅 داده‌های کلان", "url": "/macro"}],
        }

    def _handle_macro(self) -> dict[str, Any]:
        return {
            "text": "🏛️ **داده‌های کلان اقتصادی**\n\nبرای مشاهده به صفحه ماکرو بروید.",
            "type": "macro",
            "actions": [{"type": "link", "label": "🏛️ ماکرو", "url": "/macro"}],
        }

    def _handle_crypto(self) -> dict[str, Any]:
        return {
            "text": "💰 **ارزهای دیجیتال**\n\nبرای مشاهده قیمت‌ها به صفحه کریپتو بروید.",
            "type": "crypto",
            "actions": [{"type": "link", "label": "💰 کریپتو", "url": "/crypto"}],
        }

    async def _handle_ml_predict(self, entities: dict[str, Any]) -> dict[str, Any]:
        symbols = entities.get("symbols", [])
        symbol = symbols[0] if symbols else ""
        return {
            "text": f"🧠 **پیش‌بینی {symbol}**\n\nبرای مشاهده پیش‌بینی‌ها به صفحه ML بروید.",
            "type": "ml",
            "actions": [
                {
                    "type": "link",
                    "label": f"🧠 {symbol}" if symbol else "🧠 پیش‌بینی",
                    "url": f"/ml?symbol={symbol}" if symbol else "/ml",
                },
            ],
        }

    def _handle_ml_train(self) -> dict[str, Any]:
        return {
            "text": "🧠 **آموزش مدل**\n\nبرای آموزش مدل جدید به صفحه ML بروید.",
            "type": "ml",
            "actions": [{"type": "link", "label": "🧠 ML", "url": "/ml"}],
        }

    def _handle_ml_list(self) -> dict[str, Any]:
        return {
            "text": "🧠 **مدل‌های موجود**\n\nبرای مشاهده به صفحه ML بروید.",
            "type": "ml",
            "actions": [{"type": "link", "label": "🧠 ML", "url": "/ml"}],
        }

    async def _handle_backtest(self, entities: dict[str, Any]) -> dict[str, Any]:
        symbols = entities.get("symbols", [])
        symbol = symbols[0] if symbols else ""
        return {
            "text": f"🧪 **بک‌تست {symbol}**\n\nبرای اجرا به صفحه بک‌تست بروید.",
            "type": "backtest",
            "actions": [
                {
                    "type": "link",
                    "label": f"🧪 {symbol}" if symbol else "🧪 بک‌تست",
                    "url": f"/backtest?symbol={symbol}" if symbol else "/backtest",
                },
            ],
        }

    def _handle_backtest_list(self) -> dict[str, Any]:
        return {
            "text": "🧪 **بک‌تست‌های قبلی**\n\nبرای مشاهده به صفحه بک‌تست بروید.",
            "type": "backtest",
            "actions": [{"type": "link", "label": "🧪 بک‌تست", "url": "/backtest"}],
        }

    async def _handle_chart(self, entities: dict[str, Any]) -> dict[str, Any]:
        symbols = entities.get("symbols", [])
        symbol = symbols[0] if symbols else ""
        return {
            "text": f"📈 **نمودار {symbol}**\n\nبرای مشاهده نمودار به صفحه نماد بروید.",
            "type": "chart",
            "actions": [
                {
                    "type": "link",
                    "label": f"📈 {symbol}" if symbol else "📈 نمودار",
                    "url": f"/symbol/{symbol}" if symbol else "/charts",
                },
            ],
        }

    def _handle_heatmap(self) -> dict[str, Any]:
        return {
            "text": "🗺️ **نقشه حرارتی بازار**\n\nبرای مشاهده به صفحه نقشه بروید.",
            "type": "heatmap",
            "actions": [{"type": "link", "label": "🗺️ نقشه", "url": "/heatmap"}],
        }

    def _handle_risk(self) -> dict[str, Any]:
        return {
            "text": "🛡️ **مدیریت ریسک**\n\nشاخص‌های قابل پایش: VaR, Sharpe, Beta, Max Drawdown",
            "type": "risk",
            "actions": [{"type": "link", "label": "🛡️ ریسک", "url": "/risk"}],
        }

    def _handle_signals(self) -> dict[str, Any]:
        return {
            "text": "📡 **سیگنال‌های معاملاتی**\n\nبرای مشاهده به صفحه سیگنال‌ها بروید.",
            "type": "signals",
            "actions": [{"type": "link", "label": "📡 سیگنال‌ها", "url": "/signals"}],
        }

    def _handle_anomalies(self) -> dict[str, Any]:
        return {
            "text": "🚨 **ناهنجاری‌های بازار**\n\nبرای مشاهده به صفحه ناهنجاری‌ها بروید.",
            "type": "anomalies",
            "actions": [{"type": "link", "label": "🚨 ناهنجاری‌ها", "url": "/anomalies"}],
        }

    def _handle_navigate(self, entities: dict[str, Any]) -> dict[str, Any]:
        """Handle navigation intent."""
        text = entities.get("raw_text", "")
        page_map = {
            "بازار": ("📊 بازار", "/markets"),
            "غربال": ("🔍 غربال‌گر", "/screener"),
            "غربالگر": ("🔍 غربال‌گر", "/screener"),
            "تحلیل": ("📈 تحلیل", "/analysis"),
            "دیده‌بان": ("👁️ دیده‌بان", "/watchlist"),
            "اخبار": ("📰 اخبار", "/news"),
            "پرتفوی": ("💼 پرتفوی", "/portfolio"),
            "سبد": ("💼 پرتفوی", "/portfolio"),
            "کدال": ("🏢 کدال", "/codal"),
            "هشدار": ("🔔 هشدار", "/alerts"),
            "طلا": ("🏅 طلا و ارز", "/macro"),
            "ماکرو": ("🏛️ ماکرو", "/macro"),
            "پیش‌بینی": ("🧠 پیش‌بینی", "/ml"),
            "مدل": ("🧠 ML", "/ml"),
            "بک‌تست": ("🧪 بک‌تست", "/backtest"),
            "سیگنال": ("📡 سیگنال", "/signals"),
            "نقشه": ("🗺️ نقشه", "/heatmap"),
            "ریسک": ("🛡️ ریسک", "/risk"),
            "ناهنجاری": ("🚨 ناهنجاری", "/anomalies"),
            "صندوق": ("🏦 صندوق", "/funds"),
            "نماد": ("📈 نمادها", "/instruments"),
            "داشبورد": ("🏠 داشبورد", "/"),
        }

        for keyword, (label, url) in page_map.items():
            if keyword in text:
                return {
                    "text": f"🔗 در حال انتقال به {label}...",
                    "type": "navigation",
                    "link": url,
                    "link_label": label,
                }

        return {"text": "صفحه مورد نظر یافت نشد.", "type": "error"}

    async def _handle_recommendation(self, user_id: str) -> dict[str, Any]:
        return await self._handle_find_best(user_id)

    def _unknown_response(self) -> dict[str, Any]:
        return {
            "text": (
                "🤖 **متوجه درخواست شما نشدم.**\n\n"
                "لطفاً یکی از موارد زیر را امتحان کنید:\n\n"
                "• «تحلیل فولاد»\n"
                "• «بهترین سهم‌ها»\n"
                "• «بازار چطوره؟»\n"
                "• «قیمت طلا»\n"
                "• «مقایسه فولاد و خودرو»\n"
                "• «help» برای راهنما"
            ),
            "type": "unknown",
            "suggestions": [
                "تحلیل فولاد",
                "بهترین سهم‌ها",
                "خلاصه بازار",
                "قیمت طلا",
                "help",
            ],
        }
