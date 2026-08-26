# گزارش بهینه‌سازی سرعت پردازش TSETMC

## هدف
این گزارش برای رساندن پایپلاین فعلی تحلیل TSETMC از حالت `pandas-heavy` به یک معماری سریع‌تر و تولیدی تهیه شده است.  
تمرکز اصلی روی این است که:

- parse داده سریع‌تر شود
- feature computation از `DataFrame`های موقت جدا شود
- محاسبات تکراری حذف شوند
- برای 800 نماد، پردازش batch به حداقل overhead برسد

## جمع‌بندی اجرایی
در کد فعلی، گلوگاه اصلی خودِ فرمول‌ها نیستند، بلکه این‌ها هستند:

1. `json.loads` در مسیر ingest و parser
2. `DataFrame.copy()` و ساخت آبجکت‌های مکرر
3. lookupهای تکراری روی dict/DataFrame
4. rolling/loopهای پایتونی در feature builder
5. تبدیل مداوم بین dict، list، DataFrame و JSON

نتیجه:  
برای `real-time`، مسیر مناسب این است:

`raw bytes -> orjson -> numpy buffer -> numba kernel -> sparse output`

نه:

`raw bytes -> dict -> pandas -> copy -> rolling -> dict`

## وضعیت فعلی کد

### 1) parse
در `brsapi/client.py` و `ingestion/parser/tsetmc_parsers.py` از `json.loads` استفاده شده است.  
در چرخه پرتکرار بازار، این یکی از اولین گلوگاه‌هاست.

### 2) compute
در `services/feature_engine.py` محاسبات چند بلوک به‌صورت dict-based انجام می‌شود.  
این ساختار برای خوانایی خوب است، اما برای latency بالا مناسب نیست.

### 3) ML features
در `ml/features/microstructure_features.py` همچنان `DataFrame.copy()` و rollingهای pandas دیده می‌شود.  
این روش برای batch آفلاین خوب است، اما برای hot path کند است.

## معماری پیشنهادی

### لایه 1: Decode سریع
جایگزین:

```python
import orjson

data = orjson.loads(raw_bytes)
```

به‌جای `json.loads`.

مزیت:
- decode سریع‌تر
- GC کمتر
- مناسب ingest پرتکرار

### لایه 2: نرمال‌سازی به buffer عددی
به‌جای ساخت `DataFrame` در شروع، داده را به یک buffer عددی ثابت ببرید.

پیشنهاد:

- آرایه `float64` یا `float32`
- ستون‌ها با ترتیب ثابت
- mapping نماد به index
- buffer با ابعاد ثابت مثل `(800, N_FEATURES)`

### لایه 3: Feature Kernel
محاسبات سنگین را به توابع Numba منتقل کنید:

```python
from numba import njit
```

ویژگی‌ها:
- `@njit(cache=True, fastmath=True)`
- آرایه contiguous
- بدون dict
- بدون `DataFrame`

### لایه 4: State Store
برای ویژگی‌های delta و rolling:

- آخرین snapshot هر نماد را در RAM نگه دارید
- rolling window را در آرایه ring-buffer یا Redis state ذخیره کنید
- محاسبه delta را فقط روی تغییرات انجام دهید

### لایه 5: Output
فقط خروجی نهایی را دوباره به `dict` یا `DataFrame` تبدیل کنید.  
این تبدیل باید آخرین مرحله باشد، نه مرحله میانی.

## اولویت‌های بهینه‌سازی

### اولویت 1: حذف parse کند
در این فایل‌ها:

- `brsapi/client.py`
- `ingestion/parser/tsetmc_parsers.py`
- `ingestion/sources/tsetmc.py`

از `orjson.loads` استفاده شود.

### اولویت 2: حذف `DataFrame.copy()` در hot path
در `ml/features/*`، فقط جایی از pandas استفاده شود که batch آفلاین است.  
برای real-time:

- `numpy.ndarray`
- `numba`
- `np.divide(..., out=..., where=...)`

### اولویت 3: precompute
ثابت‌هایی مثل وزن‌ها، mapping ستون‌ها، و آستانه‌های score باید از قبل ساخته شوند.

### اولویت 4: in-place update
به‌جای ساخت شیء جدید در هر tick:

- buffer را یک‌بار بسازید
- فقط مقدارها را بازنویسی کنید

### اولویت 5: warm-up
در startup، kernelهای Numba را یک بار با داده dummy warm کنید.

## پیشنهاد ساختار ماژول

```text
ml/
  features/
    tsetmc_fast/
      __init__.py
      schema.py
      buffers.py
      kernels.py
      score.py
      pipeline.py
      serializer.py
```

### نقش فایل‌ها

