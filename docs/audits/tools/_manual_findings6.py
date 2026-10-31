"""Sixth batch of hand-verified findings (quotes, market scan, currency)."""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append({"cat": cat, "file": file, "anchor": anchor, "occ": occ, "title": title,
                  "sev": sev, "status": status, "impact": impact, "fix": fix})


add("DATA", "services/quote_service.py", r"return Result\.ok\(count\)", 1,
    "ذخیره دسته‌ای قیمت‌ها، شکست‌های جزئی را موفق گزارش می‌کند",
    "P1", "تأییدشده",
    "اگر بخشی از نمادها ذخیره نشوند، فراخواننده Result.ok می‌گیرد و داده ناقص را کامل می‌پندارد.",
    "برگرداندن requested/succeeded/failed و وضعیت partial.")
add("DATA", "services/quote_service.py", r"async def ingest_historical", 1,
    "دریافت تاریخچه در QuoteService پیاده‌سازی نشده و همیشه fail برمی‌گرداند",
    "P2", "تأییدشده",
    "در این نسخه هیچ call-site ندارد؛ قابلیت مرده است و اگر روزی وصل شود، تاریخچه خالی می‌ماند.",
    "حذف/غیرفعال‌سازی صریح یا پیاده‌سازی با تست انتها‌به‌انتها.")
add("DATA", "services/quote_service.py", r'price_close=float\(data\.get\("pClosing", 0\)\),', 1,
    "فیلدهای غایب پاسخ TSETMC به صفر تبدیل می‌شوند",
    "P1", "تأییدشده",
    "پاسخ ناقص یا تغییرساختار، صفر معتبر تولید می‌کند و قیمت صحیح قبلی را مخدوش می‌کند.",
    "اعتبارسنجی فیلد ضروری و تفکیک None از صفر واقعی.")
add("DATA", "ingestion/market_scan_service.py", r"self\._warm_sink = warm_sink or \(", 1,
    "MarketScanService بدون session_factory فقط لایه hot دارد",
    "P1", "تأییدشده",
    "اگر session_factory تزریق نشود، warm sink برابر None است و اسکن در دیتابیس پایدار نمی‌شود.",
    "اجبار warm sink در production و نمایش degraded در health.")
add("DATA", "ingestion/market_scan_service.py", r"if not result\.success or result\.value is None:", 1,
    "شکست اسکن در scan_once بی‌صدا None برمی‌گرداند",
    "P2", "تأییدشده",
    "علت شکست (منبع یا persistence) به فراخواننده و مانیتورینگ نمی‌رسد.",
    "تفکیک منبع/خالی/ذخیره‌سازی و ثبت کد خطا.")
add("DATA", "apps/currency_service/infra/collectors.py", r"free = await fetch_tgju_dollar\(client\) or fixture\.free", 1,
    "نرخ ارز در شکست منبع، از fixture با jitter تصادفی ساخته می‌شود",
    "P0", "تأییدشده",
    "قیمت نمایش‌داده‌شده واقعی نیست، اما timestamp تازه می‌گیرد و jitter تغییر ظاهری می‌سازد؛ کاربر آن را زنده می‌پندارد.",
    "فیلد is_fallback/source_status در پاسخ و برچسب صریح «غیرزنده» در UI.")
add("DATA", "apps/currency_service/infra/collectors.py", r'logger\.warning\("tgju fetch failed; falling back to fixture"', 1,
    "خطای منبع ارز فقط warning است و به caller ساخت‌یافته منتقل نمی‌شود",
    "P1", "تأییدشده",
    "لایه بالاتر نمی‌تواند «زنده موفق» را از «fallback» تشخیص دهد.",
    "نتیجه collector = داده + وضعیت + خطای اختیاری.")
