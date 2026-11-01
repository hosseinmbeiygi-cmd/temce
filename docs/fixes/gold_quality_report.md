# گزارش کیفیت کد — GoldDesk (temce)

## ۱. خلاصه اجرایی

| بخش | نمره (۱–۵) | دلیل یک‌خطی |
|---|---|---|
| ساختار | 2 | `api.py` 1962 خط، God module |
| تایپ | 2 | mypy: Missing type arguments for generic "dict"/"list" متعدد |
| خطا | 2 | ~95 مورد except Exception |
| تست | 3 | tests/gold_desk موجود؛ پوشش اندازه‌گیری نشد کامل |
| فرانت | 2 | tsc/eslint timeout |
| تمیزی | 3 | Any=82، noqa=39، type:ignore=6 |

## ۲. جدول یافته‌ها (نمونه)

| شناسه | شدت | مکان | شواهد | چرا مهم | پیشنهاد | تلاش |
|---|---|---|---|---|---|---|
| F1 | High | src/gold_desk/api.py | 1962 خط، 58 route | God module | شکستن | L |
| F2 | High | src/gold_desk/mypy | Missing type arguments for "dict" | تایپ ضعیف | type args | M |
| F3 | High | src/gold_desk/api.py:1444-1448 | raise HTTPException(..., str(exc)) | leakage | sanitize | S |
| F4 | Medium | src/gold_desk/chat.py:93 | process gets multiple values for user_id | باگ | بررسی | S |
| F5 | Medium | src/gold_desk/constants.py:60-64 | dict-item type mismatch | تایپ | اصلاح | S |

## ۳. ۱۰ بهبود سریع
1. sanitize HTTPException str(exc) در api.py:1444-1448
2. رفع chat.py:93
3. اضافه type args به dict/list
4. ...

## ۵. خوب‌ها
- ruff: All checks passed
- public funcs missing return annotation فقط 2 از 279

## ۶. پیوست
### ruff
```
All checks passed!
```
### mypy
خطاهای متعدد (dict type-arg، no-untyped-def، dict-item، call-arg)

### except Exception
95+ مورد (فهرست در گزارش کامل)

### HTTPException str(exc)
api.py:1444, :1446, :1448

## ۷. محدودیت‌ها
- pytest/cov کامل اجرا نشد (timeout)
- frontend tsc/eslint/vitest timeout
- vulture نصب نیست
"