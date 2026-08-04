# 📦 schemas/ — لایه اعتبارسنجی و قرارداد داده (Pydantic)

> قراردادهای ورودی/خروجی API با **Pydantic v2**. هر چیزی که از مرز API عبور می‌کند (request body, response, query params) اینجا تعریف و اعتبارسنجی می‌شود.

---

## 📑 فهرست مطالب

- [نقش و جایگاه](#نقش-و-جایگاه)
- [ساختار پوشه‌ها](#ساختار-پوشهها)
- [Schema های مشترک (common)](#schema-های-مشترک-common)
- [Schema های API](#schema-های-api)
- [الگوهای استفاده](#الگوهای-استفاده)
- [قوانین و Convention ها](#قوانین-و-convention-ها)
- [تست‌ها](#تستها)
- [نکات تکمیلی](#نکات-تکمیلی)

---

## نقش و جایگاه

```
Client ──▶ FastAPI Endpoint ──▶ schemas/ (validation) ──▶ Service ──▶ Repository
                ▲                                                │
                └────────────── schemas/ (response) ◀────────────┘
```

- **لایه مرزی**: داده از بیرون فقط بعد از عبور از schema وارد سیستم می‌شود.
- **قرارداد OpenAPI**: FastAPI از روی همین schema ها مستندات `/docs` را می‌سازد.
- **صفر وابستگی به دیتابیس**: schema ها فقط داده‌ی خام هستند؛ نگاشت به ORM در repositories انجام می‌شود.

---

## ساختار پوشه‌ها

```
schemas/
├── common/        # Schema های پایه و مشترک بین همه endpoints
│   ├── responses.py   # ApiResponse / SuccessResponse / ErrorResponse
│   ├── pagination.py  # PaginationParams / PaginatedResponse
│   ├── filters.py     # FilterParams / DateRangeFilter
│   ├── sorting.py     # SortParams
│   └── errors.py      # AppErrorSchema / ValidationErrorSchema
├── api/           # قراردادهای REST (درخواست/پاسخ هر گروه endpoint)
│   ├── auth.py        # ورود، ثبت‌نام، توکن
│   ├── instruments.py # نمادها و ابزارها
│   ├── symbols.py     # کاتالوگ نماد
│   ├── quotes.py      # قیمت‌ها
│   ├── markets.py     # بازارها
│   ├── signals.py     # سیگنال‌ها
│   ├── funds.py       # صندوق‌ها
│   ├── ...
├── backtest/      # قراردادهای موتور بک‌تست
├── ml/            # قراردادهای پایپ‌لاین یادگیری ماشین
├── providers/     # قراردادهای تأمین‌کنندگان داده
├── admin/         # قراردادهای پنل مدیریت
└── reporting/     # قراردادهای گزارش‌گیری
```

---

## Schema های مشترک (common)

### پاسخ‌های یکپارچه (`responses.py`)

همه endpoints باید از این قالب استفاده کنند تا پاسخ API یکنواخت بماند:

```python
from schemas.common.responses import ApiResponse

# موفق
{"success": true, "data": {...}, "error": null, "message": null}

# خطا
{"success": false, "data": null, "error": {"code": "...", "details": {...}}, "message": "..."}
```

| کلاس | کاربرد |
|------|--------|
| `ApiResponse[T]` | قالب عمومی (جنریک) — `data: T \| None` |
| `SuccessResponse[T]` | پاسخ موفق با `data` الزامی |
| `ErrorResponse` | پاسخ خطا با `error` الزامی |

### صفحه‌بندی (`pagination.py`)

```python
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
```

### فیلتر و مرتب‌سازی (`filters.py`, `sorting.py`)

```python
class FilterParams(BaseModel):
    search: str | None
    is_active: bool | None
    date_range: DateRangeFilter | None   # start_date / end_date
    tags: list[str] | None
    extra_filters: dict[str, Any] | None

class SortParams(BaseModel):
    sort_by: str = "created_at"
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
```

### خطاها (`errors.py`)

```python
class AppErrorSchema(BaseModel):
    code: str = "UNKNOWN"
    message: str = "An error occurred"
    details: dict[str, Any] | None = None

class ValidationErrorSchema(AppErrorSchema):
    code: str = "VALIDATION_ERROR"
    field_errors: list[dict[str, Any]] = []
```

---

## Schema های API

### نمونه — `schemas/api/auth.py`

```python
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

### نمونه — `schemas/api/instruments.py`

```python
class InstrumentCreate(BaseModel):
    symbol: str                      # نماد الزامی
    name: str = ""
    isin: str = ""
    market_type: str = "bours"
    asset_class: str = "equity"
    ...
```

### الگوی نام‌گذاری

| نوع | الگو | مثال |
|-----|------|------|
| Request | `<Entity>Create` / `<Entity>Update` | `InstrumentCreate` |
| Response | `<Entity>Response` | `InstrumentResponse` |
| List | `<Entity>ListResponse` | `InstrumentListResponse` |
| Params | `<Domain>Params` | `PaginationParams` |

---

## الگوهای استفاده

### در endpoint ها

```python
from schemas.api.instruments import InstrumentCreate, InstrumentResponse
from schemas.common.responses import ApiResponse

@router.post("/instruments", response_model=ApiResponse[InstrumentResponse])
async def create_instrument(payload: InstrumentCreate, ...):
    ...
    return ApiResponse(success=True, data=result)
```

### تبدیل به ORM

تبدیل schema → مدل ORM **در لایه Service/Repository** انجام می‌شود، نه در endpoint:

```python
# service layer
instrument = InstrumentModel(**payload.model_dump(exclude={"id"}))
```

### اعتبارسنجی خودکار

- FastAPI به‌صورت خودکار request body را با schema اعتبارسنجی می‌کند.
- خطای اعتبارسنجی → **422** با جزئیات فیلدها.
- `Field(..., min_length=..., pattern=...)` → محدودیت در مستندات OpenAPI هم دیده می‌شود.

---

## قوانین و Convention ها

1. **هر schema باید از `BaseModel` (Pydantic v2) ارث بگیرد** — نه dataclass.
2. **مقادیر پیش‌فرض**: فیلدهای اختیاری با `= None` یا مقدار پیش‌فرض واقعی.
3. **الزامات**: فیلدهای الزامی با `Field(...)` یا `...` در نوع.
4. **جنریک‌ها**: برای پاسخ‌های تکراری از `Generic[T]` استفاده کنید (`ApiResponse[T]`).
5. **بدون منطق تجاری**: schema فقط داده و اعتبارسنجی؛ محاسبات در Service.
6. **اعتبارسنجی پیشرفته**: اگر `pattern`/`min_length` کافی نیست، از `field_validator` استفاده کنید.
7. **فایل `__init__.py`**: در `schemas/common/__init__.py` همه schema های پایه re-export شده‌اند:

```python
from schemas.common import ApiResponse, PaginatedResponse, PaginationParams, SortParams, ...
```

---

## تست‌ها

برخی تست‌ها به schema ها متکی هستند:

```bash
pytest tests/unit/test_backend_api.py tests/unit/test_endpoints.py -v
```

این تست‌ها قالب پاسخ (`ApiResponse`)، صفحه‌بندی و خطاها را از طریق HTTP واقعی بررسی می‌کنند.

---

## نکات تکمیلی

- **Backward Compat**: افزودن فیلد جدید با مقدار پیش‌فرض، پاسخ‌های قدیمی client ها را نمی‌شکند.
- **Performance**: Pydantic v2 با Rust (pydantic-core) بسیار سریع است؛ برای payloadهای سنگین از `model_dump(serialize_as_any=True)` یا `orjson` استفاده کنید.
- **جدا نگه داشتن schema دیتابیس از API**: اگر یک مدل ORM و یک schema API هم‌نام دارند، در فایل‌های جدا بمانند (`models/` vs `schemas/`).
