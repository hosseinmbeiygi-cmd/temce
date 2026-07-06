"""
اسکریپت تست دستی BrsApi - ذخیره مستقیم در دیتابیس
====================================================
با استفاده از مدل‌ها و parserهای موجود، داده‌ها مستقیماً
در جداول PostgreSQL ذخیره می‌شوند.

نحوه اجرا:
    python test_brsapi_manual.py                          # تست اتصال
    python test_brsapi_manual.py --all                    # همه بخش‌ها
    python test_brsapi_manual.py --section commodity      # فقط کامودیتی
    python test_brsapi_manual.py --section crypto         # فقط کریپتو
    python test_brsapi_manual.py --section gold_coin      # فقط طلا و سکه
    python test_brsapi_manual.py --section currency       # فقط نرخ ارز
    python test_brsapi_manual.py --section tsetmc         # فقط TSETMC
    python test_brsapi_manual.py --section codal          # فقط کدال
    python test_brsapi_manual.py --section ime            # فقط بورس کالا
    python test_brsapi_manual.py --list                   # لیست بخش‌ها
"""

import asyncio
import argparse
import sys
import io
import time
import json
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

# ── Models ──────────────────────────────────────
from brsapi.models.commodity import (
    CommodityPriceModel, GoldCoinPriceModel, GoldCoinHistoryModel,
    CurrencyPriceModel, Currency24hModel, Gold24hModel,
)
from brsapi.models.crypto import CryptoPriceModel
from brsapi.models.tsetmc import (
    SymbolSnapshotModel, SymbolDetailModel, IndexValueModel,
    NavRecordModel, OptionSnapshotModel, IntradayTradeModel,
    HistoricalDailyModel, HistoricalRealLegalModel, CandlestickModel,
    ShareholderRecordModel,
)
from brsapi.models.ime import (
    ImeFutureModel, ImeOptionModel, ImeCertificateModel,
    ImeFundModel, ImePhysicalTradeModel,
)
from brsapi.models.codal import CodalAnnouncementModel

# ── Parsers ─────────────────────────────────────
from brsapi.parsers.commodity import CommodityParser, GoldCoinParser, CurrencyParser, Gold24hParser
from brsapi.parsers.crypto import CryptoParser
from brsapi.parsers.tsetmc import TsetmcParser
from brsapi.parsers.ime import ImeParser
from brsapi.parsers.codal import CodalParser

# ── Config ──────────────────────────────────────
from brsapi.config import BrsApiEndpoints

# ── DB URL ──────────────────────────────────────
DATABASE_URL = "postgresql+asyncpg://hossein:1343@localhost:5432/my_first_db"
API_KEY = "Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
BASE_URL = "https://Api.BrsApi.ir"


# ============================================
#  Section Registry
# ============================================

