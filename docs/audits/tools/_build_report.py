"""Build the numbered 1000-issue audit catalog.

Sources, in priority order:
  1. _manual_findings.py  -> hand-verified, anchored to real code
  2. _ruff_broad.json     -> tool-verified Python defects (curated rules)
  3. _pattern_findings.json -> regex-verified risky patterns
  4. _eslint.json         -> tool-verified frontend issues

Every emitted row cites a real file:line and quotes the actual source line.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from _manual_findings import F as MANUAL_BATCH1
from _manual_findings2 import F as MANUAL_BATCH2
from _manual_findings3 import F as MANUAL_BATCH3
from _manual_findings4 import F as MANUAL_BATCH4
from _manual_findings5 import F as MANUAL_BATCH5
from _manual_findings6 import F as MANUAL_BATCH6
from _manual_findings7 import F as MANUAL_BATCH7
from _manual_findings8 import F as MANUAL_BATCH8
from _manual_findings9 import F as MANUAL_BATCH9

MANUAL = (MANUAL_BATCH1 + MANUAL_BATCH2 + MANUAL_BATCH3 + MANUAL_BATCH4
          + MANUAL_BATCH5 + MANUAL_BATCH6 + MANUAL_BATCH7 + MANUAL_BATCH8
          + MANUAL_BATCH9)

MAX_ITEMS = 1000
BASE = Path(__file__).resolve().parent  # tooling + cached scan outputs live here

CAT_ORDER = ["DEP", "DATA", "SCH", "DB", "CACHE", "API", "FE", "PROC", "SEC", "OBS"]

CLAIM_VERIFY = [
    ("DATA-013 (محدودیت ۵ نماد)", "رد شد", "`ingestion/worker.py:58`", "هیچ برش `[:5]` وجود ندارد؛ حلقه روی همه نمادهاست. مشکل واقعی برعکس است: هر tick همه نمادها فراخوانی می‌شوند."),
    ("DATA-014 (کش نمادها تازه نمی‌شود)", "تأیید شد", "`ingestion/sources/tsetmc.py:47`", "تا وقتی `_instruments` پر باشد همان فهرست برگردانده می‌شود؛ refresh ساعتی worker بی‌اثر است."),
    ("DATA-015 (dedup قبل از ذخیره)", "رد شد", "`ingestion/worker.py:154`", "`mark_seen` اکنون بعد از `_write_event` موفق صدا زده می‌شود."),
    ("DATA-016 (retry خطاهای aiohttp)", "تأیید شد", "`ingestion/retry.py:23-27`", "فقط TimeoutError/ConnectionError/ConnectionResetError؛ ClientConnectorError پوشش ندارد."),
    ("DATA-017 (نادیده گرفتن market_timezone)", "تأیید شد", "`ingestion/scheduler.py:56`", "افست +۳:۳۰ هاردکد شده و تنظیمات خوانده نمی‌شود."),
    ("DATA-018 (زمان fetch در parser)", "تأیید شد", "`ingestion/parser/tsetmc_parsers.py:25,71,113` و `worker.py:127`", "زمان parse جای زمان fetch می‌نشیند."),
    ("DATA-019 (یک رکورد خراب، کل payload)", "تأیید شد", "`ingestion/worker.py:127` + `tsetmc_parsers.py:52`", "`int()` روی مقدار خام است و try دور کل parse است."),
    ("DATA-020 (None شدن مقدار خراب)", "تأیید شد", "`ingestion/parser/tsetmc_parsers.py:163`", "`_to_decimal` هر استثنا را می‌بلعد."),
    ("DATA-021 (تاریخچه به‌عنوان trade_tick)", "منقضی شد", "`ingestion/parser/tsetmc_parsers.py:78`", "اکنون `event_type=\"daily_ohlcv\"` است؛ ادعای قبلی با کد امروز نمی‌خواند."),
    ("DATA-022 (نبود کلید یکتا در trade_ticks)", "تأیید ساختاری", "`ingestion/db/models.py:38-50`", "درست است، اما مسیر فعلی parser چیزی در این جدول نمی‌نویسد؛ اثر عملی محدود است."),
    ("DATA-023 (append شدن snapshotها)", "تأیید شد", "`ingestion/storage/__init__.py:32`", "`INSERT` بدون upsert برای هر poll."),
    ("DATA-024 (به‌روز نشدن fetched_at در upsert)", "تأیید شد", "`ingestion/storage/__init__.py:74-82`", "فهرست SET شامل fetched_at نیست."),
    ("DATA-025 (تکرار orderbook)", "تأیید شد", "`ingestion/storage/__init__.py:55`", "هر سطح با INSERT ساده و بدون snapshot_id ثبت می‌شود."),
    ("DATA-026 (جدا بودن مسیر ingestion از heatmap)", "تأیید شد", "`ingestion/storage/__init__.py` در برابر `apps/api/endpoints/market.py:261`", "storage در جدول‌های ingestion می‌نویسد؛ heatmap از جدول‌های BrsApi می‌خواند."),
]

CAT_TITLE = {
    "DEP": "استقرار، Docker و اتصال سرویس‌ها",
    "DATA": "منبع داده، دریافت و همگام‌سازی",
    "SCH": "زمان‌بند و اجرای وظایف",
    "DB": "پایگاه داده، مدل و کوئری",
    "CACHE": "کش و تازگی داده",
    "API": "بک‌اند و API",
    "FE": "فرانت‌اند و نمایش",
    "PROC": "پردازش، پارسر و یکپارچگی داده",
    "SEC": "امنیت و پیکربندی",
    "OBS": "پایش، آزمون و پیکربندی محیط",
}

SEV_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

_LCACHE: dict[str, list[str]] = {}


def lines_of(path: str) -> list[str]:
    if path not in _LCACHE:
        try:
            _LCACHE[path] = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            _LCACHE[path] = []
    return _LCACHE[path]


def snippet(path: str, line: int) -> str:
    ls = lines_of(path)
    if 1 <= line <= len(ls):
        return ls[line - 1].strip()[:220]
    return ""


def norm(path: str) -> str:
    return path.replace("\\", "/").split("/temce/")[-1].lstrip("./")


def category_for(path: str, default: str = "PROC") -> str:
    p = path.lower()
    if p.startswith("docker") or "dockerfile" in p or p.startswith("deploy/") or p.startswith("k8s/"):
        return "DEP"
    if p.startswith("frontend/"):
        return "FE"
    if p.startswith("brsapi/services/query") or p.startswith("brsapi/models") or p.startswith("repositories/"):
        return "DB"
    if p.startswith("brsapi/") or p.startswith("ingestion/"):
        return "DATA"
    if p.startswith("jobs/") or p.startswith("apps/scheduler"):
        return "SCH"
    if p.startswith("apps/api/") or p.startswith("api/"):
        return "API"
    if p.startswith("core/config") or p.startswith("monitoring/") or p.startswith("integrations/"):
        return "OBS"
    return default


CLAIM_VERIFY2 = [
    ("DATA-027 (پاسخ خالی = موفقیت بدون commit)", "تأیید شد", "`brsapi/services/sync_service.py:388-403`", "شاخهٔ `is_empty` هم `status=success` می‌نویسد و هم بدون commit برمی‌گردد."),
    ("DATA-028 (خروجی نامعتبر پارسر)", "تأیید شد", "`brsapi/services/sync_service.py:429-445`", "نوع غیر list/dict به `records=[]` تبدیل و «موفق با صفر رکورد» ثبت می‌شود."),
    ("DATA-029 (rollback گستردهٔ سه بخش)", "تأیید شد", "`brsapi/services/sync_service.py:1352` + `:1382`", "rollback در خطا + commit نهایی روی همان session؛ تغییرات بخش‌های قبلی هم از دست می‌رود."),
    ("DATA-030 (truncate قبل از اعتبارسنجی)", "تأیید با جابه‌جایی محل", "`brsapi/services/sync_service.py:1468`", "مسیر Gold_Currency عادی اکنون upsert است، اما مسیر Gold_Currency_Pro هنوز `truncate()` سپس insert می‌کند."),
    ("DATA-031 (sparkline با success=true)", "منقضی شد", "`apps/api/endpoints/market.py:239`", "اکنون `success=result.success` است؛ ادعای قبلی با کد امروز نمی‌خواند."),
    ("DATA-032 (شاخص بر اساس created_at)", "تأیید شد", "`brsapi/services/query_service.py:385`", "MAX(created_at) معیار انتخاب است، نه fetched_at."),
    ("DATA-033 (NAV بر اساس created_at)", "تأیید شد", "`brsapi/services/query_service.py:430`", "مرتب‌سازی با created_at و limit 1؛ تاریخ NAV نقشی ندارد."),
    ("DATA-034 (همهٔ snapshotهای اختیار)", "تأیید شد", "`brsapi/services/query_service.py:437-444`", "فقط فیلتر underlying_symbol و مرتب‌سازی date_end."),
    ("DATA-035 (سهام‌داران بر اساس درصد)", "تأیید شد", "`brsapi/services/query_service.py:765`", "`percent DESC LIMIT 50` بدون انتخاب آخرین snapshot."),
    ("DATA-036 (معاملات درون‌روزی بدون فیلتر روز)", "تأیید شد", "`brsapi/services/query_service.py:786`", "مرتب‌سازی با created_at و بدون شرط trade_date."),
    ("DATA-037 (کالاها: کل تاریخچه)", "تأیید شد", "`brsapi/services/query_service.py:542` و `apps/api/endpoints/brsapi.py:70`", "`latest_only` وجود دارد اما پیش‌فرض False است و چند فراخوان آن را ست نمی‌کنند."),
    ("DATA-038 (رمزارز بدون آخرین رکورد)", "تأیید شد", "`brsapi/services/query_service.py:713-720`", "مرتب‌سازی با rank و limit؛ هر symbol می‌تواند چند بار بیاید."),
    ("DATA-039 (IME: کل تاریخچه)", "تأیید نسبی", "`brsapi/services/query_service.py:601-624`", "کوئری‌ها همهٔ ردیف‌ها را می‌خوانند؛ تکرار واقعی به dedup سمت sync بستگی دارد."),
    ("DATA-040 (fallback غیرقابل وقوع)", "تأیید شد", "`brsapi/services/query_service.py:100-109` و `:304` + `brsapi/models/tsetmc.py:49`", "شرط `ins_id IS NULL` با nullable=False هرگز برقرار نمی‌شود؛ هم fallback پایتونی و هم JOIN SQL بی‌اثرند."),
]


CLAIM_VERIFY3 = [
    ("DATA-041 (heatmap: سقف ۱۰۰)", "تأیید شد", "`apps/api/endpoints/market.py:120`", "`get_latest_snapshots(limit=100)` ثابت است و پارامتری ندارد."),
    ("DATA-042 (heatmap غنی: سقف ۵۰۰)", "تأیید شد", "`apps/api/endpoints/market.py:261`", "بدون صفحه‌بندی و بدون total."),
    ("DATA-043 (آمار کل بازار از ۵۰۰)", "تأیید شد", "`services/market_service.py:35-53`", "`total = len(snapshots)` روی همان ۵۰۰ ردیف."),
    ("DATA-044 (خلاصه صنایع: ۲۰۰ و avg=0)", "تأیید شد", "`services/market_service.py:109` و `:133`", "سقف ۲۰۰ و `sec[\"avg_change\"] = 0`."),
    ("DATA-045 (ترتیب sparkline)", "تأیید شد", "`services/market_service.py:778-787`", "`ORDER BY symbol, date DESC` و بدون reverse."),
    ("DATA-046 (sparkline با success=true)", "رد شد", "`apps/api/endpoints/market.py:239`", "کد فعلی `success=result.success` است؛ این ادعا با DATA-031 تکراری و منقضی است."),
    ("DATA-047 (فیلتر تاریخ بعد از limit)", "تأیید شد", "`services/market_service.py:217`", "ابتدا limit=500 سپس فیلتر Python."),
    ("DATA-048 (تاریخ محلی و limit*3)", "تأیید شد", "`services/market_service.py:325-326`", "`date.today()` بدون timezone و بازه تقویمی."),
    ("DATA-049 (MACD fast>slow)", "تأیید شد", "`services/market_service.py:503`", "`offset = slow - fast` بدون اعتبارسنجی رابطه."),
    ("DATA-050 (Ichimoku ناهم‌تراز)", "تأیید شد", "`services/market_service.py:668-671`", "senkou_b بدون شیفت و chikou با برش ساده."),
    ("DATA-051 (Stochastic K/D)", "تأیید شد", "`services/market_service.py:561-562`", "D از SMA روی K ساخته می‌شود (کوتاه‌تر)؛ تاریخ با طول K هم‌تراز می‌شود."),
    ("DATA-052 (close=price_last)", "تأیید شد", "`services/market_service.py:285`", "`price_close` در `_to_ohlcv` استفاده نمی‌شود."),
    ("DATA-053 (نام فیلد صنعت)", "تأیید شد", "`services/market_service.py:125`", "مدل `sector` می‌دهد، کد `sector_name`/`industry` می‌خواند → همه در «سایر»."),
    ("DATA-054 (macro موفق بدون data)", "تأیید شد", "`services/market_service.py:907`", "`Result.ok({indicator, country})` بدون کلید data."),
]


CLAIM_VERIFY4 = [
    ("DATA-055 (Promise.all در کارت‌ها)", "رد شد", "`frontend/src/hooks/useMarketData.ts:430`", "کد فعلی `Promise.allSettled` است؛ اما خطای هر منبع بی‌صدا حذف می‌شود و isError نمی‌شود — مشکل باقی است، با مکانیزم متفاوت."),
    ("DATA-056 (بازار جهانی → [])", "تأیید نسبی", "`frontend/src/hooks/useMarketData.ts:501-521`", "دیگر catch خالی نیست؛ allSettled خطا را می‌بلعد و isError=false می‌ماند."),
    ("DATA-057 (rangeIdx بی‌استفاده)", "رد شد", "`frontend/src/hooks/useMarketData.ts:536-545`", "rangeIdx به limitMap نگاشت و در URL استفاده می‌شود."),
    ("DATA-058 (treemap: خطا = خالی)", "تأیید نسبی", "`frontend/src/hooks/useMarketData.ts:571-583`", "isError برگردانده می‌شود، اما از heuristic «طول صفر» ساخته می‌شود؛ empty و error قاطی می‌شوند."),
    ("DATA-059 (جریان حقیقی/حقوقی)", "تأیید شد", "`frontend/src/hooks/useMarketData.ts:613-617`", "success:false → warn → [] (بدون حالت خطا در hook)."),
    ("DATA-060 (خلاصه جریان)", "تأیید نسبی", "`frontend/src/hooks/useMarketData.ts:638-648`", "isError/isLoading برگردانده می‌شوند، اما catch خالی و null دوحالته است."),
    ("DATA-061 (تقویم اقتصادی)", "تأیید شد", "`frontend/src/hooks/useMarketData.ts:679-684`", "success:false → warn → []؛ خطا از «بدون رویداد» تفکیک نمی‌شود."),
    ("DATA-062 (sparkline با success=true)", "رد شد", "`apps/api/endpoints/market.py:239`", "سومین بار همین ادعا؛ کد فعلی `success=result.success` است."),
    ("DATA-063 (MAX(id) برای آخرین snapshot)", "تأیید شد", "`brsapi/services/query_service.py:111`", "مکان ادعا (۱۴۰-۱۶۶) جابه‌جا شده، محتوا درست است."),
    ("DATA-064 (limit قبل از join)", "تأیید شد", "`brsapi/services/query_service.py:123-128`", "limit روی زیرکوئری نمادها اعمال و سپس join انجام می‌شود."),
    ("DATA-065 (ابهام symbol/ins_id)", "تأیید نسبی", "`brsapi/services/query_service.py:312`", "یک پارامتر symbol روی دو ستون symbol و ins_id مقایسه می‌شود."),
    ("DATA-066 (ترتیب تاریخچه شاخص)", "تأیید شد", "`brsapi/services/query_service.py:407` + `apps/api/endpoints/market.py:473`", "DESC در سرویس و reverse در endpoint."),
    ("DATA-067 (جریان بازار روی ۵۰۰)", "تأیید شد", "`apps/api/endpoints/market.py:364-365`", "limit پیش‌فرض ۵۰۰ و تجمیع روی همان نمونه."),
    ("DATA-068 (isLive کارت‌ها)", "تأیید شد", "`frontend/src/hooks/useMarketData.ts:470`", "`isLive: rows.length > 0` بدون بررسی سن داده."),
]


CLAIM_VERIFY5 = [
    ("DATA-069 (baseUrl=localhost)", "تأیید شد", "`frontend/src/hooks/useApiMonitor.ts:10`", "پیش‌فرض `http://localhost:8000` است."),
    ("DATA-070 (آنلاین = HTTP 200)", "تأیید شد", "`frontend/src/hooks/useApiMonitor.ts:26-33`", "بدنهٔ /health بررسی نمی‌شود؛ liveness با readiness قاطی می‌شود."),
    ("DATA-071 (subscription با تغییر نمادها)", "تأیید شد", "`frontend/src/hooks/useWebSocket.ts:128-133` و effect با deps=[]", "subscribe فقط در onopen ارسال می‌شود."),
    ("DATA-072 (Date.now جای timestamp منبع)", "تأیید شد", "`frontend/src/hooks/useWebSocket.ts:137`", "هر پیام timestamp مرورگر می‌گیرد."),
    ("DATA-073 (پیام نامعتبر بی‌صدا)", "تأیید شد", "`frontend/src/hooks/useWebSocket.ts:141`", "catch خالی با کامنت Ignore."),
    ("DATA-074 (خطای polling backfill)", "تأیید شد", "`frontend/src/hooks/useBackgroundBackfill.ts:63-74`", "catch → undefined بدون state خطا."),
    ("DATA-075 (running بدون تأیید)", "تأیید شد", "`frontend/src/hooks/useBackgroundBackfill.ts:95`", "state پیش از بررسی started تنظیم می‌شود."),
    ("DATA-076 (خطای شروع backfill)", "تأیید شد", "`frontend/src/hooks/useBackgroundBackfill.ts:96-103`", "catch → undefined."),
    ("DATA-077 (لغو بدون تأیید)", "تأیید شد", "`frontend/src/hooks/useBackgroundBackfill.ts:106-113`", "نتیجهٔ لغو و وضعیت سرور بازخوانی نمی‌شود."),
    ("DATA-078 (ناسازگاری ready/full)", "تأیید شد", "`apps/api/endpoints/health.py:109`", "فقط `db_status != ok` مقدار overall را تغییر می‌دهد."),
    ("DATA-079 (null_check≠null)", "تأیید شد", "`apps/api/endpoints/monitoring.py:45`", "`null_check` همان `staleness < 300` است."),
    ("DATA-080 (dead-letter صفر کاذب)", "تأیید شد", "`apps/api/endpoints/ingestion.py:62-64`", "`dl_len=0` با suppress و success=True."),
    ("DATA-081 (SQLite جدا در quotes)", "تأیید شد", "`apps/api/endpoints/quotes.py:192-196`", "engine جدید در هر درخواست و بدون dispose."),
    ("DATA-082 (افشای str(exc))", "تأیید شد", "`apps/api/endpoints/symbols.py:165`", "`Server error: {exc}` در پاسخ JSON."),
]


CLAIM_VERIFY6 = [
    ("DATA-083 (save_quotes شکست جزئی)", "تأیید شد", "`services/quote_service.py:132-137`", "فقط موفق‌ها شمرده و همیشه `Result.ok(count)` برمی‌گردد."),
    ("DATA-084 (ingest_historical پیاده‌سازی نشده)", "تأیید شد (بدون call-site)", "`services/quote_service.py:87-95`", "در این نسخه هیچ فراخواننده‌ای ندارد؛ اثر عملی فعلی کم است."),
    ("DATA-085 (صفر برای فیلد غایب)", "تأیید شد", "`services/quote_service.py:59-70`", "`float(data.get(..., 0))` برای قیمت/حجم/ارزش."),
    ("DATA-086 (فیلتر اخبار بعد از صفحه‌بندی)", "رد شد", "`apps/api/endpoints/news.py:179-181`", "دسته قبل از `list_all` نرمال و به سرویس پاس می‌شود؛ total هم فیلترشده است."),
    ("DATA-087 (ناهمگونی fallback اخبار)", "رد شد", "`apps/api/endpoints/news.py:208-210`", "fallback هم از `canonical_category` استفاده می‌کند."),
    ("DATA-088 (اسکن بدون warm sink)", "تأیید شد", "`ingestion/market_scan_service.py:55-57`", "بدون session_factory  مقدار `_warm_sink` برابر None می‌شود و فقط hot می‌ماند."),
    ("DATA-089 (scan_once بی‌صدا None)", "تأیید شد", "`ingestion/market_scan_service.py:128-130`", "شکست/خالی بدون لاگ علت برمی‌گردد."),
    ("DATA-090 (ارز: fallback با timestamp تازه)", "تأیید شد", "`apps/currency_service/infra/collectors.py:117-119`", "fixture + jitter ±۰٫۳٪ و `datetime.now(UTC)`."),
    ("DATA-091 (خطای ارز فقط در log)", "تأیید شد", "`apps/currency_service/infra/collectors.py:71-73` و `:96-98`", "هر دو collector استثنا را می‌بلعند و None برمی‌گردانند."),
]


CLAIM_VERIFY7 = [
    ("DATA-092 (QuoteIngestionJob همیشه موفق)", "تأیید شد", "`jobs/definitions/market_data_jobs.py:22`", "فقط موفق‌ها شمرده می‌شوند؛ `success_result` بی‌قید."),
    ("DATA-093 (HistoricalDataJob همیشه موفق)", "تأیید شد", "`jobs/definitions/market_data_jobs.py:35`", "با DATA-084 ترکیب می‌شود: تابع همیشه fail است ولی job همیشه سبز."),
    ("DATA-094 (RealtimeQuoteJob)", "تأیید شد", "`jobs/definitions/market_data_jobs.py:47`", "تعداد موفق گزارش می‌شود، وضعیت نه."),
    ("DATA-095 (SyncQuotesJob بدون بررسی گزارش)", "تأیید شد", "`jobs/definitions/sync_jobs.py:117-134`", "`success/error` هر دو report نادیده گرفته می‌شود."),
    ("DATA-096 (ack در finally)", "تأیید شد", "`jobs/queue_consumer.py:158-164`", "`finally: await self._ack_message(...)`."),
    ("DATA-097 (fallback BRPOP بدون processing)", "تأیید شد", "`jobs/queue_consumer.py:188-198`", "پیام در مسیر BRPOP به processing نمی‌رود."),
    ("DATA-098 (شکست requeue + ack)", "تأیید شد", "`jobs/queue_consumer.py:295-299` + `:160-164`", "خطای lpush به finally می‌رسد و ack انجام می‌شود."),
    ("DATA-099 (is_available سطحی)", "تأیید شد", "`jobs/queue_publisher.py:79-81` و `jobs/queue_consumer.py:100-102`", "فقط None نبودن client."),
    ("DATA-100 (stubهای legacy)", "تأیید شد", "`jobs/definitions/sync_jobs.py:192-206`", "سه تابع `completed` با count=0."),
]


CLAIM_VERIFY8 = [
    ("DATA-101 (فقدان fallback برای jobهای BrsApi)", "تأیید شد", "`brsapi/jobs/registry.py:504-506` + `apps/scheduler/app.py:69`", "`publish()` در `_run_handler` بدون بررسی نتیجه صدا زده می‌شود."),
    ("DATA-102 (worker بدون Redis برای همیشه idle)", "تأیید شد", "`apps/worker/consumer.py:30-35` + `core/cache.py:108-110`", "شکست `initialize()` مقدار `_redis` را None نگه می‌دارد و هیچ retry دوره‌ای نیست."),
    ("DATA-103 (پیام با token نامعتبر حذف می‌شود)", "تأیید شد", "`jobs/queue_consumer.py:234-240` + `:165-166`", "`return` بدون `_dead_letter` و سپس ack در `finally`."),
    ("DATA-104 (پیام خراب بدون dead-letter)", "تأیید شد", "`jobs/queue_consumer.py:227-231`", "فقط log و شمارنده؛ مسیر `_dead_letter` فراخوانی نمی‌شود."),
    ("DATA-105 (سلامت سطحی صف)", "تأیید شد", "`jobs/queue_consumer.py:104-105` و `jobs/queue_publisher.py:79-81`", "هر دو فقط `self._redis() is not None` را می‌سنجند؛ همین شرط شروع worker را کنترل می‌کند."),
    ("DATA-106 (Redis بدون healthcheck در compose)", "تأیید شد", "`docker-compose.yml:25-32` + `:44-45`", "سرویس redis هیچ healthcheck ندارد و depends_on فقط `service_started` است."),
]


CLAIM_VERIFY10 = [
    ("DATA-151 (سهام‌داران از کل تاریخ)", "تأیید شد — از قبل `DB-009`", "`brsapi/services/query_service.py:766`", "`percent DESC LIMIT 50` بدون انتخاب آخرین تاریخ گزارش."),
    ("DATA-152 (معاملات درون‌روزی تکراری/قدیمی)", "تأیید شد — از قبل `DB-010`", "`brsapi/services/query_service.py:788`", "مرتب‌سازی با `created_at`، بدون فیلتر `trade_date` و بدون کلید یکتا."),
    ("DATA-153 (پاسخ ناقص داده قبلی را حذف می‌کند)", "منقضی در محل ذکرشده", "`brsapi/services/sync_service.py:1328`", "مسیر Gold_Currency عادی اکنون upsert است؛ ادعا به محل قدیمی اشاره دارد."),
    ("DATA-154 (ثبت موفقیت برای پاسخ خالی)", "تأیید شد — از قبل `DATA-041`", "`brsapi/services/sync_service.py:388-408` + `repositories/base.py:82-83`", "`record()` فقط flush می‌کند و شاخهٔ خالی commit ندارد."),
    ("DATA-155 (sparkline همیشه success=True)", "رد شد — سومین تکرار", "`apps/api/endpoints/market.py:239`", "کد فعلی `success=result.success` است (قبلاً `DATA-031/046/062`)."),
    ("DATA-156 (آخرین شاخص با created_at)", "تأیید شد — از قبل `DB-006`", "`brsapi/services/query_service.py:385`", "مدل `fetched_at` دارد ولی query از `MAX(created_at)` می‌آید."),
    ("DATA-157 (truncate قبل از اعتبارسنجی)", "منقضی در محل ذکرشده", "`brsapi/services/sync_service.py:1468` → پیش‌تر `DATA-044`", "truncate در مسیر Pro بخش‌به‌بخش هنوز هست؛ الگوی کلی در `:465` باقی است."),
    ("DATA-158 (قیمت جاری کالا با تاریخچه)", "تأیید شد — از قبل `DB-011`", "`brsapi/services/query_service.py:644`", "`latest_only` پیش‌فرض False و `market_dashboard` آن را نمی‌دهد."),
    ("DATA-159 (چند نسخه از یک رمزارز)", "تأیید شد — از قبل `DB-012`", "`brsapi/services/query_service.py:713-720`", "بدون dedup و بدون on_conflict؛ هر sync ردیف تازه می‌سازد."),
    ("DATA-160 (تکرار قراردادهای بورس کالا)", "تأیید شد — از قبل `DB-013`", "`brsapi/services/query_service.py:601-623`", "همهٔ ردیف‌ها بدون انتخاب آخرین نسخه برمی‌گردند."),
    ("DATA-161 (fallback اتصال نماد)", "تأیید شد — از قبل `DB-014`", "`brsapi/services/query_service.py:304`", "`ins_id` در snapshot `nullable=False` است، پس شرط `IS NULL` هرگز برقرار نمی‌شود."),
    ("DATA-162 (heatmap فقط ۵۰۰ نماد)", "تأیید شد — از قبل `API-006`", "`apps/api/endpoints/market.py:261`", "`limit=500` ثابت و کش هم با کلید `enriched-heatmap:500`."),
]


CLAIM_VERIFY11 = [
    ("DATA-168 (heatmap فقط ۱۰۰ نماد)", "تکراری — `API-005`", "`apps/api/endpoints/market.py:120`", "همان سقف ثابت ۱۰۰ و بدون پارامتر limit."),
    ("DATA-169 (خلاصه صنایع: ۲۰۰ و avg=0)", "تکراری — `API-009` + `DATA-044`", "`services/market_service.py:109,135`", "سقف ۲۰۰ و `sec[\"avg_change\"] = 0`."),
    ("DATA-170 (MACD fast>slow)", "تکراری — `API-014`", "`services/market_service.py:501`", "`offset = slow - fast` بدون اعتبارسنجی رابطه‌ای."),
    ("DATA-171 (Ichimoku ناهم‌تراز)", "تکراری — `API-015`", "`services/market_service.py:668-671`", "senkou/chikou بدون شیفت و با طول‌های متفاوت."),
    ("DATA-172 (Stochastic K/D)", "تکراری — `API-016`", "`services/market_service.py:562`", "D از SMA روی K ساخته می‌شود و کوتاه‌تر است."),
    ("DATA-173 (فیلد صنعت)", "تکراری — `API-010`", "`services/market_service.py:125`", "مدل `sector` می‌دهد، کد `sector_name`/`industry` می‌خواند."),
    ("DATA-174 (macro بدون کلید data)", "تکراری — `API-018`", "`services/market_service.py:907`", "`Result.ok` بدون data و با success."),
    ("DATA-175 (isLive از وجود ردیف)", "تکراری — `FE-006`", "`useMarketData.ts:281, 313` (نه ۴۲۳-۴۷۰)", "هر دو hook مقدار را از طول آرایه می‌سازند."),
    ("DATA-176 (fixture ارز با زمان تازه)", "تکراری — `DATA-090`", "`apps/currency_service/infra/collectors.py:112-115`", "`or fixture.free` سپس `timestamp=datetime.now(UTC)`."),
    ("DATA-177 (خطای ارز بلعیده می‌شود)", "تکراری — `DATA-091`", "`collectors.py:72,97`", "هر دو collector فقط warning و None برمی‌گردانند."),
    ("DATA-178 (تاریخچه پیاده‌سازی نشده)", "تکراری — `DATA-084`", "`services/quote_service.py:94-96`", "`Historical ingestion not implemented yet` و بدون call-site."),
    ("DATA-179 (صفر برای فیلد غایب)", "تکراری — `DATA-085`", "`services/quote_service.py:59-70`", "الگوی `data.get(..., 0)` برای قیمت و حجم."),
    ("DATA-180 (SyncQuotesJob همیشه موفق)", "تکراری — `DATA-095`", "`jobs/definitions/sync_jobs.py:109-130`", "`success/error` هر دو report نادیده گرفته می‌شود."),
    ("DATA-181 (RealtimeQuoteJob)", "تکراری — `SCH-012`", "`jobs/definitions/market_data_jobs.py:47`", "فقط موفق‌ها شمرده می‌شوند و `success_result` بی‌قید برمی‌گردد."),
    ("DATA-182 (stubهای legacy)", "تکراری — `SCH-019`", "`jobs/definitions/sync_jobs.py:192-206`", "سه تابع `completed` با count=0."),
    ("DATA-183 (سلامت سطحی Redis)", "تکراری — `SCH-018`/`SCH-024`", "`jobs/queue_publisher.py:80` + `jobs/queue_consumer.py:105`", "فقط None نبودن client."),
    ("DATA-184 (فقدان پیام در retry)", "تکراری — `SCH-016`/`DATA-098`", "`jobs/queue_consumer.py:165-166, 286-303`", "خطای lpush به `finally` می‌رسد و ack انجام می‌شود."),
]


ROOT_VERIFY = [
    ("ROOT-001 (backend کانتینر API نیست)", "تأیید شد (با تصحیح خط)", "`docker-compose.yml:36-39` + `Dockerfile:41` → پیش‌تر `DEP-001`", "ادعا درست است؛ فقط شمارهٔ خط `Dockerfile:14` اشتباه است (فرمان در خط ۴۱ است)."),
    ("ROOT-002 (DSN مناسب کانتینر ندارد)", "تأیید و تشدید شد", "میزبان: `DATA-012` — پیشوند و scheme: `DEP-021` و `DEP-022`", "سه مانع مستقل: پیشوند `INGESTION_`، میزبان `localhost:5433`، و scheme ای که asyncpg رد می‌کند."),
    ("ROOT-003 (فرمان worker بدون entry point)", "تأیید شد (پیش‌تر ثبت)", "`Dockerfile.worker:56` → `DEP-020`", "خودمان اجرا کردیم: `python -m apps.worker.app` با کد ۰ و بی‌خروجی برمی‌گردد."),
    ("ROOT-004 (registry در worker پر نمی‌شود)", "تأیید شد (پیش‌تر ثبت)", "`apps/worker/app.py:32` → `SCH-025` / `SCH-026`", "در فرآیند تازه `list_names()` صفر است؛ پس از ثبت ۶۶ job باز هم `brsapi_all_symbols` پیدا نمی‌شود."),
    ("ROOT-005 (Dockerfile فرانت‌اند غایب)", "تأیید شد (با قید)", "`docker-compose.yml:117-121` → پیش‌تر `DEP-004`", "در حالت پایه درست است؛ اگر override اعمال شود `Dockerfile.dev` موجود است، ولی خود override نامعتبر است."),
    ("override نامعتبر (نه ادعای ROOT، ولی در همان زنجیره)", "تأیید شد (پیش‌تر ثبت)", "`docker-compose.override.yml:6` → پیش‌تر `DEP-005`", "اجرای واقعی `docker compose config` شکست می‌خورد: سرویس‌های `api`/`admin`/`postgres`/`scheduler` image یا build ندارند."),
]


# ── ruff rule metadata: rule -> (severity, title, effect, fix)
RUFF_META = {
    "F821": ("P0", "نام تعریف‌نشده در کد (NameError در زمان اجرا)", "مسیر اجرا با خطای NameError متوقف می‌شود", "تعریف/ایمپورت متغیر"),
    "F841": ("P2", "متغیر محلی تخصیص‌یافته اما بی‌استفاده", "نشانه منطق نیمه‌کاره یا محاسبه دورریخته", "حذف یا استفاده صحیح"),
    "F401": ("P3", "ایمپورت بی‌استفاده", "وابستگی پنهان و بار اضافی import", "حذف ایمپورت"),
    "S110": ("P1", "try/except/pass — خطا کاملاً بلعیده می‌شود", "شکست بی‌صدا؛ علت اصلی داده قدیمی پنهان می‌ماند", "لاگ + بازگرداندن خطا یا شمارش"),
    "S112": ("P1", "try/except/continue — خطا نادیده گرفته می‌شود", "ردیف معیوب بی‌صدا حذف می‌شود", "ثبت خطا و متریک"),
    "S314": ("P2", "پارس XML با پیکربندی ناامن", "ریسک XXE", "defusedxml"),
    "ASYNC240": ("P1", "فراخوانی مسدودکننده فایل در تابع async", "event loop بلاک و زمان‌بندی وظایف مختل می‌شود", "asyncio.to_thread"),
    "ASYNC230": ("P1", "open مسدودکننده در تابع async", "event loop بلاک می‌شود", "to_thread / aiofiles"),
    "ASYNC110": ("P1", "حلقه انتظار فعال (busy wait) در async", "مصرف CPU و تأخیر سایر وظایف", "asyncio.Event"),
    "RUF006": ("P1", "نتیجه asyncio.create_task ذخیره نمی‌شود", "تسک ممکن است توسط GC حذف و وظیفه بی‌صدا متوقف شود", "نگه‌داشتن رفرنس تا اتمام"),
    "B006": ("P2", "آرگومان پیش‌فرض تغییرپذیر", "حالت بین فراخوانی‌ها نشت می‌کند", "None + مقدارپیش‌فرض داخل تابع"),
    "B023": ("P2", "استفاده از متغیر حلقه در closure", "همه closureها مقدار آخر را می‌بینند", "پارامتر پیش‌فرض"),
    "B905": ("P3", "zip بدون strict", "طول‌های ناهمگون بی‌صدا بریده می‌شوند", "strict=True"),
    "PLW0603": ("P3", "استفاده از global", "وضعیت مشترک و غیرقابل تست", "کپسوله‌سازی در کلاس/DI"),
    "PLW0602": ("P3", "global بدون تخصیص", "کد مرده/گیج‌کننده", "حذف"),
    "RUF012": ("P3", "ویژگی کلاس تغییرپذیر بدون ClassVar", "اشتراک ناخواسته بین نمونه‌ها", "ClassVar / field"),
    "RUF059": ("P3", "متغیر unpack‌شده بی‌استفاده", "نویز", "حذف"),
    "RUF021": ("P3", "ترتیب عملگرهای and/or مبهم", "منطق شرط ممکن است اشتباه خوانده شود", "پرانتز"),
    "RUF005": ("P3", "الحاق لیست به‌جای unpack", "کارایی", "unpack"),
    "RUF007": ("P3", "zip به‌جای pairwise", "خوانایی", "itertools.pairwise"),
    "RUF019": ("P3", "بررسی کلید و دسترسی تکراری در dict", "کارایی", "dict.get"),
    "RUF046": ("P3", "int() روی مقدار از پیش عددی", "نویز", "حذف"),
    "RUF034": ("P3", "شرط if/else بی‌اثر", "منطق تکراری", "ساده‌سازی"),
    "RET505": ("P3", "else پس از return", "خوانایی", "حذف else"),
    "RET504": ("P3", "تخصیص بی‌استفاده پیش از return", "خوانایی", "return مستقیم"),
    "SIM103": ("P3", "بازگشت شرط به‌جای if/return", "خوانایی", "ساده‌سازی"),
    "SIM105": ("P3", "try/except/pass قابل تبدیل به contextlib.suppress", "خوانایی", "contextlib.suppress"),
    "SIM108": ("P3", "if/else قابل تبدیل به عبارت شرطی", "خوانایی", "عبارت شرطی"),
    "E701": ("P3", "چند دستور در یک خط", "خوانایی و پوشش تست", "شکستن خط"),
    "E702": ("P3", "چند دستور با semicolon", "خوانایی", "شکستن خط"),
    "E741": ("P3", "نام متغیر مبهم (l/O/I)", "خوانایی", "نام واضح"),
    "I001": ("P3", "ایمپورت‌ها مرتب نیستند", "نویز diff", "ruff --fix"),
    "N801": ("P3", "نام کلاس با قاعده سازگار نیست", "خوانایی", "تغییر نام"),
    "UP042": ("P3", "استفاده از StrEnum به‌جای str+Enum", "سازگاری نسخه", "StrEnum"),
    "W293": ("P3", "خط خالی دارای فضای سفید", "نویز", "حذف فاصله"),
    "RUF022": ("P3", "ترتیب __all__", "نویز", "مرتب‌سازی"),
    "RUF100": ("P3", "noqa بی‌مورد", "پنهان‌سازی بی‌دلیل", "حذف noqa"),
    "PLW2901": ("P3", "بازنویسی متغیر حلقه", "گیج‌کننده", "متغیر جدید"),
    "PLW0127": ("P3", "خودتخصیصی", "کد مرده", "حذف"),
    "PLW1510": ("P2", "subprocess بدون check", "خطای اجرا نادیده گرفته می‌شود", "check=True"),
    "PLW3301": ("P3", "min/max تودرتو", "خوانایی", "ساده‌سازی"),
    "PLR0911": ("P3", "تعداد زیاد return", "پیچیدگی", "بازآرایی"),
    "PLR0124": ("P3", "مقایسه شیء با خودش", "باگ منطقی", "حذف"),
    "PLR1714": ("P3", "چند مقایسه قابل ادغام", "خوانایی", "in"),
    "PLR1730": ("P3", "if قابل تبدیل به min/max", "خوانایی", "min/max"),
    "PLR1736": ("P3", "enumerate با اندیس اضافه", "خوانایی", "مستقیم"),
    "PLC0206": ("P3", "پیمایش dict بدون items()", "کارایی", "items()"),
    "PLR5501": ("P3", "else-if قابل ادغام", "خوانایی", "elif"),
    "PLC0415": ("P3", "import داخل تابع", "چرخه import و تأخیر اولین فراخوانی پنهان می‌شود", "import در سطح ماژول"),
}

PATTERN_META = {
    "PY_BARE_EXCEPT": ("P1", "except بدون نوع — همه خطاها گرفته می‌شوند", "خطاهای برنامه‌نویسی (NameError/KeyboardInterrupt) پنهان می‌شوند", "except Exception + لاگ"),
    "PY_EXCEPT_PASS": ("P1", "except با بدنه pass", "شکست بی‌صدا", "لاگ و بازگرداندن خطا"),
    "PY_SLEEP_IN_ASYNC": ("P1", "time.sleep در تابع async", "event loop بلاک می‌شود و وظایف دیگر دیر اجرا می‌شوند", "await asyncio.sleep"),
    "PY_SYNC_REQUESTS": ("P1", "کتابخانه requests در کد async/سرویس", "I/O مسدودکننده در مسیر درخواست", "httpx.AsyncClient"),
    "PY_SYNC_HTTPX_CLIENT": ("P2", "httpx.Client همگام", "بلاک شدن worker در async", "AsyncClient"),
    "PY_VERIFY_FALSE": ("P0", "غیرفعال‌سازی بررسی TLS", "ریسک MITM روی داده بازار", "verify=True"),
    "PY_NAIVE_NOW": ("P2", "datetime.now بدون timezone", "ذخیره زمان بی‌ناحیه و مقایسه نادرست تازگی", "datetime.now(UTC یا Tehran)"),
    "PY_UTCNOW": ("P2", "datetime.utcnow منسوخ و naive", "تاریخ‌های بی‌ناحیه", "datetime.now(UTC)"),
    "PY_EVAL": ("P0", "استفاده از eval/exec", "اجرای کد دلخواه", "حذف یا parser امن"),
    "PY_PICKLE": ("P0", "deserialize با pickle", "اجرای کد در صورت دستکاری داده", "JSON/msgpack"),
    "PY_YAML_UNSAFE": ("P0", "yaml.load بدون Loader امن", "ساخت شیء دلخواه", "safe_load"),
    "PY_SHELL_TRUE": ("P0", "subprocess با shell=True", "تزریق فرمان", "لیست آرگومان"),
    "PY_EQ_NONE": ("P3", "مقایسه با None به‌جای is", "رفتار نامناسب با اشیای خاص", "is None"),
    "PY_MUTABLE_DEFAULT": ("P2", "آرگومان پیش‌فرض تغییرپذیر", "نشت حالت بین فراخوانی‌ها", "None + مقدار داخلی"),
    "PY_TODO": ("P3", "TODO/FIXME باز", "کار ناتمام در مسیر تولید", "پیگیری در issue"),
    "PY_PRINT": ("P3", "print در کد سرویس", "خروجی بدون ساختار و بدون trace", "logger"),
    "PY_SQL_FSTRING": ("P1", "SQL ساخته‌شده با f-string", "نام جدول/ستون در متن SQL تزریق می‌شود؛ اگر از ورودی کاربر بیاید تزریق SQL است", "شناسه‌های مجاز را allowlist و مقادیر را bind کنید"),
    "PY_SQL_FORMAT": ("P0", "SQL ساخته‌شده با format", "ریسک تزریق SQL", "bind params"),
    "PY_GLOBAL": ("P3", "وضعیت global", "غیرقابل تست و نشت بین درخواست‌ها", "DI/کلاس"),
    "PY_ASSERT": ("P2", "assert در کد اجرایی", "با python -O حذف می‌شود و اعتبارسنجی از بین می‌رود", "raise صریح"),
    "PY_EXCEPT_BASE": ("P1", "گرفتن BaseException", "لغو/خروج سیستم هم بلعیده می‌شود", "Exception"),
    "PY_RAISE_GENERIC": ("P3", "raise Exception عمومی", "خطای غیرقابل تفکیک", "کلاس خطای مشخص"),
    "PY_NOQA": ("P3", "سرکوب هشدار با noqa", "خطای واقعی پنهان می‌شود", "رفع علت"),
    "PY_TYPE_IGNORE": ("P3", "سرکوب type checker", "ناسازگاری نوع پنهان", "رفع نوع"),
    "PY_OPEN_NO_WITH": ("P3", "open بدون context manager", "نشت فایل‌دسکریپتور", "with open"),
    "PY_HARDCODED_LOCAL": ("P2", "آدرس localhost هاردکد", "در کانتینر/تولید به مقصد اشتباه می‌رود", "env"),
    "PY_HARDCODED_SECRET": ("P0", "مقدار محرمانه هاردکد", "افشای اعتبارنامه در مخزن", "secret manager"),
    "PY_CREATE_TASK_UNSAVED": ("P1", "create_task بدون نگه‌داشتن رفرنس", "تسک ممکن است نیمه‌کاره GC شود", "نگه‌داشتن در set"),
    "PY_SUBPROCESS": ("P2", "فراخوانی subprocess", "ریسک تزریق/وابستگی سیستمی", "بازبینی ورودی"),
    "PY_BROAD_EXCEPT_SWALLOW": ("P1", "except Exception بدون re-raise", "خطای همگام‌سازی/دریافت بلعیده می‌شود و سرویس ادعای موفقیت می‌کند", "لاگ ساختارمند + شکست صریح/متریک"),
    "TS_CONSOLE": ("P3", "console.log در کد تولید", "نویز و افشای اطلاعات", "حذف"),
    "TS_ANY": ("P3", "استفاده از any", "از دست رفتن بررسی نوع در داده مالی", "نوع دقیق"),
    "TS_TSIGNORE": ("P2", "سرکوب خطای TypeScript", "باگ نوع در زمان اجرا", "رفع نوع"),
    "TS_ESLINT_DISABLE": ("P3", "disabled کردن eslint", "قاعده کیفیت غیرفعال", "رفع علت"),
    "TS_DANGEROUS_HTML": ("P1", "dangerouslySetInnerHTML", "ریسک XSS", "sanitize"),
    "TS_LOCALSTORAGE": ("P2", "ذخیره داده در localStorage", "ریسک XSS و داده کهنه بین نسخه‌ها", "حافظه/کوکی httpOnly"),
    "TS_LOCALHOST": ("P2", "آدرس localhost هاردکد در فرانت", "در دسترسی از موبایل/شبکه کار نمی‌کند", "مسیر نسبی"),
    "TS_TODO": ("P3", "TODO باز در فرانت", "کار ناتمام", "issue"),
    "TS_JSON_PARSE": ("P3", "JSON.parse بدون اعتبارسنجی", "استثنا در زمان اجرا", "schema/zod"),
    "TS_AS_ANY": ("P3", "cast به any", "از دست رفتن بررسی نوع در داده بازار", "نوع دقیق"),
    "TS_CATCH_SILENT": ("P2", "بلعیدن خطا در catch", "شکست شبکه به داده خالی/بی‌حرکت تبدیل می‌شود", "نمایش خطا و retry"),
    "TS_EMPTY_FALLBACK": ("P2", "fallback به آرایه خالی", "نبود داده و خطا یکسان نمایش داده می‌شوند", "تفکیک حالت خالی از خطا"),
    "TS_REFETCH_OFF": ("P2", "بازخوانی هنگام بازگشت به تب خاموش است", "کاربر داده کهنه می‌بیند تا interval بعدی", "فعال‌سازی refetchOnWindowFocus"),
    "TS_INTERVAL": ("P3", "setInterval دستی", "نشت تایمر/به‌روزرسانی تکراری در StrictMode", "بررسی cleanup"),
    "TS_POLL_FAST": ("P3", "interval بازخوانی کوتاه", "بار اضافی بدون تازه‌تر شدن منبع", "interval تطبیقی"),
    "PY_IMPORT_IN_FUNC": ("P3", "import داخل تابع", "وابستگی دوری/تأخیر در اولین فراخوانی و پنهان‌شدن چرخه import", "import در سطح ماژول"),
}

ESLINT_META = {
    "@typescript-eslint/no-unused-vars": ("P3", "متغیر/پارامتر بی‌استفاده", "نویز و نشانه کد ناتمام", "حذف"),
    "react-hooks/exhaustive-deps": ("P2", "وابستگی useEffect ناقص", "داده کهنه در UI یا حلقه بی‌پایان", "تکمیل deps"),
    "react/no-unescaped-entities": ("P3", "کاراکتر escape‌نشده در JSX", "خطای رندر در برخی متن‌ها", "escape"),
    "react-hooks/set-state-in-effect": ("P2", "setState مستقیم در effect", "رندر آبشاری و پرش UI", "محاسبه مشتق‌شده"),
    "@next/next/no-img-element": ("P3", "img خام به‌جای next/image", "کارایی تصویر", "next/image"),
    None: ("P3", "خطای پارس/قاعده ESLint", "فایل ممکن است هرگز بررسی نشود", "رفع خطای پارس"),
}


def resolve_manual() -> tuple[list[dict], list[str]]:
    out, unresolved = [], []
    for m in MANUAL:
        ls = lines_of(m["file"])
        pat = re.compile(m["anchor"])
        hits = [i for i, line in enumerate(ls, 1) if pat.search(line)]
        if len(hits) < m["occ"]:
            unresolved.append(f"{m['file']} :: {m['anchor']}")
            continue
        line = hits[m["occ"] - 1]
        out.append(
            {
                "cat": m["cat"], "file": m["file"], "line": line, "sev": m["sev"], "status": m["status"],
                "title": m["title"], "impact": m["impact"], "fix": m["fix"], "anchor": m["anchor"],
                "snippet": snippet(m["file"], line), "source": "دستی/تأییدشده",
            }
        )
    return out, unresolved


def load_ruff(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for x in data:
        code = x.get("code")
        if code not in RUFF_META:
            continue
        f = norm(x["filename"])
        if not f or f.startswith("tests/"):
            continue
        sev, title, impact, fix = RUFF_META[code]
        out.append(
            {"cat": category_for(f), "file": f, "line": x["location"]["row"], "sev": sev, "status": "ابزار (ruff)",
                 "title": f"{title} [{code}]", "impact": impact, "fix": fix,
                 "snippet": snippet(f, x["location"]["row"]), "source": "ruff"}
        )
    return out


def load_patterns(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for x in data:
        meta = PATTERN_META.get(x["rule"])
        if not meta:
            continue
        sev, title, impact, fix = meta
        f = x["file"]
        out.append(
            {"cat": category_for(f), "file": f, "line": x["line"], "sev": sev, "status": "الگو (regex)",
                 "title": f"{title} [{x['rule']}]", "impact": impact, "fix": fix,
                 "snippet": x["snippet"], "source": "pattern"}
        )
    return out


ESLINT_FILE_MAP = {}


def load_eslint(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for r in data:
        f = norm(r.get("filePath", ""))
        for m in r.get("messages", []):
            rule = m.get("ruleId")
            sev, title, impact, fix = ESLINT_META.get(rule, ("P3", f"قاعده {rule}", "کیفیت کد", "رفع"))
            line = m.get("line") or 1
            out.append(
                {"cat": "FE", "file": f, "line": line, "sev": sev, "status": "ابزار (eslint)",
                     "title": f"{title} [{rule or 'parse'}]", "impact": impact, "fix": fix,
                     "snippet": snippet(f, line), "source": "eslint"}
            )
    return out


# The twelve findings an operator should read first, in causal order of the
# "data is stale" symptom.
HOT = [
    ("Dockerfile", r'CMD \["python", "-m", "ingestion.main"\]'),
    ("docker-compose.yml", r"context: \./frontend"),
    ("docker-compose.override.yml", r"^  api:"),
    ("docker-compose.yml", r"NEXT_PUBLIC_API_URL=http://backend:8000"),
    ("frontend/src/hooks/useMarketData.ts", r"isLive: cells\.length > 0"),
    ("brsapi/services/query_service.py", r'func\.max\(SymbolSnapshotModel\.id\)\.label\("max_id"\)'),
    ("apps/api/endpoints/market.py", r'"board": s\.get\("board", ""\),'),
    ("ingestion/config.py", r'default="postgresql\+asyncpg://postgres:postgres@localhost:5433/marketdb"'),
    ("ingestion/lake/__init__.py", r'or self\._config\.lake_secret_key == "minioadmin"'),
    ("ingestion/worker.py", r"count \+= len\(events\)"),
    ("apps/api/app.py", r"scheduler_app = SchedulerApp\(\)"),
    ("apps/scheduler/app.py", r"Scheduler could not enqueue %s — falling back to in-process dispatch"),
]


def build() -> None:
    manual, unresolved = resolve_manual()
    if unresolved:
        print("!! unresolved anchors:", len(unresolved))
        for u in unresolved:
            print("   ", u)

    seen: set[tuple[str, int]] = set()
    pool: list[dict] = []
    for item in manual:
        key = (item["file"], item["line"])
        if key in seen:
            continue
        seen.add(key)
        pool.append(item)

    rest: list[dict] = []
    for item in load_ruff(str(BASE / "_ruff_broad.json")) + load_patterns(str(BASE / "_pattern_findings.json")) + load_eslint(str(BASE / "_eslint.json")):
        key = (item["file"], item["line"])
        if key in seen:
            continue
        seen.add(key)
        rest.append(item)

    # Keep the catalog diverse: a single lint rule must not fill the whole list.
    CODE_CAP = {
        "PLC0415": 90, "PY_NOQA": 40, "PY_TYPE_IGNORE": 40, "PY_GLOBAL": 40,
        "PY_PRINT": 40, "RUF100": 25, "E701": 25, "E702": 25, "PLR0911": 20,
        "RET505": 20, "UP042": 15, "RUF022": 15, "PLW0603": 25,
        "PY_BROAD_EXCEPT_SWALLOW": 140, "TS_EMPTY_FALLBACK": 45, "TS_CATCH_SILENT": 55,
    }
    used: Counter = Counter()
    capped: list[dict] = []
    for item in rest:
        m = re.search(r"\[([A-Z][A-Z0-9_]+)\]$", item["title"])
        code = m.group(1) if m else None
        cap = CODE_CAP.get(code) if code else None
        if cap is not None:
            if used[code] >= cap:
                continue
            used[code] += 1
        capped.append(item)
    rest = capped

    rest.sort(key=lambda x: (SEV_RANK[x["sev"]], CAT_ORDER.index(x["cat"]) if x["cat"] in CAT_ORDER else 9, x["file"], x["line"]))
    selected = pool[:MAX_ITEMS] + rest[: max(0, MAX_ITEMS - len(pool))]

    # assign ids
    counters: Counter = Counter()
    sections: dict[str, list[dict]] = defaultdict(list)
    for n, item in enumerate(selected, 1):
        counters[item["cat"]] += 1
        item["id"] = f"{item['cat']}-{counters[item['cat']]:03d}"
        item["n"] = n
        sections[item["cat"]].append(item)

    sev_count = Counter(i["sev"] for i in selected)
    src_count = Counter(i["source"] for i in selected)

    out = []
    w = out.append
    w("# فهرست ۱۰۰۰ ایراد پروژه temce — با محل دقیق")
    w("")
    w("این گزارش بر پایه کد موجود در مخزن ساخته شده و هر ردیف به **فایل:خط واقعی** اشاره می‌کند؛")
    w("متن کد نقل‌شده از همان خط خوانده شده است، نه از حافظه یا گزارش قبلی.")
    w("")
    w(f"- تعداد ردیف: **{len(selected)}**")
    w("- توزیع شدت: " + " · ".join(f"{k}={sev_count[k]}" for k in ["P0", "P1", "P2", "P3"]))
    w("- منبع هر ردیف: " + " · ".join(f"{k}={v}" for k, v in src_count.most_common()))
    w("")
    w("## راهنمای شدت و وضعیت")
    w("")
    w("| شدت | معنا |")
    w("|---|---|")
    w("| P0 | مسیر داده/سرویس را می‌شکند یا علت مستقیم کهنه‌بودن داده است |")
    w("| P1 | ریسک بالا: خطای بی‌صدا، داده ناقص، مصرف سهمیه، رفتار نادرست |")
    w("| P2 | نقص کیفیت/پایداری که در شرایط خاص اثر می‌گذارد |")
    w("| P3 | بدهی فنی و خوانایی |")
    w("")
    w("| وضعیت | معنا |")
    w("|---|---|")
    w("| تأییدشده | با خواندن کد در همین نسخه تأیید شده |")
    w("| ابزار (ruff/eslint) | خروجی ابزار با فایل:خط دقیق |")
    w("| الگو (regex) | الگوی مشخص در خط مشخص؛ نیازمند قضاوت انسانی |")
    w("| نیازمند آزمون | رفتار وابسته به محیط/داده است |")
    w("")
    w("## زنجیره علت کهنه‌شدن داده (به ترتیب اثر)")
    w("")
    w("```")
    w("منبع (BRSAPI_ENABLED/سهمیه 302)")
    w("   └─ همگام‌سازی اجرا نمی‌شود یا شکست می‌خورد (خطای بلعیده‌شده)")
    w("        └─ جدول snapshot تازه نمی‌شود؛ خواندن با MAX(id) رکورد قدیمی را «آخرین» می‌بیند")
    w("             └─ API پاسخ success=True با داده کهنه می‌دهد (بدون as_of)")
    w("                  └─ فرانت isLive را از «تعداد ردیف > 0» می‌سازد → داده قدیمی «زنده» دیده می‌شود")
    w("```")
    w("")
    w("## ۱۲ یافته‌ای که باید اول بررسی شوند (به ترتیب همین زنجیره)")
    w("")
    by_key = {(i["file"], i.get("anchor")): i for i in manual}
    top = [by_key[k] for k in HOT if k in by_key][:12]
    for i in top:
        w(f"**{i['id']}** — `{i['file']}:{i['line']}` — {i['title']}")
        w("")
        w(f"> {i['snippet']}")
        w("")
        w(f"اثر: {i['impact']} — راه‌حل: {i['fix']}")
        w("")
    w("---")
    w("")

    serial = 0
    for cat in CAT_ORDER:
        rows = sections.get(cat, [])
        if not rows:
            continue
        w(f"## {cat} — {CAT_TITLE[cat]} ({len(rows)} مورد)")
        w("")
        w("| # | کد | شدت | محل دقیق | مشکل | اثر / راه‌حل | کد خط |")
        w("|---|---|---|---|---|---|---|")
        for i in rows:
            serial += 1
            i["n"] = serial
            snip = i["snippet"].replace("|", "\\|")[:120]
            title = i["title"].replace("|", "\\|")
            fix = i["fix"].replace("|", "\\|")
            impact = i["impact"].replace("|", "\\|")
            w(f"| {i['n']} | {i['id']} | {i['sev']} | `{i['file']}:{i['line']}` | {title} | {impact} → {fix} | `{snip}` |")
        w("")

    w("---")
    w("")
    w("## پیوست — بازبینی ادعاهای مسیر ingestion (DATA-013 تا DATA-026)")
    w("")
    w("ادعاهای یک تحلیل قبلی روی همین مخزن دوباره با کد فعلی مقایسه شد. سه مورد در این نسخه برقرار نیستند؛")
    w("آن‌ها را دور نزنید، اما به‌عنوان باگ موجود هم ثبت نکنید.")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ دوم: DATA-027 تا DATA-040 (سرویس sync و کوئری‌های خواندن)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY2:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ سوم: DATA-041 تا DATA-054 (اندپوینت بازار و اندیکاتورها)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY3:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ چهارم: DATA-055 تا DATA-068 (هوک‌های فرانت و تجمیع جریان)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY4:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ پنجم: DATA-069 تا DATA-082 (پایش، WebSocket، backfill، سلامت)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY5:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ ششم: DATA-083 تا DATA-091 (ذخیرهٔ قیمت، اسکن بازار، ارز)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY6:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ هفتم: DATA-092 تا DATA-100 (jobها و صف Redis)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY7:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ هشتم: DATA-101 تا DATA-106 (اتصال scheduler به صف، startup کارگر، از دست رفتن job)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY8:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("#### یافته‌های تازه‌ای که هنگام تأیید همین دسته پیدا شد")
    w("")
    w("| # | یافته | محل | چرا مهم است |")
    w("|---|---|---|---|")
    w("| ۱ | worker image ماژولی را اجرا می‌کند که نقطهٔ ورودی ندارد | `Dockerfile.worker:56` | "
      "`python -m apps.worker.app` بلافاصله با کد ۰ خارج می‌شود؛ هیچ jobی مصرف نمی‌شود. |")
    w("| ۲ | worker کلاس‌های job را register نمی‌کند | `apps/worker/app.py:32` در برابر `apps/scheduler/app.py:61` | "
      "registry در فرآیند worker خالی است؛ هر job صف‌شده «not found» و سپس dead-letter می‌شود. |")
    w("| ۳ | نام jobهای BrsApi با کلید registry یکی نیست | `brsapi/jobs/registry.py:119` در برابر `jobs/definitions/brsapi_jobs.py:103` | "
      "`brsapi_all_symbols` منتشر می‌شود اما کلید ثبت‌شده `BrsApiAllSymbolsJob` است. |")
    w("| ۴ | گیت ساعات بازار در مسیر صف اعمال نمی‌شود | `jobs/definitions/brsapi_jobs.py:41` | "
      "با اصلاح نام‌ها، jobها خارج از ساعت بازار هم اجرا می‌شوند و سهمیهٔ رایگان می‌سوزد. |")
    w("")
    w("نکته: DATA-106 همان ردیف `DEP-016` است (Redis بدون healthcheck + `service_started`) و "
      "برای پرهیز از تکرار، ردیف تازه‌ای برایش ساخته نشد؛ ادعا در جدول بالا تأیید می‌شود.")
    w("")
    w("### دستهٔ نهم: ROOT-001 تا ROOT-005 (زنجیرهٔ استقرار)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in ROOT_VERIFY:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("### دستهٔ دهم: DATA-151 تا DATA-162 (انتخاب رکورد جاری)")
    w("")
    w("| ادعا | وضعیت در این نسخه | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY10:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("ده مورد از این دوازده ادعا از قبل ردیف کاتالوگ دارند (DB-006، DB-009…DB-014، API-006، "
      "DATA-041/044)؛ دو مورد به محل قدیمی اشاره می‌کنند و یک مورد (sparkline) سومین بار رد می‌شود. "
      "فقط یک ردیف تازه ساخته شد: `DATA-052` (truncation کل جدول به‌ازای هر نماد).")
    w("")
    w("### دستهٔ یازدهم: DATA-168 تا DATA-184 (نمایش و محاسبات)")
    w("")
    w("هر ۱۷ ادعای این دسته از قبل ردیف کاتالوگ دارند؛ هیچ ردیف تازه‌ای ساخته نشد. "
      "شماره‌خط‌های گزارش به نسخهٔ قدیمی‌تر اشاره می‌کنند (مثلاً isLive از ۴۲۳-۴۷۰ به ۲۸۱/۳۱۳ و heatmap از ۱۰۶ به ۱۲۰).")
    w("")
    w("| ادعا | وضعیت | محل واقعی امروز | توضیح |")
    w("|---|---|---|---|")
    for claim, status, loc, note in CLAIM_VERIFY11:
        w(f"| {claim} | {status} | {loc} | {note} |")
    w("")
    w("#### شواهد اجرایی محدود (بدون بالا آوردن سرویس‌ها)")
    w("")
    w("- `python -m apps.worker.app` در همین محیط با کد ۰ و بدون هیچ خروجی برمی‌گردد؛ "
      "یعنی همان CMD ایمیج worker هیچ حلقه‌ای اجرا نمی‌کند.")
    w("- در یک فرآیند تازه، `job_registry.list_names()` برابر ۰ و `get('SyncQuotesJob')` برابر `None` است.")
    w("- پس از `register_module(jobs.definitions)` تعداد ۶۶ job ثبت می‌شود، اما "
      "`get('brsapi_all_symbols')` هنوز `None` است (تأیید نامطابقی نام صف و کلید registry).")
    w("- `docker compose config` با خطای `service \"api\" has neither an image nor a build context "
      "specified: invalid compose project` برمی‌گردد؛ یعنی ترکیب فایل پایه و override معتبر نیست.")
    w("- `asyncpg.create_pool('postgresql+asyncpg://...')` با "
      "`ClientConfigurationError: scheme is expected to be either \"postgresql\" or \"postgres\"` رد می‌شود.")
    w("")
    w("")
    w("---")
    w("")
    w("## روش تولید و محدودیت‌ها")
    w("")
    w("1. ردیف‌های «تأییدشده» با خواندن همان فایل و همان خط در این نسخه نوشته شده‌اند.")
    w("2. ردیف‌های ruff با اجرای `ruff check --select E,F,W,B,S,SIM,UP,C4,RET,ASYNC,PL,PT,RUF,I,N` روی")
    w("   `brsapi apps ingestion jobs core domain services api repositories providers orchestration monitoring integrations contracts schemas config` تولید شده‌اند.")
    w("3. ردیف‌های eslint با اجرای `eslint src -f json` روی `frontend/src` تولید شده‌اند.")
    w("4. ردیف‌های «الگو» با اسکن regex روی همان درخت‌ها ساخته شده‌اند؛ هر ردیف الگوی واقعی را در خط واقعی نشان می‌دهد،")
    w("   اما قضاوت درباره شدت آن نیازمند بررسی زمینه است.")
    w("5. این گزارش **اثبات اجرایی محیط شما نیست**: نه سرویس‌ها اجرا شده‌اند و نه دیتابیس/Redis واقعی خوانده شده است.")
    w("   برای قطعی‌کردن علت، خروجی `docker compose ps -a`، لاگ سرویس‌ها و `MAX(fetched_at)` جدول snapshot لازم است.")
    w("")

    Path("docs/audits").mkdir(parents=True, exist_ok=True)
    target = Path("docs/audits/ISSUE_CATALOG_1000.md")
    target.write_text("\n".join(out), encoding="utf-8")
    print("wrote", target, "rows", len(selected))
    print("per-category", dict(counters))
    print("severity", dict(sev_count))
    print("sources", dict(src_count))
    print("hot-resolved", len(top), "of", len(HOT))


if __name__ == "__main__":
    build()
