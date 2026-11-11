"""Eighth batch of hand-verified findings (scheduler→queue, worker startup, job loss)."""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append({"cat": cat, "file": file, "anchor": anchor, "occ": occ, "title": title,
                  "sev": sev, "status": status, "impact": impact, "fix": fix})


# ── DATA-101 … DATA-106 ─────────────────────────────────────────────
add("SCH", "brsapi/jobs/registry.py", r"await self\._run_handler\(job_name\)", 1,
    "در حالت queue، شکست publish برای jobهای BrsApi هیچ fallback درون‌فرآیندی ندارد",
    "P1", "تأییدشده",
    "پوشش صف در `apps/scheduler/app.py:69` فقط `publish()` را صدا می‌زند؛ خروجی None بررسی نمی‌شود، "
    "پس هنگام اختلال Redis این jobها نه در صف می‌روند نه درون‌فرآیند اجرا می‌شوند.",
    "بررسی نتیجه publish و اجرای امن درون‌فرآیندی یا ثبت خطای قابل‌پایش و retry زمان‌بندی.")
add("SCH", "apps/worker/consumer.py", r"if self\.consumer\.is_available:", 1,
    "worker در نبود Redis هنگام startup برای همیشه idle می‌ماند",
    "P0", "تأییدشده",
    "اگر `initialize()` در `core/cache.py` شکست بخورد، `_redis` برای همیشه None می‌ماند و "
    "`WorkerApp.start()` هیچ تلاش دوره‌ای برای اتصال مجدد یا start دوباره consumer ندارد؛ "
    "Redis که چند ثانیه دیرتر بالا بیاید، تا restart مصرف نمی‌شود.",
    "retry با backoff برای اتصال و راه‌اندازی consumer؛ readiness صادق و restart مصرف‌کننده پس از قطعی.")
add("SCH", "jobs/queue_consumer.py", r'payload\.get\("token"\) != self\._token', 1,
    "پیام با token نامعتبر دور ریخته می‌شود و به dead-letter نمی‌رود",
    "P1", "تأییدشده",
    "با ناسازگاری `JOB_QUEUE_TOKEN` بین scheduler و worker، job دریافت داده رد و سپس در "
    "`finally` از processing پاک می‌شود؛ فقط شمارنده بالا می‌رود و بدنه پیام برای بررسی نمی‌ماند.",
    "ثبت متادیتای امن و علت رد در dead-letter و قابل‌مقایسه کردن پیکربندی دو طرف در health.")
add("SCH", "jobs/queue_consumer.py", r"malformed message dropped", 1,
    "پیام غیرقابل‌پارس بدون dead-letter حذف می‌شود",
    "P2", "تأییدشده",
    "`json.loads` که شکست بخورد فقط log و شمارنده failed دارد و حلقه پیام را ack می‌کند؛ "
    "نام job، پارامترها و زمان انتشار برای عیب‌یابی از دست می‌رود.",
    "انتقال پیام خراب به dead-letter جداگانه با علت، زمان و شناسه (بدون نگه‌داشتن token).")
add("SCH", "jobs/queue_consumer.py", r"return self\._redis\(\) is not None", 1,
    "شرط `is_available` که شروع worker را کنترل می‌کند فقط وجود شیء client را می‌سنجد",
    "P1", "تأییدشده",
    "همین شرط در `apps/worker/consumer.py:30` تصمیم شروع worker را می‌گیرد؛ client ساخته‌شده "
    "با Redis از دست‌رفته «آماده» دیده می‌شود و LPUSH/BRPOP بعدی شکست می‌خورد.",
    "health فعال (PING) و جدا کردن «client ساخته شده» از «صف قابل استفاده».")
# DATA-106 همان DEP-016 است (redis بدون healthcheck + service_started)؛
# برای پرهیز از ردیف تکراری اینجا اضافه نمی‌شود و در پیوست به همان ردیف ارجاع داده می‌شود.
# ── Findings discovered while verifying this batch ───────────────────
add("DEP", "Dockerfile.worker", r'CMD \["python", "-m", "apps\.worker\.app"\]', 1,
    "worker image ماژولی را اجرا می‌کند که بلوک `__main__` ندارد؛ کانتینر بلافاصله خارج می‌شود",
    "P0", "تأییدشده",
    "`apps/worker/app.py` فقط کلاس تعریف می‌کند و هیچ نقطهٔ ورودی ندارد (برخلاف "
    "`apps/worker/__main__.py`). با `restart: always` این یعنی حلقهٔ restart و صفر مصرف؛ "
    "در حالت queue هیچ job دریافت داده‌ای اجرا نمی‌شود.",
    "CMD را به `python -m apps.worker` (که `__main__.py` را اجرا می‌کند) تغییر دهید یا "
    "بلوک `__main__` را به `apps/worker/app.py` اضافه کنید.")
add("SCH", "apps/worker/app.py", r"await self\.consumer\.start\(\)", 1,
    "worker هرگز کلاس‌های job را register نمی‌کند؛ dispatcher همه را «not found» می‌بیند",
    "P0", "تأییدشده",
    "`job_registry.register_module(job_definitions)` فقط در `apps/scheduler/app.py:61` صدا زده "
    "می‌شود. registry در فرآیند worker خالی است، پس `dispatch()` هر job صف‌شده را "
    "ناموجود می‌بیند، به retry می‌فرستد و در نهایت dead-letter می‌کند.",
    "register کردن definitionها در startup worker (مشترک با scheduler) و تست دود "
    "«هر نامی که scheduler منتشر می‌کند در worker قابل dispatch است».")
add("SCH", "jobs/definitions/brsapi_jobs.py", r"class BrsApiAllSymbolsJob\(_BrsApiSyncBaseJob\):", 1,
    "نام jobهای BrsApi در صف با کلید registry یکی نیست",
    "P1", "تأییدشده",
    "scheduler نام `brsapi_all_symbols` را منتشر می‌کند، اما `JobRegistry.register` کلید را "
    "از `job_class.__name__` می‌سازد (`BrsApiAllSymbolsJob`). حتی با رفع نبودِ registration، "
    "این نام‌ها هرگز تطبیق نمی‌شوند.",
    "نگاشت صریح نام صف به کلاس job (یا ثبت با نام صف) و تست تطبیق برای همهٔ jobهای BrsApi.")
add("SCH", "jobs/definitions/brsapi_jobs.py", r"class _BrsApiSyncBaseJob\(BaseJob\):", 1,
    "کلاس‌های BrsApi گیت ساعات بازار و سهمیه را دور می‌زنند",
    "P1", "تأییدشده",
    "`market_hours_only`/`codal_window` فقط در `BrsApiJobRegistry.run_job` اعمال می‌شود؛ "
    "مسیر صف به این کلاس‌ها می‌رسد و گیت را ندارد. امروز با نام‌های نامطابق پوشیده شده، "
    "اما با اصلاح نام‌ها سهمیهٔ رایگان خارج از ساعت بازار مصرف می‌شود و به HTTP 402 می‌رسد.",
    "اعمال همان گیت در لایهٔ job یا در consumer پیش از dispatch.")
