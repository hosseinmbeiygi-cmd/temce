# معماری اجرایی — رفع مشکلات تأیید شده

> بر اساس اعتبارسنجی واقعی کدبیس (آگوست ۲۰۲۶)
> فقط ادعاهایی که **تأیید** شده‌اند در این نقشه لحاظ شده‌اند

---

## اولویت‌بندی (بر اساس ریسک واقعی)

### 🔴 فوری (P0) — امنیت و یکپارچگی

| # | مشکل | فایل‌ها | راه‌حل |
|---|-------|---------|--------|
| **P0-1** | SQL Injection در ۳ فایل | `data_repo.py`, `database_handler.py`, `datenrepo.py` | مهاجرت به SQLAlchemy Core با `insert().values()` + حذف f-string |
| **P0-2** | hash_api_key بدون salt | `core/security/__init__.py:66` | افزودن salt تصادفی + ذخیره `salt$hash` |
| **P0-3** | Refresh Token بدون rotation | `core/security/tokens.py`, `apps/api/endpoints/auth.py` | افزودن jti + invalidate در refresh + token family |
| **P0-4** | ۳ فایل Repository تکراری | ریشه پروژه | حذف `database_handler.py` و `datenrepo.py` + یکپارچه‌سازی در `services/` |

### 🟠 بالا (P1) — پایداری و کیفیت کد

| # | مشکل | فایل‌ها | راه‌حل |
|---|-------|---------|--------|
| **P1-1** | ۲ Container DI تکراری | `core/dependency_injection/__init__.py`, `container.py` | نگهداری فقط `container.py` + حذف تعریف تکراری |
| **P1-2** | Feature Flags ۳ لایه | `core/feature_flags/` | ساده‌سازی به یک کلاس `FeatureFlagManager` واحد |
| **P1-3** | ۲ Result تکراری | `core/typing/result.py`, `core/result.py` | نگهداری فقط `core/typing/result.py` |
| **P1-4** | ContextVar بدون reset | `core/context/__init__.py` | افزودن `reset_request_context()` + middleware در FastAPI |
| **P1-5** | EventBus بدون weakref | `core/event_bus.py` | افزودن `weakref.WeakMethod` + `unsubscribe()` |
| **P1-6** | ON CONFLICT بی‌shima | `database_handler.py:108` | افزودن شرط `WHERE EXCLUDED.updated_at > table.updated_at` |
| **P1-7** | extra="ignore" در ۱۵ Settings | `core/config/*.py` | تغییر به `extra="forbid"` در production |

### 🟡 متوسط (P2) — بهینه‌سازی

| # | مشکل | فایل‌ها | راه‌حل |
|---|-------|---------|--------|
| **P2-1** | Enumهای تکراری | `core/constants/__init__.py`, `core/enums/`, `domain/common/` | یکپارچه‌سازی در `core/enums/` |
| **P2-2** | ثابت‌های تکراری | `core/constants/` | حذف تکرارها + import مشترک |
| **P2-3** | CircuitBreaker تکراری | `core/resilience/` | نگهداری فقط `circuit_breaker.py` |

### 🔵 پایین (P3) — مستندات و ساختار

| # | مشکل | راه‌حل |
|---|-------|--------|
| **P3-1** | نبود persona کاربر | تعریف ۳ persona: خرد، نهادی، اسکالپر |
| **P3-2** | ۵۰+ اندیکاتور بدون consensus | ایجاد لایه اجماع وزنی |
| **P3-3** | نبود Arrow of Time در DB | افزودن `event_at` و `received_at` جداگانه |

---

## معماری هدف (Target Architecture)