- `schema.py`: ترتیب ستون‌ها و dtypeها
- `buffers.py`: buffer ثابت و state per symbol
- `kernels.py`: توابع Numba
- `score.py`: Omni Alpha Score
- `pipeline.py`: orchestration
- `serializer.py`: خروجی سبک برای API یا DB

## نمونه طراحی سریع

### buffer

```python
import numpy as np

N_SYMBOLS = 800
N_FEATURES = 64

feature_buffer = np.zeros((N_SYMBOLS, N_FEATURES), dtype=np.float64)
```

### kernel

```python
from numba import njit
import numpy as np

@njit(cache=True, fastmath=True)
def compute_obi_5(qd1, qd2, qd3, qd4, qd5, qo1, qo2, qo3, qo4, qo5):
    bid = qd1 + qd2 + qd3 + qd4 + qd5
    ask = qo1 + qo2 + qo3 + qo4 + qo5
    total = bid + ask
    if total <= 0.0:
        return 0.0
    return (bid - ask) / total
```

### safe divide

```python
@njit(cache=True, fastmath=True)
def safe_div(a, b):
    if b == 0.0:
        return 0.0
    return a / b
```

## چه چیزهایی باید از hot path حذف شوند

- `DataFrame.copy()`
- `rolling()` داخل حلقه real-time
- `sum(df[f"..."])` روی ستون‌ها برای هر tick
- تبدیل مکرر `dict <-> DataFrame`
- ساخت featureهای غیرضروری قبل از فیلتر اولیه

## کاربرد عملی برای برنامه شما

### مسیر پیشنهادی در runtime

1. fetch raw payload
2. decode با `orjson`
3. normalize به buffer
4. compute feature kernel
5. score
6. filter
7. serialize فقط برای top candidates

### متریک‌های هدف

- ingest decode: کمترین overhead ممکن
- feature kernel: زیر 1ms برای batch 800 نماد در صورت array-based بودن
- خروجی نهایی: فقط برای نمادهای منتخب

## نکته مهم درباره HFT
رسیدن به latency میکروثانیه‌ای در کل زنجیره Python + شبکه + API معمولاً واقع‌بینانه نیست.  
چیزی که واقعاً قابل دستیابی است:

- decode سریع
- compute زیر میلی‌ثانیه
- کاهش شدید allocation
- حذف pandas از مسیر داغ

اگر واقعاً microsecond-level می‌خواهید، بخش compute باید نزدیک‌تر به:

- Numba
- Cython
- Rust extension
- یا سرویس جداگانه in-process شود

## پیشنهاد نهایی

برای این پروژه، بهترین ترکیب این است:

- `orjson` برای parse
- `numpy` برای buffer
- `numba` برای kernel
- `pandas` فقط برای batch/offline
- `DataFrame` فقط در خروجی‌های غیرحساس به latency

## مرحله بعد
اگر این مسیر را تایید کنید، نسخه بعدی گزارش می‌تواند شامل این سه بخش باشد:

1. کد کامل `TsetmcFastFeatureEngine`
2. اسکلت `Omni Alpha Score` برداری
3. تست‌های benchmark برای مقایسه pandas vs numba

## ضمیمه: قرارداد `type` و جدول فیلدهای پایه API

پارامتر `type` اختیاری است و اگر ارسال نشود، مقدار پیش‌فرض آن `1` است.

### نگاشت نوع دارایی

| type | توضیح |
|---|---|
| `1` | سهام بورس و فرابورس + صندوق‌های ETF + حق‌تقدم |
| `2` | بورس کالا، فقط نمادهای موجود در TSETMC |
| `3` | آتی |
| `4` | اوراق بدهی |
| `5` | تسهیلات مسکن |

### جدول راهنمای فیلدهای پایه

| متغیر | توضیح | مثال |
|---|---|---|
| `time` | زمان آخرین اطلاعات قیمت | `12:30:01` |
| `l18` | نماد | `شتران` |
| `l30` | نام شرکت | `پالايش نفت تهران` |
| `isin` | شناسه بین‌المللی نماد | `IRO1PTEH0001` |
| `id` | شناسه داخلی نماد | `51617145873056483` |
| `cs` | گروه صنعت | `فراورده‌های نفتی، کک و سوخت هسته‌ای` |
| `cs_id` | شناسه گروه صنعت | `14` |
| `z` | تعداد سهام | `50000000000` |
| `bvol` | حجم مبنا | `275000000000` |

### نکته تحلیلی

- `time` برای سنجش تازگی داده و هم‌ترازی snapshotها کلیدی است.
- `l18` و `l30` برای جست‌وجو، نمایش و اتصال به منابع بیرونی مناسب‌اند.
- `isin` و `id` باید به‌عنوان کلیدهای پایدار ذخیره شوند.
- `cs` و `cs_id` پایه تحلیل صنعت و مقایسه هم‌گروهی هستند.
