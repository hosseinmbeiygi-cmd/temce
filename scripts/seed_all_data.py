#!/usr/bin/env python
"""
Comprehensive Database Seed Script

Populates the database with realistic test data:
  - Markets (TSE, Farabourse, Payeh)
  - Instruments (30 symbols from various sectors)
  - News articles (20+ Persian financial news items)
  - Historical quotes (30 trading days of OHLC data for each symbol)
  - Signals (buy/sell signals for key symbols)
  - Recommendations (analyst recommendations)

Usage:
    python scripts/seed_all_data.py

Requirements:
    - Backend running (``python main.py`` in another terminal) OR
    - The script will initialize SQLite database directly
"""

from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.database import close_database, get_session, init_database
from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)

# ── Deterministic random (same every run) ──────────────────────
RNG = Random(42)


def _rand_price(base: float, variance: float) -> float:
    return round(base + RNG.uniform(-variance, variance), 0)


def _rand_int(lo: int, hi: int) -> int:
    return RNG.randint(lo, hi)





# ── Market definitions ─────────────────────────────────────────
MARKETS_DATA = [
    {"id": "mkt_tse", "name": "بورس اوراق بهادار تهران", "market_type": "bours", "exchange_code": "TSE"},
    {"id": "mkt_farabourse", "name": "فرابورس ایران", "market_type": "farabours", "exchange_code": "IFB"},
    {"id": "mkt_payeh", "name": "پایه", "market_type": "payeh", "exchange_code": "PAYEH"},
]


# ── Instrument definitions (30 symbols) ───────────────────────
INSTRUMENTS_DATA = [
    # symbol, name, isin, market_type, group_code, sector_code, shares_count, base_volume
    ("فولاد", "فولاد مبارکه اصفهان", "IRO1FOLD0001", "bours", "01", "metal", 10_000_000_000, 5_000_000),
    ("فملی", "ملی صنایع مس ایران", "IRO1FMEL0001", "bours", "01", "metal", 8_500_000_000, 4_000_000),
    ("شپنا", "پالایش نفت اصفهان", "IRO1SHPN0001", "bours", "06", "refinery", 6_000_000_000, 3_000_000),
    ("شتران", "پالایش نفت تهران", "IRO1SHTR0001", "bours", "06", "refinery", 5_500_000_000, 2_500_000),
    ("خودرو", "ایران خودرو", "IRO1IKCO0001", "bours", "02", "auto", 12_000_000_000, 8_000_000),
    ("خساپا", "سایپا", "IRO1SAPA0001", "bours", "02", "auto", 10_000_000_000, 6_000_000),
    ("وبملت", "بانک ملت", "IRO1BMLT0001", "bours", "02", "bank", 15_000_000_000, 10_000_000),
    ("وتجارت", "بانک تجارت", "IRO1BTJR0001", "bours", "02", "bank", 20_000_000_000, 12_000_000),
    ("وبصادر", "بانک صادرات", "IRO1BSDR0001", "bours", "02", "bank", 18_000_000_000, 11_000_000),
    ("پارسان", "پارسیان", "IRO1PARS0001", "bours", "04", "holding", 5_000_000_000, 2_000_000),
    ("شستا", "سرمایه گذاری تامین اجتماعی", "IRO1SHST0001", "bours", "04", "holding", 7_000_000_000, 3_000_000),
    ("فخوز", "فولاد خوزستان", "IRO1FKHZ0001", "bours", "01", "metal", 4_500_000_000, 2_000_000),
    ("ذوب", "ذوب آهن اصفهان", "IRO1ZOBE0001", "bours", "01", "metal", 6_000_000_000, 3_000_000),
    ("کگل", "گل گهر", "IRO1KGOL0001", "bours", "01", "mining", 3_000_000_000, 1_500_000),
    ("چادرملو", "چادرملو", "IRO1CHML0001", "bours", "01", "mining", 2_500_000_000, 1_200_000),
    ("رمپنا", "گروه مپنا", "IRO1MPNA0001", "bours", "03", "energy", 4_000_000_000, 2_000_000),
    ("رانفور", "انفورماتیک", "IRO1RINF0001", "farabours", "07", "it", 1_500_000_000, 800_000),
    ("وتوصا", "توسعه سرمایه اندوز", "IRO1VTOS0001", "bours", "04", "investment", 3_000_000_000, 1_500_000),
    ("شاروم", "آلومینیوم ایران", "IRO1AROM0001", "bours", "01", "metal", 2_000_000_000, 1_000_000),
    ("قشیر", "شیر پگاه", "IRO1GSHIR0001", "bours", "05", "food", 1_200_000_000, 600_000),
    ("غفاذر", "فاذر", "IRO1GFAZ0001", "bours", "05", "food", 800_000_000, 400_000),
    ("دماوند", "دماوند", "IRO1DMAV0001", "payeh", "02", "bank", 1_000_000_000, 500_000),
    ("سپ", "سپ", "IRO1SEP0001", "bours", "04", "holding", 2_000_000_000, 1_000_000),
    ("حافظ", "حافظ", "IRO1HAFZ0001", "farabours", "03", "energy", 900_000_000, 450_000),
    ("آریا", "آریا", "IRO1ARYA0001", "farabours", "01", "metal", 700_000_000, 350_000),
    ("سینا", "سینا", "IRO1SINA0001", "bours", "05", "food", 600_000_000, 300_000),
    ("کوثر", "کوثر", "IRO1KOWS0001", "bours", "04", "investment", 1_800_000_000, 900_000),
    ("فسبزوار", "فولاد سبزوار", "IRO1FSBZ0001", "farabours", "01", "metal", 1_100_000_000, 550_000),
    ("میدکو", "میدکو", "IRO1MIDK0001", "bours", "01", "mining", 2_200_000_000, 1_100_000),
    ("بوعلی", "بوعلی", "IRO1BOAL0001", "bours", "05", "pharma", 1_500_000_000, 750_000),
]

