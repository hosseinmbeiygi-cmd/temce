from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.news.rss.rss_provider import RSSNewsProvider

logger = get_logger(__name__)


DOMESTIC_RSS_FEEDS: dict[str, str] = {
    # Note: mehrnews, tasnim, irna, fars, donya-eqtesad — blocked or no valid RSS.
    # Note: isna removed — general news, not market-relevant.
    # Only fardayeeghtesad (business/economy/Bourse-focused) feeds remain.

    # روزنامه فردای اقتصاد (Fardaye Eqtesad) — اقتصاد و بورس
    "fardaye_latest": "https://www.fardayeeghtesad.com/rss",                    # آخرین اخبار
    "fardaye_homepage": "https://www.fardayeeghtesad.com/rss-homepage",          # صفحه اصلی
    "fardaye_popular": "https://www.fardayeeghtesad.com/rss/pl/232",             # پربیننده
    "fardaye_macro": "https://www.fardayeeghtesad.com/rss/tp/2",                # اقتصاد کلان
    "fardaye_bourse": "https://www.fardayeeghtesad.com/rss/tp/20",              # بورس
    "fardaye_gold": "https://www.fardayeeghtesad.com/rss/tp/56",                # طلا و ارز
    "fardaye_crypto": "https://www.fardayeeghtesad.com/rss/tp/57",              # رمزارز
    "fardaye_industry": "https://www.fardayeeghtesad.com/rss/tp/3",             # صنعت، معدن و تجارت
    "fardaye_energy": "https://www.fardayeeghtesad.com/rss/tp/15",              # انرژی
    "fardaye_housing": "https://www.fardayeeghtesad.com/rss/tp/71",             # مسکن
    "fardaye_auto": "https://www.fardayeeghtesad.com/rss/tp/19",                # خودرو
    "fardaye_tech": "https://www.fardayeeghtesad.com/rss/tp/16",                # تکنولوژی و استارتاپ
    "fardaye_companies": "https://www.fardayeeghtesad.com/rss/tp/66",           # شرکت‌ها
    "fardaye_enterprise": "https://www.fardayeeghtesad.com/rss/tp/78",          # بنگاه‌ها
    "fardaye_market": "https://www.fardayeeghtesad.com/rss/tp/61",              # بازارچه
    "fardaye_think_tank": "https://www.fardayeeghtesad.com/rss/tp/67",          # اندیشکده
    # برنامه‌های تخصصی بورس و اقتصاد فردای اقتصاد
    "fardaye_prog_boursan": "https://www.fardayeeghtesad.com/rss/tp/88",        # برنامه‌ها > بورسان
    "fardaye_prog_bank": "https://www.fardayeeghtesad.com/rss/tp/131",          # برنامه‌ها > میز بانک
    "fardaye_prog_crypto": "https://www.fardayeeghtesad.com/rss/tp/94",         # برنامه‌ها > فردای کریپتو
    "fardaye_prog_oil": "https://www.fardayeeghtesad.com/rss/tp/108",           # برنامه‌ها > نفت و پتروشیمی
    "fardaye_prog_mining": "https://www.fardayeeghtesad.com/rss/tp/128",        # برنامه‌ها > میز معدن و فولاد
    "fardaye_prog_market": "https://www.fardayeeghtesad.com/rss/tp/132",        # برنامه‌ها > فردای بازارها
    "fardaye_prog_industry": "https://www.fardayeeghtesad.com/rss/tp/92",       # برنامه‌ها > فردای صنعت
    "fardaye_prog_auto": "https://www.fardayeeghtesad.com/rss/tp/129",          # برنامه‌ها > میز خودرو
    "fardaye_prog_trade": "https://www.fardayeeghtesad.com/rss/tp/126",         # برنامه‌ها > میز صنعت و تجارت
    "fardaye_prog_innovation": "https://www.fardayeeghtesad.com/rss/tp/134",    # برنامه‌ها > اقتصاد نوآوری
    "fardaye_prog_startup": "https://www.fardayeeghtesad.com/rss/tp/95",        # برنامه‌ها > تک شاخ
    "fardaye_prog_equity": "https://www.fardayeeghtesad.com/rss/tp/90",         # برنامه‌ها > خط سود
    "fardaye_prog_invest": "https://www.fardayeeghtesad.com/rss/tp/105",        # برنامه‌ها > سواد سرمایه‌گذاری
    "fardaye_prog_watchlist": "https://www.fardayeeghtesad.com/rss/tp/125",     # برنامه‌ها > واچ‌لیست
    "fardaye_prog_editorial": "https://www.fardayeeghtesad.com/rss/tp/99",      # برنامه‌ها > سرمقاله
    "fardaye_prog_policy": "https://www.fardayeeghtesad.com/rss/tp/91",         # برنامه‌ها > سیاست و دیپلماسی
    "fardaye_prog_gov": "https://www.fardayeeghtesad.com/rss/tp/93",            # برنامه‌ها > حکمرانی خوب
}


class RSSDomesticProvider(RSSNewsProvider):
    """Fetches Iranian domestic news from a configured set of Persian RSS feeds.

    Fetches feeds in parallel using asyncio.gather for better performance.
    """

    def __init__(self) -> None:
        super().__init__(name="rss_domestic")
        self.feeds = DOMESTIC_RSS_FEEDS.copy()

    async def fetch_news(
        self,
        symbols: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Result[list[dict[str, Any]]]:
        source = kwargs.get("source")
        if source and source in self.feeds:
            result = await self.parse_feed(self.feeds[source], limit)
            if result.success and result.value:
                # Tag articles with this specific feed source
                for article in result.value:
                    article["_source_feed"] = source
            return result

        # Delegate to parent for parallel fetch, forwarding all parameters
        return await super().fetch_news(
            symbols=symbols,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            **kwargs,
        )

    async def search_news(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("Search not supported for RSS feeds")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self.feeds)} RSS feeds configured"}