SECTIONS = {
    "commodity": {
        "name": "کامودیتی‌ها",
        "endpoint": BrsApiEndpoints.COMMODITY,
        "model": CommodityPriceModel,
        "parser": CommodityParser.parse,
        "category": "commodity",
    },
    "crypto": {
        "name": "ارزهای دیجیتال",
        "endpoint": BrsApiEndpoints.CRYPTOCURRENCY,
        "model": CryptoPriceModel,
        "parser": CryptoParser.parse,
        "category": "cryptocurrency",
    },
    "gold_coin": {
        "name": "طلا و سکه",
        "endpoint": BrsApiEndpoints.GOLD_COIN,
        "model": GoldCoinPriceModel,
        "parser": GoldCoinParser.parse,
        "category": "commodity",
    },
    "gold_24h": {
        "name": "تغییرات ۲۴h طلا",
        "endpoint": BrsApiEndpoints.GOLD_24H,
        "model": Gold24hModel,
        "parser": Gold24hParser.parse,
        "category": "commodity",
    },
    "currency": {
        "name": "نرخ ارز",
        "endpoint": BrsApiEndpoints.CURRENCY,
        "model": CurrencyPriceModel,
        "parser": CurrencyParser.parse,
        "category": "commodity",
    },
    "currency_24h": {
        "name": "تغییرات ۲۴h ارز",
        "endpoint": BrsApiEndpoints.CURRENCY_24H,
        "model": Currency24hModel,
        "parser": CurrencyParser.parse_24h,
        "category": "commodity",
    },
    "symbols": {
        "name": "تمامی نمادها",
        "endpoint": BrsApiEndpoints.ALL_SYMBOLS,
        "model": SymbolSnapshotModel,
        "parser": TsetmcParser.parse_all_symbols,
        "category": "tsetmc",
        "extra_params": {"type": "1"},
    },
    "index": {
        "name": "شاخص‌ها",
        "endpoint": BrsApiEndpoints.INDEX,
        "model": IndexValueModel,
        "parser": TsetmcParser.parse_index,
        "category": "tsetmc",
        "extra_params": {"type": "1"},
    },
    "option": {
        "name": "آپشن‌ها",
        "endpoint": BrsApiEndpoints.OPTION,
        "model": OptionSnapshotModel,
        "parser": TsetmcParser.parse_options,
        "category": "tsetmc",
    },
    "codal": {
        "name": "اطلاعیه‌های کدال",
        "endpoint": BrsApiEndpoints.CODAL_ANNOUNCEMENT,
        "model": CodalAnnouncementModel,
        "parser": CodalParser.parse_announcements_only,
        "category": "codal",
    },
    "ime_futures": {
        "name": "آتی بورس کالا",
        "endpoint": BrsApiEndpoints.IME_FUTURES,
        "model": ImeFutureModel,
        "parser": ImeParser.parse_futures,
        "category": "ime",
    },
    "ime_options": {
        "name": "اختیار بورس کالا",
        "endpoint": BrsApiEndpoints.IME_OPTION,
        "model": ImeOptionModel,
        "parser": ImeParser.parse_options,
        "category": "ime",
    },
    "ime_certificates": {
        "name": "گواهی سپرده کالایی",
        "endpoint": BrsApiEndpoints.IME_CERTIFICATE,
        "model": ImeCertificateModel,
        "parser": ImeParser.parse_certificates,
        "category": "ime",
    },
    "ime_funds": {
        "name": "صندوق‌های کالایی",
        "endpoint": BrsApiEndpoints.IME_FUND,
        "model": ImeFundModel,
        "parser": ImeParser.parse_funds,
        "category": "ime",
    },
    "ime_physical": {
        "name": "معاملات فیزیکی",
        "endpoint": BrsApiEndpoints.IME_PHYSICAL,
        "model": ImePhysicalTradeModel,
        "parser": ImeParser.parse_physical_trades,
        "category": "ime",
    },
}


# ============================================
#  Helpers
# ============================================

def P(msg):
    print(msg)

def OK(msg):
    P(f"  [OK] {msg}")

def ERR(msg):
    P(f"  [ERR] {msg}")

def INFO(msg):
    P(f"  [..] {msg}")

def HEADER(title):
    P("\n" + "=" * 60)
    P(f"  {title}")
    P("=" * 60)


# ============================================
#  Fetch data from API
# ============================================

def fetch_api(endpoint_path: str, extra_params: dict = None) -> dict | list | None:
    url = f"{BASE_URL}{endpoint_path}"
    params = {"key": API_KEY}
    if extra_params:
        params.update(extra_params)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        ERR(f"HTTP {resp.status_code}")
        return None
    except Exception as e:
        ERR(f"Connection error: {e}")
        return None


# ============================================
#  Save parsed records to database
# ============================================

async def save_records(session: AsyncSession, model_class, records: list[dict]) -> int:
    if not records:
        return 0
    objs = [model_class(**r) for r in records]
    session.add_all(objs)
    await session.flush()
    return len(objs)