# ── News definitions (20 Persian financial news items) ────────
NEWS_DATA = [
    {
        "title": "افزایش ۲ درصدی شاخص کل بورس در معاملات امروز",
        "summary": "شاخص کل بورس اوراق بهادار تهران با رشد ۲ درصدی به کار خود پایان داد.",
        "content": "شاخص کل بورس اوراق بهادار تهران در پایان معاملات امروز با رشد ۲ درصدی مواجه شد. ارزش معاملات به بیش از ۵ هزار میلیارد تومان رسید. نمادهای فولاد، فملی و شپنا بیشترین تاثیر مثبت را بر شاخص داشتند.",
        "source": "تسنیم",
        "category": "market",
        "sentiment": "positive",
        "sentiment_score": 0.85,
        "symbols": ["فولاد", "فملی", "شپنا"],
    },
    {
        "title": "قیمت جهانی مس و فولاد افزایش یافت",
        "summary": "قیمت جهانی فلزات پایه در بازارهای جهانی روند صعودی به خود گرفت.",
        "content": "قیمت جهانی مس با رشد ۱.۵ درصدی به ۸۵۰۰ دلار رسید. قیمت سنگ آهن نیز با افزایش ۲ درصدی همراه بود. این موضوع می‌تواند بر سودآوری شرکت‌های فولادی و معدنی تاثیر مثبت بگذارد.",
        "source": "ایرنا",
        "category": "commodity",
        "sentiment": "positive",
        "sentiment_score": 0.75,
        "symbols": ["فولاد", "فملی", "کگل", "چادرملو"],
    },
    {
        "title": "قیمت نفت به بالای ۸۰ دلار رسید",
        "summary": "قیمت نفت برنت با افزایش ۱.۳ درصدی به مرز ۸۱ دلار رسید.",
        "content": "قیمت نفت برنت امروز با افزایش ۱.۳ درصدی به ۸۰.۸ دلار رسید. این افزایش قیمت می‌تواند بر سودآوری شرکت‌های پالایشی تاثیر مثبت داشته باشد.",
        "source": "بیزینس وایر",
        "category": "commodity",
        "sentiment": "positive",
        "sentiment_score": 0.70,
        "symbols": ["شپنا", "شتران"],
    },
    {
        "title": "افزایش نرخ بهره بین بانکی به ۲۳.۵ درصد",
        "summary": "نرخ بهره بین بانکی در هفته جاری با افزایش ۰.۳ درصدی همراه بود.",
        "content": "نرخ بهره بین بانکی در هفته جاری به ۲۳.۵ درصد رسید. کارشناسان معتقدند این افزایش می‌تواند باعث کاهش تقاضا در بازار سهام شود.",
        "source": "اکو ایران",
        "category": "economy",
        "sentiment": "negative",
        "sentiment_score": -0.6,
        "symbols": [],
    },
    {
        "title": "گزارش فروش ماهانه ایران خودرو منتشر شد",
        "summary": "ایران خودرو در گزارش ماهانه خود از افزایش فروش خبر داد.",
        "content": "گروه صنعتی ایران خودرو گزارش فروش ماهانه خود را منتشر کرد. این شرکت موفق به فروش ۴۵ هزار دستگاه خودرو به ارزش ۱۲ هزار میلیارد تومان شده است.",
        "source": "کدال",
        "category": "corporate",
        "sentiment": "positive",
        "sentiment_score": 0.80,
        "symbols": ["خودرو"],
    },
    {
        "title": "افزایش سرمایه بانک ملت تصویب شد",
        "summary": "مجمع عمومی فوق العاده بانک ملت با افزایش سرمایه ۵۰ درصدی موافقت کرد.",
        "content": "مجمع عمومی فوق العاده بانک ملت افزایش سرمایه ۵۰ درصدی از محل سود انباشته را تصویب کرد. این افزایش سرمایه به منظور بهبود نسبت کفایت سرمایه انجام می‌شود.",
        "source": "کدال",
        "category": "corporate",
        "sentiment": "positive",
        "sentiment_score": 0.90,
        "symbols": ["وبملت"],
    },
    {
        "title": "نرخ تورم در آبان ماه اعلام شد",
        "summary": "مرکز آمار ایران نرخ تورم نقطه به نقطه را ۳۲.۵ درصد اعلام کرد.",
        "content": "مرکز آمار ایران اعلام کرد نرخ تورم نقطه به نقطه در آبان ماه به ۳۲.۵ درصد رسیده است. این رقم نسبت به ماه قبل ۱.۲ درصد کاهش داشته است.",
        "source": "ایسنا",
        "category": "economy",
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "symbols": [],
    },
    {
        "title": "صادرات غیرنفتی ایران ۱۵ درصد افزایش یافت",
        "summary": "حجم صادرات غیرنفتی کشور در ۸ ماهه نخست سال جاری ۱۵ درصد رشد داشت.",
        "content": "گمرک ایران اعلام کرد صادرات غیرنفتی کشور در ۸ ماهه نخست سال جاری با رشد ۱۵ درصدی به ۳۵ میلیارد دلار رسید. فولاد، پتروشیمی و محصولات معدنی بیشترین سهم را داشتند.",
        "source": "مهر",
        "category": "economy",
        "sentiment": "positive",
        "sentiment_score": 0.65,
        "symbols": ["فولاد", "شپنا"],
    },
    {
        "title": "شاخص فرابورس به کانال ۲۵ هزار واحد وارد شد",
        "summary": "شاخص کل فرابورس برای اولین بار به کانال ۲۵ هزار واحد وارد شد.",
        "content": "شاخص کل فرابورس با رشد ۱.۸ درصدی وارد کانال ۲۵ هزار واحد شد. نمادهای آریا، حافظ و رانفور بیشترین تاثیر را در این رشد داشتند.",
        "source": "فرابورس",
        "category": "market",
        "sentiment": "positive",
        "sentiment_score": 0.78,
        "symbols": ["آریا", "حافظ", "رانفور"],
    },
    {
        "title": "عرضه اولیه جدید در راه فرابورس",
        "summary": "یک شرکت جدید در بازار فرابورس عرضه اولیه خواهد شد.",
        "content": "مدیریت بازار فرابورس از عرضه اولیه سهام یک شرکت دارویی در آینده نزدیک خبر داد. زمان و قیمت عرضه متعاقبا اعلام خواهد شد.",
        "source": "سنا",
        "category": "market",
        "sentiment": "neutral",
        "sentiment_score": 0.2,
        "symbols": [],
    },
    {
        "title": "فولاد مبارکه سال مالی موفقی را پشت سر گذاشت",
        "summary": "فولاد مبارکه اصفهان در گزارش سالانه خود از رشد ۳۰ درصدی سودآوری خبر داد.",
        "content": "شرکت فولاد مبارکه اصفهان گزارش سالانه خود را منتشر کرد. این شرکت موفق به ثبت سود ۴۵ هزار میلیارد تومانی شده است که نشان دهنده رشد ۳۰ درصدی نسبت به سال قبل است.",
        "source": "کدال",
        "category": "corporate",
        "sentiment": "positive",
        "sentiment_score": 0.92,
        "symbols": ["فولاد"],
    },
    {
        "title": "ملی مس از رکورد تولید خبر داد",
        "summary": "شرکت ملی صنایع مس ایران رکورد جدید تولید را ثبت کرد.",
        "content": "مدیرعامل شرکت ملی صنایع مس ایران اعلام کرد تولید کاتد مس در این شرکت به رکورد ۳۰۰ هزار تن رسیده است. این میزان ۱۲ درصد بیشتر از سال گذشته است.",
        "source": "ایرنا",
        "category": "corporate",
        "sentiment": "positive",
        "sentiment_score": 0.88,
        "symbols": ["فملی"],
    },
    {
        "title": "تحلیل تکنیکال شاخص کل: مقاومت ۲.۳ میلیون واحدی",
        "summary": "کارشناسان بازار سرمایه سطح مقاومت شاخص کل را ۲.۳ میلیون واحد می‌دانند.",
        "content": "تحلیلگران تکنیکال معتقدند شاخص کل بورس در صورت عبور از مقاومت ۲.۳ میلیون واحدی، می‌تواند تا ۲.۵ میلیون واحد رشد کند. در غیر این صورت احتمال اصلاح تا ۲.۱ میلیون واحد وجود دارد.",
        "source": "تحلیلگران",
        "category": "analysis",
        "sentiment": "neutral",
        "sentiment_score": 0.1,
        "symbols": [],
    },
    {
        "title": "افزایش قیمت محصولات پتروشیمی در بازار جهانی",
        "summary": "قیمت محصولات پتروشیمی در بازارهای جهانی روند افزایشی به خود گرفته است.",
        "content": "قیمت محصولات پتروشیمی به دنبال افزایش قیمت نفت، با رشد ۲ تا ۴ درصدی همراه بوده است. این موضوع می‌تواند بر سودآوری شرکت‌های پتروشیمی تاثیر مثبت داشته باشد.",
        "source": "شانا",
        "category": "commodity",
        "sentiment": "positive",
        "sentiment_score": 0.72,
        "symbols": ["شپنا", "شتران"],
    },
    {
        "title": "بورس هفته را مثبت آغاز کرد",
        "summary": "شاخص کل بورس در اولین روز معاملاتی هفته با رشد همراه شد.",
        "content": "شاخص کل بورس اوراق بهادار تهران در اولین روز معاملاتی هفته جاری با رشد ۱.۵ درصدی به کار خود پایان داد. ارزش صف‌های خرید از ۳ هزار میلیارد تومان فراتر رفت.",
        "source": "اقتصاد آنلاین",
        "category": "market",
        "sentiment": "positive",
        "sentiment_score": 0.82,
        "symbols": [],
    },
    {
        "title": "بانک مرکزی نرخ ارز را اعلام کرد",
        "summary": "نرخ رسمی دلار آمریکا در مرکز مبادله ارز و طلا اعلام شد.",
        "content": "بانک مرکزی نرخ رسمی دلار آمریکا را ۴۲ هزار تومان اعلام کرد. نرخ یورو نیز ۴۵ هزار تومان تعیین شد.",
        "source": "بانک مرکزی",
        "category": "economy",
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "symbols": [],
    },
    {
        "title": "بازار سرمایه در انتظار انتشار صورت‌های مالی",
        "summary": "فصل انتشار صورت‌های مالی نیمه دوم سال آغاز شده است.",
        "content": "شرکت‌های بورسی موظفند صورت‌های مالی خود را به سازمان بورس ارسال کنند. پیش بینی می‌شود بسیاری از شرکت‌های فولادی و معدنی گزارش‌های خوبی ارائه دهند.",
        "source": "سنا",
        "category": "market",
        "sentiment": "positive",
        "sentiment_score": 0.55,
        "symbols": ["فولاد", "فملی", "کگل"],
    },
    {
        "title": "تصویب لایحه بودجه ۱۴۰۶ در مجلس",
        "summary": "لایحه بودجه سال ۱۴۰۶ با افزایش ۲۰ درصدی هزینه‌ها به تصویب رسید.",
        "content": "مجلس شورای اسلامی لایحه بودجه سال ۱۴۰۶ را به تصویب رساند. نرخ تورم هدف ۲۵ درصد تعیین شده است. افزایش قیمت حامل‌های انرژی می‌تواند بر شرکت‌های انرژی‌بر تاثیر منفی بگذارد.",
        "source": "خبرگزاری صدا و سیما",
        "category": "economy",
        "sentiment": "negative",
        "sentiment_score": -0.4,
        "symbols": [],
    },
    {
        "title": "سایپا از ورود شریک خارجی خبر داد",
        "summary": "گروه خودروسازی سایپا از مذاکره با یک خودروساز خارجی برای سرمایه‌گذاری مشترک خبر داد.",
        "content": "مدیرعامل گروه خودروسازی سایپا اعلام کرد این شرکت در حال مذاکره با یک خودروساز معتبر خارجی برای سرمایه‌گذاری مشترک است. این همکاری می‌تواند به تولید خودروهای جدید با کیفیت بالاتر منجر شود.",
        "source": "ایسنا",
        "category": "corporate",
        "sentiment": "positive",
        "sentiment_score": 0.68,
        "symbols": ["خساپا"],
    },
    {
        "title": "قیمت سکه و طلا کاهش یافت",
        "summary": "قیمت سکه امامی و طلا در بازار تهران با کاهش همراه بود.",
        "content": "قیمت سکه امامی در بازار تهران به ۳۵ میلیون تومان رسید که کاهش ۲ درصدی نسبت به هفته قبل دارد. قیمت طلای ۱۸ عیار نیز ۳.۲ میلیون تومان معامله می‌شود.",
        "source": "اتحادیه طلا",
        "category": "economy",
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "symbols": [],
    },
]


