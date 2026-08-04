"""SuggestionEngine — Generate proactive suggestions for users (Level 18).

Provides:
- Context-aware follow-up suggestions
- Personalized recommendations based on user history
- Market-driven suggestions (top movers, news)
- Smart "next steps" for each intent
"""

from __future__ import annotations

import random
from typing import Any

from services.chat.dialog_manager import DialogManager
from services.chat.personalizer import Personalizer


class SuggestionEngine:
    """Generate intelligent suggestions for users."""

    # Intent-specific follow-up suggestions
    INTENT_SUGGESTIONS: dict[str, list[str]] = {
        "analyze_symbol": [
            "مقایسه با نماد دیگر",
            "اخبار این نماد",
            "نمودار قیمت",
            "پیش‌بینی قیمت",
            "اضافه به دیده‌بان",
        ],
        "compare_symbols": [
            "تحلیل نماد برتر",
            "مقایسه با نماد سوم",
            "اخبار نمادها",
            "بهترین سهم‌ها",
        ],
        "find_best": [
            "تحلیل اولین نماد",
            "فیلتر با SMC بالای 0.7",
            "سهام ارزنده",
            "غربال‌گری حرفه‌ای",
        ],
        "find_cheap": [
            "تحلیل ارزان‌ترین نماد",
            "فیلتر P/E<5",
            "بهترین سهم‌ها",
        ],
        "market_overview": [
            "پرمتقاضی‌ترین‌ها",
            "بیشترین کاهش",
            "تحلیل شاخص",
            "نقشه بازار",
        ],
        "get_news": [
            "خلاصه بازار",
            "اخبار نماد دیگر",
            "تحلیل احساسات بازار",
            "کدال",
        ],
        "screener": [
            "غربال با SMC بالا",
            "نمادهای با نقدشوندگی قوی",
            "فیلتر خرید حقیقی",
            "تحلیل اولین نتیجه",
        ],
        "dynamic_filter": [
            "ذخیره فیلتر",
            "تغییر فیلتر",
            "تحلیل نتایج",
            "مقایسه نتایج برتر",
        ],
        "portfolio_summary": [
            "اضافه سهم جدید",
            "بهبود پرتفوی",
            "تحلیل ریسک پرتفوی",
            "بک‌تست",
        ],
        "add_watchlist": [
            "دیده‌بان من",
            "اضافه نماد دیگر",
            "ثبت هشدار",
            "تحلیل نماد",
        ],
    }

    # Market-aware suggestions
    MARKET_SUGGESTIONS: list[str] = [
        "پرتحرک‌ترین نمادهای امروز",
        "بهترین سهام از نظر SMC",
        "نمادهای با خرید حقیقی بالا",
        "آخرین اخبار بازار",
        "ناهنجاری‌های قیمتی",
        "سیگنال‌های معاملاتی",
        "قیمت طلا و دلار",
    ]

    # General purpose suggestions for any context
    GENERAL_SUGGESTIONS: list[str] = [
        "تحلیل فولاد",
        "بهترین سهم‌ها",
        "خلاصه بازار",
        "بازار چطوره؟",
        "قیمت طلا",
        "پیش‌بینی بازار",
        "اخبار بازار",
        "اضافه فولاد به دیده‌بان",
        "مقایسه فولاد و شپنا",
        "نقشه بازار",
        "فیلتر RSI<30",
        "پرتفوی من",
        "سیگنال‌های خرید",
        "ناهنجاری‌های بازار",
        "help",
    ]

    def __init__(
        self,
        personalizer: Personalizer | None = None,
        dialog_manager: DialogManager | None = None,
    ):
        self._personalizer = personalizer
        self._dialog = dialog_manager

    def get_suggestions(
        self,
        user_id: str,
        intent: str,
        entities: dict[str, Any],
        response_type: str = "text",
        max_suggestions: int = 4,
    ) -> list[str]:
        """Get context-aware suggestions for the user."""
        suggestions: list[str] = []

        # 1. Intent-specific suggestions
        intent_suggestions = self.INTENT_SUGGESTIONS.get(intent, [])
        symbols = entities.get("symbols", [])

        for s in intent_suggestions[:2]:
            # Personalize with symbol if available
            if "{symbol}" in s and symbols:
                s = s.replace("{symbol}", symbols[0])
            elif "نماد" in s and symbols:
                s = s.replace("نماد", symbols[0])
            if s not in suggestions:
                suggestions.append(s)

        # 2. Personalized suggestions from user history
        if self._personalizer:
            favs = self._personalizer.store.get_favorite_symbols(user_id)
            if favs:
                # Suggest analyzing a favorite symbol
                fav_sym = random.choice(favs[:3])
                suggestions.append(f"تحلیل {fav_sym}")

            # Suggest recent filter
            recent_filters = self._personalizer.store.get_recent_filters(user_id)
            if recent_filters:
                filter_suggestion = f"اعمال فیلتر {recent_filters[0]}"
                if filter_suggestion not in suggestions:
                    suggestions.append(filter_suggestion)

        # 3. Context-based suggestions from dialog
        if self._dialog:
            context = self._dialog.get_context(user_id)
            last_intent = context.get("last_intent")
            if last_intent and last_intent != intent:
                # User switched intents — suggest returning to previous
                pass  # Skip for now

        # 4. Add general suggestions to fill
        general_pool = self.GENERAL_SUGGESTIONS + self.MARKET_SUGGESTIONS
        random.shuffle(general_pool)
        for g in general_pool:
            if g not in suggestions:
                suggestions.append(g)
                if len(suggestions) >= max_suggestions:
                    break

        return suggestions[:max_suggestions]

    def get_market_suggestions(self) -> list[str]:
        """Get market-aware suggestions."""
        return random.sample(self.MARKET_SUGGESTIONS, min(3, len(self.MARKET_SUGGESTIONS)))

    def get_intro_suggestions(self, user_id: str) -> list[str]:
        """Get personalized intro suggestions for a new conversation."""
        suggestions = []

        if self._personalizer:
            favs = self._personalizer.store.get_favorite_symbols(user_id)
            if favs:
                suggestions.append(f"تحلیل {favs[0]}")
                if len(favs) > 1:
                    suggestions.append(f"مقایسه {favs[0]} و {favs[1]}")

        suggestions.extend([
            "خلاصه بازار",
            "بهترین سهم‌ها",
            "قیمت طلا",
            "پیش‌بینی بازار",
        ])

        return suggestions[:5]
