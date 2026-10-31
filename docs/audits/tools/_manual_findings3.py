"""Third batch of hand-verified findings (market endpoints + indicators)."""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append({"cat": cat, "file": file, "anchor": anchor, "occ": occ, "title": title,
                  "sev": sev, "status": status, "impact": impact, "fix": fix})


add("API", "apps/api/endpoints/market.py", r"get_latest_snapshots\(limit=100\)", 1,
    "heatmap ساده فقط ۱۰۰ نماد می‌گیرد و پارامتر limit ندارد",
    "P1", "تأییدشده",
    "در بازار با بیش از ۱۰۰ نماد، بقیه در پاسخ نیستند و پاسخ همچنان success=True است.",
    "صفحه‌بندی واقعی یا limit قابل تنظیم + اعلام total/returned در قرارداد.")
add("API", "apps/api/endpoints/market.py", r"get_enriched_snapshots\(limit=500\)", 1,
    "heatmap غنی سقف ثابت ۵۰۰ نماد دارد",
    "P1", "تأییدشده",
    "نمادهای فراتر از ۵۰۰ حذف می‌شوند؛ با مرتب‌سازی بر ارزش معامله، نمادهای کم‌معامله بیشتر قربانی می‌شوند.",
    "cursor/صفحه‌بندی و نمایش total.")
add("API", "services/market_service.py", r"get_latest_snapshots\(limit=500\)", 1,
    "آمار «کل بازار» از حداکثر ۵۰۰ snapshot محاسبه می‌شود",
    "P1", "تأییدشده",
    "total_instruments/total_quotes و مجموع ارزش و میانگین تغییر، آمار کل بازار نیستند.",
    "تجمیع در SQL روی کل آخرین چرخه یا نام‌گذاری صریح «نمونه».")
add("API", "services/market_service.py", r"get_latest_snapshots\(limit=200\)", 1,
    "خلاصه صنایع حداکثر ۲۰۰ نماد را می‌بیند",
    "P2", "تأییدشده",
    "شمارش و ارزش هر صنعت ناقص است.",
    "تجمیع دیتابیسی روی کل snapshotهای چرخه آخر.")
add("API", "services/market_service.py", r'sec\["avg_change"\] = 0', 1,
    "میانگین تغییر صنعت همیشه صفر برگردانده می‌شود",
    "P2", "تأییدشده",
    "فیلد avg_change هرگز از price_last_change_pct محاسبه نمی‌شود و گمراه‌کننده است.",
    "محاسبه میانگین با سیاست روشن برای null.")
add("API", "services/market_service.py", r'sector = s\.get\("sector_name"\) or s\.get\("industry", "سایر"\)', 1,
    "نام فیلد صنعت با مدل snapshot هم‌خوان نیست",
    "P1", "تأییدشده",
    "مدل و `_row_dict` فیلد `sector` می‌دهند؛ بنابراین همه نمادها در دسته «سایر» می‌افتند.",
    "افزودن `sector` به زنجیره خواندن و یکسان‌سازی نام فیلد.")
add("API", "services/market_service.py", r"ORDER BY symbol, date DESC", 1,
    "sparkline برخلاف docstring از جدید به قدیم برگردانده می‌شود",
    "P2", "تأییدشده",
    "نمودارهایی که آرایه را چپ‌به‌راست زمانی رسم می‌کنند روند را وارونه نشان می‌دهند.",
    "reverse پس از انتخاب N ردیف یا ORDER BY صعودی در خروجی.")
add("API", "services/market_service.py", r"data = await self\._brsapi\.get_historical_daily\(symbol, limit=500\)", 1,
    "فیلتر بازه تاریخی بعد از محدودسازی به ۵۰۰ ردیف اعمال می‌شود",
    "P1", "تأییدشده",
    "درخواست بازه قدیمی‌تر ممکن است خالی برگردد در حالی که داده در دیتابیس موجود است.",
    "انتقال شرط تاریخ به کوئری دیتابیس.")
add("API", "services/market_service.py", r"start = \(date\.today\(\) - timedelta\(days=limit \* 3\)\)\.isoformat\(\)", 1,
    "بازه fallback با تاریخ محلی سرور و روز تقویمی ساخته می‌شود",
    "P2", "تأییدشده",
    "اختلاف timezone مرز روز را جابه‌جا می‌کند و تعطیلات در limit*3 حساب نمی‌شوند.",
    "تاریخ بازار با timezone صریح + شمارش کندل به‌جای روز تقویمی.")
add("API", "services/market_service.py", r"offset = slow - fast", 1,
    "MACD با fast بزرگ‌تر از slow اعتبارسنجی نمی‌شود",
    "P2", "تأییدشده",
    "با fast>slow آفست منفی می‌شود و EMAها نادرست هم‌تراز می‌شوند؛ خروجی بی‌معنی.",
    "اعتبارسنجی رابطه‌ای fast<slow در endpoint و تابع.")
add("API", "services/market_service.py", r"chikou = closes\[kijun_period:\]", 1,
    "سری‌های Ichimoku هم‌تراز نیستند و شیفت Senkou/Chikou اعمال نمی‌شود",
    "P2", "تأییدشده",
    "tenkan/kijun/senkou/chikou طول‌های متفاوت دارند؛ تاریخ‌ها فقط با سری اول هم‌تراز می‌شوند.",
    "خروجی با آرایه تاریخ مستقل یا null برای نقاط شیفت‌خورده.")
add("API", "services/market_service.py", r"d_line = MarketService\._sma\(k_line, d_smooth\)", 1,
    "طول سری %D کمتر از %K است اما تاریخ‌ها با طول %K هم‌تراز می‌شوند",
    "P2", "تأییدشده",
    "نقاط D با تاریخ اشتباه یا تعداد نامتوازن رسم می‌شوند.",
    "تاریخ مستقل per-series یا offset صریح.")
add("API", "services/market_service.py", r'"close": d\.get\("price_last"\),', 1,
    "کندل روزانه close را از price_last می‌گیرد و price_close را نادیده می‌برد",
    "P2", "تأییدشده",
    "نمودار روزانه به‌جای قیمت پایانی رسمی، آخرین معامله را نشان می‌دهد.",
    "استفاده از price_close برای کندل روزانه و price_last فقط برای realtime.")
add("API", "services/market_service.py", r'return Result\.ok\(\{"indicator": indicator, "country": country\}\)', 1,
    "نبود دادهٔ macro به‌صورت موفقیت بدون کلید data برگردانده می‌شود",
    "P2", "تأییدشده",
    "مصرف‌کننده پاسخ را موفق می‌بیند و بعداً به‌خاطر نبود data خطا می‌دهد.",
    "data: [] صریح یا Result.fail با دلیل.")