# ── Seed functions ─────────────────────────────────────────────

async def seed_markets(session: Any) -> int:
    """Seed market data."""
    from repositories.market_repository import Market as MarketEntity, MarketRepository

    repo = MarketRepository(session=session)
    count = 0

    for m in MARKETS_DATA:
        entity = MarketEntity(
            id=m["id"],
            name=m["name"],
            market_type=m["market_type"],
            exchange_code=m["exchange_code"],
        )
        result = await repo.save(entity)
        if result.success:
            count += 1
            logger.info("  ✓ Market: %s", m["name"])

    return count


async def seed_instruments(session: Any) -> dict[str, str]:
    """Seed instrument data. Returns mapping of symbol -> id."""
    from domain.common.enum_types import AssetClass, MarketType
    from domain.instruments.instrument import Instrument
    from repositories.instrument_repository import InstrumentRepository

    repo = InstrumentRepository(session=session)
    symbol_to_id: dict[str, str] = {}

    for symbol, name, isin, market_type, group_code, sector_code, shares, base_vol in INSTRUMENTS_DATA:
        inst_id = new_id("inst")
        instrument = Instrument(
            id=inst_id,
            symbol=symbol,
            name=name,
            isin=isin,
            market_type=MarketType(market_type),
            asset_class=AssetClass.EQUITY if market_type != "farabours" else AssetClass.EQUITY,
            group_code=group_code,
            sector_code=sector_code,
            shares_count=shares,
            base_volume=base_vol,
            lot_size=1000,
            par_value=1000,
            tick_size=10.0,
        )
        result = await repo.save(instrument)
        if result.success:
            symbol_to_id[symbol] = inst_id
            logger.info("  ✓ Instrument: %s (%s)", symbol, name)

    return symbol_to_id


