# صندوق‌یار — پایش هوشمند صندوق‌های سرمایه‌گذاری ایران

سامانه SaaS برای تحلیل همه صندوق‌های بازار سرمایه ایران: اهرمی، طلا، درآمد ثابت، سهامی، شاخصی، مختلط، بخشی، صندوق در صندوق، تضمین اصل سرمایه و تأمین مالی خصوصی.

هر صندوق پیشنهاد «خرید/فروش/نگهداری» + Reason Vector می‌گیرد و وضعیت ریسک، بازده، نقدشوندگی، حباب و کیفیت مدیریت را با یک نگاه نشان می‌دهد.

## ویژگی‌ها

| ماژول | شرح |
|---|---|
| **Metrics Engine** | ۵۶+ شاخص در ۵ لایه (پایه، ریسک-بازده، ساختار، کوانت-رفتاری، اختصاصی ایران) |
| **Scoring Engine** | امتیاز ۰-۱۰۰ + سیگنال ۵ سطحی + Reason Vector ۳-۵تایی + Config Versioning |
| **Peer Group** | هم‌گروه‌بندی دو محوره (نوع صندوق + باند AUM) + صدک هم‌گروه |
| **Bubble Monitor** | P/NAV لحظه‌ای + میانه هم‌گروه + پایش آربیتراژ |
| **Adapters** | فیپیران، TSETMC، کدال با Circuit Breaker + Retry + Stale Flag + Fallback chain |
| **RBAC** | نقش‌های guest/user/analyst/admin + API Key + Rate Limit |
| **Cold Start** | مدیریت «داده ناکافی» + badge «صندوق جدید» برای صندوق‌های کم‌سابقه |

## ساختار

```
apps/funds/
├── adapters/        Adapter Pattern: fipiran, tsetmc, codal + resilience
├── metrics/         لایه‌های ۱ تا ۵ (۵۶ شاخص) + Cold Start
├── scoring/         امتیازدهی وزن‌دار + جدول وزن v1.0 + Config Versioning
├── auth.py          JWT + RBAC + API Key + Rate Limiter
├── peers.py         تعریف هم‌گروه دو محوره + صدک
├── services.py      FundService: orchestration کامل
├── api.py           endpointهای FastAPI
├── models.py        جداول DB (Fund, FundMetric, BubbleSnapshot, ...)
├── schemas.py       Pydantic models + Disclaimer سه‌لایه
└── main.py          ورودی مستقل (uvicorn)
```

## اجرا

```bash
# standalone
uvicorn apps.funds.main:app --reload --port 8000

# داخل پروژه اصلی (روی مسیر /sandooghyar)
uvicorn apps.api.main:app --reload
```

مستندات: http://localhost:8000/docs

## تست

```bash
python -m pytest tests/test_funds_metrics.py tests/test_funds_adapters.py tests/test_funds_api.py -v
```

## اندپوینت‌ها

| مسیر | دسترسی |
|---|---|
| `GET /funds` | public |
| `GET /funds/{symbol}` | public |
| `GET /funds/compare?symbols=A,B` | public |
| `POST /funds/screener` | analyst+ (JWT یا API Key) |
| `GET /funds/bubble/live` | public |
| `GET /funds/health/sources` | public |
| `GET /funds/backtest/report` | analyst+ |
| `GET/POST /funds/alerts` | user+ |

## احراز هویت

- **JWT**: نقش در payload. توکن: `issue_token(sub, role)` (در تولید با RS256).
- **API Key**: فرمت `syar_{env}_{32hex}` — هش SHA-256 در DB.
- **Rate Limit**: guest 60/min/IP، user 300/min، analyst 600/min.

## Config Versioning

تغییر وزن‌ها در `scoring_config_history` ثبت می‌شود (timestamp، نویسنده، دلیل). بازتولید امتیاز تاریخی با `ScoringConfigStore.get_version(version, type_code)`.

## وزن‌دهی (v1.0)

جدول کامل ۲۰-۲۳ شاخص وزن‌دار برای هر نوع (EQ/FI/GO/LV) در `apps/funds/scoring/__init__.py`. جمع هر ستون = ۱۰۰ (normalize خودکار). هیچ «بقیه شاخص‌ها» مخفی نیست — ردیف صریح برای هر شاخص.

## Disclaimer

سه‌لایه:
1. در بدنه هر پاسخ API پیشنهادی (`disclaimer` فیلد)
2. کنار هر کارت پیشنهاد در UI
3. در صفحه اصلی و پروفایل

این پلتفرم تحلیلی است، نه مشاور سرمایه‌گذاری مجاز. مشاوره رسمی نیازمند مجوز سازمان بورس است.

## فازبندی spec

| فاز | محدوده |
|---|---|
| ۱ (MVP) | ۵ صندوق: کارین، کمند، طلا، عیار، اهرم + لایه‌های ۱-۲ + پروفایل |
| ۲ | ۱۰۰ صندوق + لایه‌های ۳-۵ + Bubble Monitor + هشدار تلگرام |
| ۳ | ۳۰۰-۵۰۰ صندوق + Screener کامل + WebSocket + Compare |
| ۴ | کالیبراسیون وزن از بک‌تست + پرتفوی کاربر (حریم خصوصی) |

## نکته داده واقعی

Adapterها با HTTP client واقعی کار می‌کنند. در dev بدون HTTP، یک seed داخلی ۸ صندوقی استفاده می‌شود تا سیستم کامل قابل اجرا باشد. اتصال واقعی: `FundService.sync_from_adapters()` یا کرون‌جاب ingestion.