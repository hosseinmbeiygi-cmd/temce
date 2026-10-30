"""Fifth batch of hand-verified findings (monitoring, WS, backfill, health)."""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append(dict(cat=cat, file=file, anchor=anchor, occ=occ, title=title,
                  sev=sev, status=status, impact=impact, fix=fix))


add("FE", "frontend/src/hooks/useApiMonitor.ts", r'export function useApiMonitor\(baseUrl: string = "http://localhost:8000"\)', 1,
    "مانیتور API به‌طور پیش‌فرض localhost کاربر را بررسی می‌کند",
    "P1", "تأییدشده",
    "در production، مرورگر خودِ دستگاه کاربر را روی پورت ۸۰۰۰ می‌زند و API سالم را offline نشان می‌دهد.",
    "آدرس از پیکربندی واحد/مسیر same-origin و بدون پیش‌فرض localhost در تولید.")
add("FE", "frontend/src/hooks/useApiMonitor.ts", r"if \(response\.ok\)", 1,
    "وضعیت «آنلاین» فقط از کد ۲۰۰ ساخته می‌شود و بدنه بررسی نمی‌شود",
    "P2", "تأییدشده",
    "/health فقط liveness است؛ دیتابیس، Redis و منبع داده ممکن است خراب باشند ولی پنل «آنلاین» بدهد.",
    "تفکیک liveness/readiness و نمایش آخرین sync.")
add("FE", "frontend/src/hooks/useWebSocket.ts", r"action: 'subscribe',", 1,
    "اشتراک WebSocket فقط در onopen ارسال می‌شود و با تغییر نمادها به‌روز نمی‌شود",
    "P1", "تأییدشده",
    "نماد تازه‌اضافه‌شده قیمت زنده نمی‌گیرد و نماد حذف‌شده در اشتراک می‌ماند.",
    "ارسال subscribe/unsubscribe در effect وابسته به symbols یا بازسازی اتصال.")
add("FE", "frontend/src/hooks/useWebSocket.ts", r"timestamp: Date\.now\(\),", 1,
    "زمان دریافت مرورگر جای timestamp منبع را می‌گیرد",
    "P1", "تأییدشده",
    "پیام دیررس «تازه» به نظر می‌رسد و تأخیر شبکه/منبع قابل اندازه‌گیری نیست.",
    "حفظ timestamp سرور و افزودن received_at جداگانه.")
add("FE", "frontend/src/hooks/useWebSocket.ts", r"// Ignore malformed messages", 1,
    "پیام نامعتبر WebSocket بی‌صدا دور ریخته می‌شود",
    "P2", "تأییدشده",
    "اتصال connected می‌ماند ولی قیمت‌ها به‌روز نمی‌شوند؛ هیچ نشانه‌ای ثبت نمی‌شود.",
    "شمارنده decode_error + لاگ محدود + اعتبارسنجی schema.")
add("FE", "frontend/src/hooks/useBackgroundBackfill.ts", r"const res = await apiGet<\{ success: boolean; data: BackfillState \}>\(statusUrl\);", 1,
    "خطای polling وضعیت backfill به undefined تبدیل می‌شود",
    "P2", "تأییدشده",
    "خطای شبکه/۵۰۰ از «وضعیت در دسترس نیست» قابل تفکیک نیست و UI وضعیت قدیمی را نشان می‌دهد.",
    "فیلد pollError و last_poll_ok_at.")
add("FE", "frontend/src/hooks/useBackgroundBackfill.ts", r'setBackfill\(\{ \.\.\.IDLE_BACKFILL, status: "running"', 1,
    "شروع backfill بدون بررسی started به running تغییر می‌کند",
    "P2", "تأییدشده",
    "اگر سرور درخواست را رد کند، UI همچنان «در حال اجرا» می‌ماند.",
    "اعتبارسنجی success/started و شروع polling فقط برای job واقعی.")
add("FE", "frontend/src/hooks/useBackgroundBackfill.ts", r"const res = await apiPost<\{ success: boolean; data: StartResponse \}>\(startUrl\);", 1,
    "خطای شروع backfill به undefined تبدیل می‌شود",
    "P2", "تأییدشده",
    "دلیل شکست شروع job به کاربر نمی‌رسد.",
    "نتیجه {ok:false,error} و نمایش پیام سرور.")
add("FE", "frontend/src/hooks/useBackgroundBackfill.ts", r"const res = await apiPost<\{ success: boolean; data: CancelResponse \}>\(cancelUrl\);", 1,
    "لغو backfill بدون تأیید سرور و بدون بازخوانی وضعیت انجام می‌شود",
    "P2", "تأییدشده",
    "ممکن است UI لغو را انجام‌شده بداند در حالی که job در سرور ادامه دارد.",
    "پس از لغو، status را دوباره بخوانید و تا تأیید سرور «لغوشده» نشان ندهید.")
add("API", "apps/api/endpoints/health.py", r'if db_status != "ok":', 1,
    "در /health/full فقط وضعیت دیتابیس روی overall اثر می‌گذارد",
    "P2", "تأییدشده",
    "Redis یا BrsApi می‌توانند error باشند ولی overall=ok بماند؛ /ready با همان شرایط 503 می‌دهد.",
    "تعریف واحد از overall و مستندسازی معنای هر endpoint.")
add("API", "apps/api/endpoints/monitoring.py", r'"null_check": staleness < 300,', 1,
    "چک null_check در داشبورد کیفیت داده، nullها را بررسی نمی‌کند",
    "P2", "تأییدشده",
    "نام چک با محاسبه هم‌خوان نیست و سلامت فیلدهای قیمت/حجم را القا می‌کند بدون بررسی.",
    "متریک null_price_rows/null_volume_rows واقعی یا حذف/تغییر نام چک.")
add("API", "apps/api/endpoints/ingestion.py", r"dl_len = 0", 1,
    "خطای خواندن صف dead-letter به «صف خالی» تبدیل می‌شود",
    "P1", "تأییدشده",
    "اگر Redis قطع باشد، داشبورد عمق صفر گزارش می‌کند و هشدار هرگز فعال نمی‌شود.",
    "queue_status=unknown و success=false در خطا.")
add("API", "apps/api/endpoints/quotes.py", r'engine = create_async_engine\("sqlite\+aiosqlite:///data/market\.db"\)', 1,
    "اندپوینت تست قیمت مستقیماً SQLite جدا می‌سازد و engine را dispose نمی‌کند",
    "P2", "تأییدشده",
    "نتیجه با PostgreSQL برنامه متفاوت است و اتصال‌ها نشت می‌کنند؛ در محیط عمومی ریسک اطلاعاتی دارد.",
    "استفاده از session واحد یا محدودسازی به محیط توسعه + dispose.")
add("API", "apps/api/endpoints/symbols.py", r'error=\{"message": f"Server error: \{exc\}"\}', 1,
    "متن خام استثنا به کلاینت برگردانده می‌شود",
    "P2", "تأییدشده",
    "ممکن است مسیر فایل یا جزئیات اتصال افشا شود.",
    "پیام عمومی + شناسه درخواست و جزئیات فقط در لاگ.")