async def seed_news(session: Any) -> int:
    """Seed news articles."""
    from domain.news.news_item import NewsItem
    from repositories.news_repository import NewsRepository

    repo = NewsRepository(session=session)
    count = 0
    now = datetime.now(timezone.utc)

    for i, item in enumerate(NEWS_DATA):
        # Stagger publish times
        pub_date = now - timedelta(hours=i * 3, minutes=_rand_int(0, 59))

        news = NewsItem(
            id=new_id("news"),
            title=item["title"],
            summary=item["summary"],
            content=item["content"],
            source=item["source"],
            category=item["category"],
            sentiment=item["sentiment_score"],
            sentiment_label=item["sentiment"],
            symbols=item["symbols"],
            publish_date=pub_date,
            data_source="seed",
        )
        result = await repo.save(news)
        if result.success:
            count += 1

    return count


async def seed_quotes(session: Any, symbol_to_id: dict[str, str]) -> int:
    """Seed 30 trading days of OHLC quote data for each symbol."""
    from domain.market_data.quote import Quote
    from repositories.quote_repository import QuoteRepository

    repo = QuoteRepository(session=session)

    # Base prices for each symbol
    BASE_PRICES = {
        "فولاد": 5800, "فملی": 8500, "شپنا": 4500, "شتران": 3800,
        "خودرو": 2800, "خساپا": 1500, "وبملت": 3200, "وتجارت": 1800,
        "وبصادر": 1600, "پارسان": 12000, "شستا": 8000, "فخوز": 3500,
        "ذوب": 4200, "کگل": 25000, "چادرملو": 18000, "رمپنا": 7000,
        "رانفور": 4500, "وتوصا": 5500, "شاروم": 3000, "قشیر": 15000,
        "غفاذر": 12000, "دماوند": 2500, "سپ": 4000, "حافظ": 3500,
        "آریا": 2000, "سینا": 8000, "کوثر": 4500, "فسبزوار": 3000,
        "میدکو": 6000, "بوعلی": 9500,
    }

    count = 0
    today = datetime.now(timezone.utc)

    # Generate 30 trading days (Mon-Fri, skipping weekends)
    for day_offset in range(30):
        day = today - timedelta(days=day_offset)
        # Skip Friday (5) and Saturday (6) in Iran calendar approximation
        # Using weekday(): Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
        # Iran weekend: Thu (3), Fri (4)
        if day.weekday() in (3, 4):
            continue

        date_str = day.strftime("%Y-%m-%d")

        for symbol, inst_id in symbol_to_id.items():
            base = BASE_PRICES.get(symbol, 5000)

            # Random walk from base
            daily_change_pct = _rand_price(0, 2.5)
            direction = 1 if RNG.random() > 0.45 else -1

            price_yesterday = base + _rand_price(-500, 500)
            price_open = price_yesterday + (price_yesterday * daily_change_pct * direction / 100)
            price_high = price_open * (1 + _rand_price(0.5, 1.8) / 100)
            price_low = price_open * (1 - _rand_price(0.5, 1.8) / 100)
            price_close = _rand_price(price_low, price_high)
            price_change = price_close - price_yesterday
            price_change_pct = ((price_close - price_yesterday) / price_yesterday) * 100 if price_yesterday else 0

            volume = _rand_int(500_000, base_volume := BASE_PRICES.get(symbol, 5000) * 100)
            value = volume * price_close
            trade_count = _rand_int(500, 5000)

            quote = Quote(
                id=new_id("q"),
                instrument_id=inst_id,
                symbol=symbol,
                price_close=round(price_close, 0),
                price_open=round(price_open, 0),
                price_high=round(price_high, 0),
                price_low=round(price_low, 0),
                price_last=round(price_close, 0),
                price_change=round(price_change, 0),
                price_change_pct=round(price_change_pct, 2),
                volume=volume,
                value=round(value, 0),
                trade_count=trade_count,
                price_yesterday=round(price_yesterday, 0),
                price_first=round(price_open, 0),
                price_max=round(price_high, 0),
                price_min=round(price_low, 0),
                date=date_str,
                time="12:30:00",
                timeframe="1d",
                data_source="seed",
            )
            result = await repo.save(quote)
            if result.success:
                count += 1

    return count


