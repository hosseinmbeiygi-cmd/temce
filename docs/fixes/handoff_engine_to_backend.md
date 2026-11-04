# Handoff — assistant «engine» → assistant «backend/api»

این فایل درخواست‌های تغییر در فایل‌هایی است که خارج از محدودهٔ مالکیت من
(`fix/engine`) هستند. هیچ‌کدام از فایل‌های زیر را من تغییر نداده‌ام.

## 1. `src/gold_desk/schemas.py` — `ScoreBlock.decision` باید `NO_DATA` را بپذیرد

- خط: `class ScoreBlock` → `decision: Literal["GREEN", "YELLOW", "RED"]`
- تغییر مطلوب:

  ```python
  decision: Literal["GREEN", "YELLOW", "RED", "NO_DATA"]
  ```

- دلیل: قرارداد C1 و رفع E-C5. `scorer.compute_score` وقتی
  `available_weight < MIN_SCORE_COVERAGE_WEIGHT` (۶۰ از ۱۰۰) تصمیم `NO_DATA`
  می‌دهد. `snapshot_service.build_snapshot` همان مقدار را داخل `ScoreBlock`
  می‌ریزد؛ با Literal فعلی، pydantic `ValidationError` می‌دهد و `/snapshot`
  می‌شکند. بدون این تغییر، E-C5 در production قابل استفاده نیست.
- تست پیشنهادی: `ScoreBlock(total=100, decision="NO_DATA", components=...)`
  بدون خطا ساخته شود.

## 2. `src/gold_desk/snapshot_service.py` — `_soft_check` باید `None` را بپذیرد

- خط: `def _soft_check(value: float, valid_range: tuple[float, float], name: str) -> bool:`
  و دو فراخوانی `_soft_check(bub.bubble_pct, VALID_BUBBLE_PCT_RANGE, ...)`
  (حدود خطوط ۲۳۱ و ۲۵۲)
- تغییر مطلوب: امضا به `value: float | None` و بدنه:

  ```python
  if value is None:
      return False   # چک ناممکن است؛ هشدار لازم نیست
  ```

- دلیل: قرارداد C2 و رفع E-M16. `bubbler.calc_bubble` برای `fair <= 0` دیگر
  `bubble_pct=0` نمی‌دهد بلکه `None` می‌دهد (صفر سکوتی، scorer را GREEN می‌کرد).
  `lo <= None` در `_soft_check` امروز `TypeError` می‌دهد و کل snapshot را
  می‌اندازد.
- نکته: مقدار `None` را به `AssetBlock.bubble_pct`/`implied_usd` عبور دهید
  (هر دو در schema از قبل nullable هستند).

## 3. `src/gold_desk/schemas.py` — `FundBlock.bpr` باید nullable شود

- خط: `class FundBlock` → `bpr: float`
- تغییر مطلوب: `bpr: float | None`
- دلیل: رفع E-M4. `nav_checker._fund_market_data` وقتی `sell_real_value` صفر
  یا `None` است دیگر `bpr=0` نمی‌دهد بلکه `None` (نسبت تعریف‌ناپذیر است و صفر
  باعث می‌شد کامپوننت TSETMC با وزن ۱۸ امتیاز صفر بگیرد). `snapshot_service`
  مقدار `f.bpr` را مستقیم در `FundBlock` می‌گذارد ⇒ با `float` غیرnullable،
  pydantic خطا می‌دهد.
- توجه: مقدار تجمعیِ امتیازدهی (`total_buy / total_sell` در
  `snapshot_service`) از قبل با `None` امن است و باید بدون تغییر بماند.

## 4. `src/gold_desk/api.py` — `GET /macro` باید `"affects_score": false` بدهد

- خط: بلوک `@router.get("/macro" ...)` (حدود خطوط ۱۳۶۰–۱۳۹۰)
- تغییر مطلوب: در هر دو مسیر پاسخ (با داده و بدون داده) فیلد
  `"affects_score": False` اضافه شود.
- دلیل: قرارداد C6 و رفع E-M10. تحلیل کلان اطلاعاتی است و به امتیاز ۰-۱۰۰ وصل
  نمی‌شود؛ فیلد صریح باید این را به مصرف‌کننده (UI) بگوید، وگرنه کاربر فرض
  می‌کند `macro_multiplier` در امتیاز ضرب می‌شود.

## 5. `src/gold_desk/api.py` — `ValueError` در مسیر آپشن‌ها باید 400 شود

- خط: `price_gold_option` (حدود ۶۲۷) و `protective_collar` endpoint (حدود ۶۷۳)
- تغییر مطلوب: فراخوانی `price_option(...)` / `protective_collar(...)` داخل
  `try/except ValueError as exc: raise HTTPException(400, str(exc))`
- دلیل: رفع E-L6. `years_to_expiry` حالا برای سررسید گذشته `ValueError` می‌دهد
  (قبلاً عدد تقریباً صفر برمی‌گرداند). بدون این تغییر، درخواست با تاریخ گذشته
  به 500 تبدیل می‌شود، در حالی که خطای کاربر است.

## 6. `src/gold_desk/api.py` — نمایش `NO_DATA` در پاسخ‌ها (اطلاعی)

- هیچ تغییری لازم نیست مگر جایی که `decision` را به `Literal` محدود کرده‌اید
  یا در فرانت به سه رنگ map کرده‌اید. `NO_DATA` یعنی «امتیاز محاسبه شد ولی
  پوشش داده کافی نبود»؛ عدد `total` همچنان برای نمودار معتبر است.