```
┌─────────────────────────────────────────────────┐
│                  Interfaces                      │
│  (FastAPI routes, WebSocket, CLI, Scheduler)     │
├─────────────────────────────────────────────────┤
│              Application Services                │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ TradePlan │ │ Screening│ │  Risk Management  │ │
│  │  Service  │ │  Service │ │     Service       │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────┤
│                 Domain Layer                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │  Signal   │ │  Order   │ │    Position      │ │
│  │  Entity   │ │  Entity  │ │    Entity        │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────┤
│              Infrastructure Layer                │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Database  │ │  Cache   │ │    EventBus      │ │
│  │ (SQLAlch) │ │ (Redis)  │ │  (Redis Streams) │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## نقشه اجرایی ۱۲ هفته‌ای

### هفته ۱-۲: امنیت فوری
- [ ] P0-1: حذف f-string SQL Injection از ۳ فایل
- [ ] P0-2: افزودن salt به hash_api_key
- [ ] P0-3: پیاده‌سازی Refresh Token Rotation
- [ ] تست: نوشتن تست‌های امنیتی

### هفته ۳-۴: یکپارچه‌سازی Repository
- [ ] P0-4: حذف `database_handler.py` و `datenrepo.py`
- [ ] P1-6: افزودن version/updated_at به ON CONFLICT
- [ ] P1-4: افزودن middleware ContextVar cleanup
- [ ] تست: نوشتن تست‌های یکپارچه‌سازی

### هفته ۵-۶: ساده‌سازی معماری
- [ ] P1-1: حذف Container تکراری
- [ ] P1-2: ساده‌سازی Feature Flags
- [ ] P1-3: حذف Result تکراری
- [ ] P2-1: یکپارچه‌سازی Enumها
- [ ] P2-2: حذف ثابت‌های تکراری

### هفته ۷-۸: EventBus و Caching
- [ ] P1-5: افزودن weakref به EventBus
- [ ] جایگزینی EventBus با Redis Streams (اختیاری)
- [ ] پیاده‌سازی adaptive TTL برای کش
- [ ] تست: تست‌های نشت حافظه

### هفته ۹-۱۰: Trade Plan Engine
- [ ] ایجاد `services/trade_planner.py`
- [ ] پیاده‌سازی ATR, VWAP, EMA, RSI
- [ ] الگوریتم Entry (Breakout/Pullback/Gap)
- [ ] الگوریتم SL (ATR-based) و TP (Multi-target)
- [ ] تست: بک‌تست روی ۱۰ نماد

### هفته ۱۱-۱۲: لایه اجماع و نهایی‌سازی
- [ ] P3-2: لایه اجماع وزنی برای سیگنال‌ها
- [ ] P1-7: تغییر extra="forbid" در production
- [ ] مستندسازی نهایی
- [ ] تست نهایی + deployment

---

## جدول تصمیم‌گیری

| مشکل | آیا واقعاً وجود دارد؟ | آیا فوری است؟ | هزینه رفع |
|-------|----------------------|---------------|-----------|
| SQL Injection | ✅ بله | 🔴 فوری | کم |
| hash_api_key | ✅ بله | 🔴 فوری | کم |
| Refresh Token | ✅ بله | 🔴 فوری | متوسط |
| ۳ Repository تکراری | ✅ بله | 🟠 بالا | زیاد |
| Container DI تکراری | ✅ بله | 🟠 بالا | کم |
| Feature Flags ۳ لایه | ✅ بله | 🟠 بالا | کم |
| Result تکراری | ✅ بله | 🟠 بالا | کم |
| ContextVar reset | ✅ بله | 🟠 بالا | کم |
| EventBus leak | ✅ بله | 🟠 بالا | کم |
| Enum تکراری | ✅ بله | 🟡 متوسط | متوسط |
| Alembic | ✅ وجود دارد | ❌ نیازی به رفع نیست | — |
| Rate Limiter race | ❌ وجود ندارد | ❌ نیازی به رفع نیست | — |
| weekday تعطیلات | ❌ وجود ندارد | ❌ نیازی به رفع نیست | — |
| core.cache نبود | ❌ وجود دارد | ❌ نیازی به رفع نیست | — |

---

> **نتیجه نهایی:** تحلیل ۷ سطحی حدود ۶۶٪ دقیق بود. بزرگترین اشتباهات در سطوح ۵ و ۶ بود (Rate Limiter و تعطیلات). ادعاهای سطوح ۱-۳ عمدتاً درست بودند. اجرای این نقشه، پروژه را از وضعیت «ناقص اما کارآمد» به «امن و ساختاریافته» ارتقا میدهد.