async def seed_signals(session: Any, symbol_to_id: dict[str, str]) -> int:
    """Seed trading signals for key symbols."""
    from domain.analytics.signal import Signal
    from domain.common.enum_types import SignalType
    from repositories.signal_repository import SignalRepository

    repo = SignalRepository(session=session)
    count = 0

    SIGNALS_DATA = [
        # (symbol, signal_type, score, confidence, strategy, description)
        ("فولاد", SignalType.BULLISH, 82, 0.85, "Momentum", "روند صعودی فولاد با حجم بالای معاملات تایید شد"),
        ("فملی", SignalType.BULLISH, 78, 0.80, "Momentum", "قیمت مس جهانی در حال افزایش است"),
        ("شپنا", SignalType.NEUTRAL, 50, 0.60, "MeanReversion", "شپنا در محدوده خنثی قرار دارد"),
        ("خودرو", SignalType.BEARISH, 35, 0.70, "Trend", "روند نزولی خودرو با افزایش عرضه"),
        ("وبملت", SignalType.BULLISH, 75, 0.82, "Value", "افزایش سرمایه می‌تواند محرک قیمت باشد"),
        ("کگل", SignalType.STRONG_BUY, 90, 0.92, "Momentum", "روند صعودی قوی با تایید اندیکاتورها"),
        ("چادرملو", SignalType.BULLISH, 72, 0.78, "Value", "قیمت زیر ارزش ذاتی"),
        ("پارسان", SignalType.NEUTRAL, 48, 0.55, "Volatility", "نوسانات محدود"),
        ("شتران", SignalType.BULLISH, 68, 0.72, "Momentum", "افزایش قیمت نفت محرک مثبت"),
        ("وتجارت", SignalType.BEARISH, 30, 0.65, "Trend", "فشار فروش بالا"),
    ]

    for symbol, signal_type, score, confidence, strategy, desc in SIGNALS_DATA:
        inst_id = symbol_to_id.get(symbol)
        if not inst_id:
            continue

        signal = Signal(
            id=new_id("sig"),
            instrument_id=inst_id,
            signal_type=signal_type,
            score=score,
            confidence=confidence,
            symbol=symbol,
            source="seed_analysis",
            strategy=strategy,
            description=desc,
            timeframe="1d",
        )
        result = await repo.save(signal)
        if result.success:
            count += 1

    return count


