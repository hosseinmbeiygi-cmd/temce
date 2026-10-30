"""Seventh batch of hand-verified findings (jobs + Redis queue)."""

F = []


def add(cat, file, anchor, occ, title, sev, status, impact, fix):
    F.append(dict(cat=cat, file=file, anchor=anchor, occ=occ, title=title,
                  sev=sev, status=status, impact=impact, fix=fix))


add("SCH", "jobs/definitions/market_data_jobs.py", r'data=\{"ingested": count, "source": source\}', 1,
    "QuoteIngestionJob حتی با شکست همه نمادها موفق گزارش می‌شود",
    "P1", "تأییدشده",
    "داشبورد jobها سبز می‌ماند در حالی که هیچ داده‌ای وارد نشده؛ retry و هشدار فعال نمی‌شوند.",
    "ثبت requested/succeeded/failed و شکست صریح در شکست کامل.")
add("SCH", "jobs/definitions/market_data_jobs.py", r'data=\{"processed": count, "symbols": len\(symbols\)\}', 1,
    "HistoricalDataJob همیشه موفق است، حتی وقتی ingest_historical همیشه fail می‌دهد",
    "P1", "تأییدشده",
    "این job با تابع پیاده‌سازی‌نشده ترکیب شده و برای همیشه سبز است؛ هیچ تاریخچه‌ای وارد نمی‌شود ولی کسی خبردار نمی‌شود.",
    "حذف job یا disabled صریح تا پیاده‌سازی؛ گزارش شکست.")
add("SCH", "jobs/definitions/market_data_jobs.py", r'data=\{"quotes": len\(results\)\}', 1,
    "RealtimeQuoteJob نبود داده را موفقیت تلقی می‌کند",
    "P2", "تأییدشده",
    "شکست منبع یا پاسخ خالی در وضعیت job دیده نمی‌شود.",
    "تفکیک موفق/خالی/ناموفق.")
add("SCH", "jobs/definitions/sync_jobs.py", r"indices_count = idx_report\.items_count", 1,
    "SyncQuotesJob وضعیت success گزارش‌های sync را بررسی نمی‌کند",
    "P0", "تأییدشده",
    "شکست دریافت نمادها یا شاخص‌ها به‌عنوان اجرای موفق ثبت می‌شود؛ همان مسیری که snapshot را تازه می‌کند.",
    "بررسی success/error هر دو گزارش و شکست جزئی صریح.")
add("SCH", "jobs/queue_consumer.py", r"await self\._ack_message\(client, raw\)", 1,
    "ack پیام در finally انجام می‌شود، حتی وقتی مدیریت خطا/retry نیمه‌کاره مانده",
    "P0", "تأییدشده",
    "پیام از processing حذف می‌شود بدون نتیجه نهایی؛ job دریافت داده دیگر خودکار تکرار نمی‌شود.",
    "ack فقط پس از نتیجه قطعی (موفق/requeued/dead-lettered).")
add("SCH", "jobs/queue_consumer.py", r"result = await client\.brpop\(self\._queue_name, self\._poll_timeout\)", 1,
    "مسیر جایگزین BRPOP پیام را به لیست processing منتقل نمی‌کند",
    "P1", "تأییدشده",
    "اگر worker بعد از BRPOP بمیرد، پیام از صف خارج شده و recovery (که فقط processing را می‌گردد) آن را پیدا نمی‌کند.",
    "الزام BRPOPLPUSH/BLMOVE یا fallback durable.")
add("SCH", "jobs/queue_consumer.py", r"await client\.lpush\(self\._queue_name, json\.dumps\(payload", 1,
    "شکست requeue مانع ack نمی‌شود",
    "P0", "تأییدشده",
    "اگر lpush در زمان retry شکست بخورد، پیام اصلی هم از processing حذف می‌شود و job برای همیشه از دست می‌رود.",
    "تأیید موفقیت enqueue پیش از ack و نگه‌داشتن پیام در خطا.")
add("SCH", "jobs/queue_publisher.py", r"return self\._redis\(\) is not None", 1,
    "is_available فقط وجود client را می‌سنجد، نه سلامت صف",
    "P2", "تأییدشده",
    "Redis قطع یا بدون مجوز، «queue mode قابل استفاده» تلقی می‌شود و تصمیم fallback را خراب می‌کند.",
    "health واقعی (ping + مجوز LPUSH/BRPOP).")
add("SCH", "jobs/definitions/sync_jobs.py", r'return \{"status": "completed", "source": source, "count": 0\}', 1,
    "توابع legacy دریافت داده، completed با count=0 برمی‌گردانند",
    "P2", "تأییدشده",
    "هر call-site قدیمی موفقیت کاذب می‌بیند بدون اینکه داده‌ای وارد شود.",
    "حذف یا پاسخ deprecated/unsupported.")