# ============================================
#  Sync a single section
# ============================================

async def sync_section(session: AsyncSession, section_id: str, cfg: dict) -> int:
    """
    Fetch from API → Parse → Save to DB.
    Returns number of saved records.
    """
    endpoint = cfg["endpoint"]
    parser = cfg["parser"]
    model_class = cfg["model"]
    extra = cfg.get("extra_params")

    # 1. Fetch
    raw = fetch_api(endpoint.path, extra)
    if raw is None:
        return 0

    # 2. Parse
    try:
        records = parser(raw)
    except Exception as e:
        ERR(f"Parse error: {e}")
        return 0

    if not records:
        INFO("No records parsed")
        return 0

    # 3. Save
    count = await save_records(session, model_class, records)
    await session.commit()
    return count


# ============================================
#  CLI commands
# ============================================

async def cmd_test_connection():
    HEADER("Testing API Connection")
    data = fetch_api(BrsApiEndpoints.COMMODITY.path)
    if data is None:
        ERR("Cannot connect to BrsApi!")
        return

    total = 0
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list):
                total += len(v)
    elif isinstance(data, list):
        total = len(data)

    OK(f"Connected! Received {total} items")


async def cmd_sync_all():
    HEADER("Syncing ALL sections to database")
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        total_saved = 0
        for section_id, cfg in SECTIONS.items():
            P(f"\n  [{section_id}] {cfg['name']} ...")
            try:
                count = await sync_section(session, section_id, cfg)
                total_saved += count
                if count > 0:
                    OK(f"Saved {count} records")
                else:
                    INFO("No data")
            except Exception as e:
                ERR(f"Failed: {e}")
            await asyncio.sleep(2)

    await engine.dispose()
    HEADER(f"DONE - Total saved: {total_saved} records")


async def cmd_sync_section(section_id: str):
    if section_id not in SECTIONS:
        ERR(f"Unknown section: {section_id}")
        P(f"  Available: {', '.join(SECTIONS.keys())}")
        return

    cfg = SECTIONS[section_id]
    HEADER(f"Syncing: {cfg['name']} ({section_id})")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        count = await sync_section(session, section_id, cfg)
        if count > 0:
            OK(f"Saved {count} records to {cfg['model'].__tablename__}")
        else:
            INFO("No data received from API")

    await engine.dispose()


async def cmd_list_sections():
    HEADER("Available BrsApi Sections")
    P("")
    for sid, cfg in SECTIONS.items():
        table = cfg["model"].__tablename__
        P(f"  {sid:<20} | {cfg['name']:<25} | {table}")
    P("")
    P("Usage:")
    P("  python test_brsapi_manual.py --section <id>")
    P("  python test_brsapi_manual.py --all")


# ============================================
#  Main
# ============================================

def main():
    parser = argparse.ArgumentParser(description="BrsApi manual test tool")
    parser.add_argument("--test", action="store_true", help="Test API connection")
    parser.add_argument("--all", action="store_true", help="Sync all sections to DB")
    parser.add_argument("--section", type=str, help="Sync a specific section")
    parser.add_argument("--list", action="store_true", help="List all sections")

    args = parser.parse_args()

    HEADER("BrsApi.ir - Manual Sync Tool")
    P(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    P(f"  Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

    if args.test:
        asyncio.run(cmd_test_connection())
    elif args.all:
        asyncio.run(cmd_sync_all())
    elif args.section:
        asyncio.run(cmd_sync_section(args.section))
    elif args.list:
        asyncio.run(cmd_list_sections())
    else:
        asyncio.run(cmd_test_connection())
        P("\n  Usage:")
        P("    python test_brsapi_manual.py --test          # Test connection")
        P("    python test_brsapi_manual.py --list           # List sections")
        P("    python test_brsapi_manual.py --section crypto # Sync one section")
        P("    python test_brsapi_manual.py --all            # Sync everything")


if __name__ == "__main__":
    main()