async def seed_recommendations(session: Any, symbol_to_id: dict[str, str]) -> int:
    """Seed analyst recommendations for key symbols.

    Note: RecommendationRepository only uses InMemoryRepository,
    so we write directly to the ORM model for persistence.
    """
    from domain.common.enum_types import RecommendationAction
    from models.recommendation import RecommendationModel

    count = 0

    RECS_DATA = [
        # (symbol, action, confidence, target_price, rationale, horizon)
        ("فولاد", RecommendationAction.BUY, 0.85, 7200, "قیمت جهانی فولاد در حال افزایش و صورت‌های مالی قوی", "medium_term"),
        ("فملی", RecommendationAction.BUY, 0.80, 10500, "رشد قیمت مس جهانی و افزایش تولید", "medium_term"),
        ("شپنا", RecommendationAction.HOLD, 0.55, 5000, "عدم اطمینان از حاشیه سود پالایش", "short_term"),
        ("خودرو", RecommendationAction.REDUCE, 0.65, 2500, "روند نزولی و افزایش رقابت", "short_term"),
        ("وبملت", RecommendationAction.ACCUMULATE, 0.78, 4000, "افزایش سرمایه و بهبود نسبت کفایت", "long_term"),
        ("کگل", RecommendationAction.BUY, 0.90, 32000, "رکوردزنی تولید و قیمت‌های جهانی بالا", "medium_term"),
        ("چادرملو", RecommendationAction.BUY, 0.72, 22000, "ارزش ذاتی بالاتر از قیمت بازار", "medium_term"),
        ("شتران", RecommendationAction.HOLD, 0.60, 4200, "چشم‌انداز مبهم با توجه به نوسانات نفت", "medium_term"),
    ]

    for symbol, action, confidence, target, rationale, horizon in RECS_DATA:
        inst_id = symbol_to_id.get(symbol)
        if not inst_id:
            continue

        orm = RecommendationModel(
            id=new_id("rec"),
            instrument_id=inst_id,
            symbol=symbol,
            action=action.value,
            confidence=confidence,
            target_price=target,
            rationale=rationale,
            horizon=horizon,
            data_source="seed_analyst",
        )
        session.add(orm)
        count += 1

    return count


# ── Main ────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("=" * 55)
    logger.info("  Comprehensive Database Seed Script")
    logger.info("=" * 55)

    await init_database()

    async for session in get_session():
        logger.info("")
        logger.info("📊 Seeding markets...")
        mkt_count = await seed_markets(session)
        logger.info("  → %d markets seeded", mkt_count)

        logger.info("")
        logger.info("📈 Seeding instruments...")
        symbol_to_id = await seed_instruments(session)
        logger.info("  → %d instruments seeded", len(symbol_to_id))

        logger.info("")
        logger.info("📰 Seeding news articles...")
        news_count = await seed_news(session)
        logger.info("  → %d news articles seeded", news_count)

        logger.info("")
        logger.info("💰 Seeding historical quotes...")
        quote_count = await seed_quotes(session, symbol_to_id)
        logger.info("  → %d quotes seeded (30 days × %d symbols)", quote_count, len(symbol_to_id))

        logger.info("")
        logger.info("🔔 Seeding signals...")
        sig_count = await seed_signals(session, symbol_to_id)
        logger.info("  → %d signals seeded", sig_count)

        logger.info("")
        logger.info("📋 Seeding recommendations...")
        rec_count = await seed_recommendations(session, symbol_to_id)
        logger.info("  → %d recommendations seeded", rec_count)

    await close_database()

    logger.info("")
    logger.info("=" * 55)
    logger.info("  ✅ Seeding complete!")
    logger.info("  Markets:         %d", mkt_count)
    logger.info("  Instruments:     %d", len(symbol_to_id))
    logger.info("  News:            %d", news_count)
    logger.info("  Quotes:          %d", quote_count)
    logger.info("  Signals:         %d", sig_count)
    logger.info("  Recommendations: %d", rec_count)
    logger.info("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
