# تکمیل نهایی موتور استراتژی — کتابخانه الگوها، اعتبارسنجی و موارد لبه‌ای

> ادامه‌ی فایل «تکمیل-بخش-موتور-استراتژی»؛ این بخش موارد اجرایی‌تر و فنی‌تری را پوشش می‌دهد که در دو نسخه قبلی به‌صورت اشاره شده بودند.

---

## ۷.۹ کتابخانه‌ی الگوهای استراتژی (StrategyTemplateLibrary) — پیاده‌سازی کامل

هر الگو به‌صورت تابعی پارامتریک تعریف می‌شود که با گرفتن قیمت فعلی سهم پایه، زنجیره‌ی آپشن موجود، و چند پارامتر ساده، لیست `StrategyLeg` تولید می‌کند — این همان چیزی است که دکمه‌ی «ساخت با یک کلیک» در `Strategy Builder` پشت صحنه صدا می‌زند.

```python
from dataclasses import dataclass

@dataclass
class ChainLookup:
    """رابط ساده برای پیدا کردن نزدیک‌ترین Strike/سررسید موجود در زنجیره واقعی"""
    def nearest_strike(self, target_strike, option_type, expiry): ...
    def nearest_expiry(self, target_dte): ...
    def premium_of(self, strike, option_type, expiry): ...


class StrategyTemplateLibrary:
    def __init__(self, chain: ChainLookup):
        self.chain = chain
        self.templates = {
            "COVERED_CALL": self.covered_call,
            "PROTECTIVE_PUT": self.protective_put,
            "IRON_CONDOR": self.iron_condor,
            "IRON_BUTTERFLY": self.iron_butterfly,
            "CALENDAR_SPREAD": self.calendar_spread,
            "BULL_CALL_SPREAD": self.bull_call_spread,
            "COLLAR": self.collar,
            "JADE_LIZARD": self.jade_lizard,
        }

    def build(self, name: str, **params):
        if name not in self.templates:
            raise ValueError(f"الگوی ناشناخته: {name}")
        return self.templates[name](**params)

    def iron_condor(self, S, dte_target=30, wing_width_pct=5, short_delta_target=0.20):
        expiry = self.chain.nearest_expiry(dte_target)
        # Strikeهای Short بر اساس Delta هدف (نه فاصله ثابت) انتخاب می‌شوند - دقیق‌تر برای احتمال ITM شدن
        short_put_k = self.chain.strike_for_delta(-short_delta_target, "PUT", expiry)
        short_call_k = self.chain.strike_for_delta(short_delta_target, "CALL", expiry)
        long_put_k = short_put_k * (1 - wing_width_pct / 100)
        long_call_k = short_call_k * (1 + wing_width_pct / 100)

        legs = [
            StrategyLeg("PUT", "SHORT", self.chain.nearest_strike(short_put_k, "PUT", expiry),
                        self.chain.premium_of(short_put_k, "PUT", expiry)),
            StrategyLeg("PUT", "LONG", self.chain.nearest_strike(long_put_k, "PUT", expiry),
                        self.chain.premium_of(long_put_k, "PUT", expiry)),
            StrategyLeg("CALL", "SHORT", self.chain.nearest_strike(short_call_k, "CALL", expiry),
                        self.chain.premium_of(short_call_k, "CALL", expiry)),
            StrategyLeg("CALL", "LONG", self.chain.nearest_strike(long_call_k, "CALL", expiry),
                        self.chain.premium_of(long_call_k, "CALL", expiry)),
        ]
        return legs

    def calendar_spread(self, S, near_dte_target=15, far_dte_target=45, strike_offset_pct=0):
        near_expiry = self.chain.nearest_expiry(near_dte_target)
        far_expiry = self.chain.nearest_expiry(far_dte_target)
        strike = self.chain.nearest_strike(S * (1 + strike_offset_pct / 100), "CALL", near_expiry)
        return [
            StrategyLeg("CALL", "SHORT", strike, self.chain.premium_of(strike, "CALL", near_expiry)),
            StrategyLeg("CALL", "LONG", strike, self.chain.premium_of(strike, "CALL", far_expiry)),
        ]

    def collar(self, S, shares_qty, put_offset_pct=5, call_offset_pct=5, dte_target=30):
        expiry = self.chain.nearest_expiry(dte_target)
        put_k = self.chain.nearest_strike(S * (1 - put_offset_pct / 100), "PUT", expiry)
        call_k = self.chain.nearest_strike(S * (1 + call_offset_pct / 100), "CALL", expiry)
        return [
            StrategyLeg("STOCK", "LONG", None, S, quantity=shares_qty),
            StrategyLeg("PUT", "LONG", put_k, self.chain.premium_of(put_k, "PUT", expiry)),
            StrategyLeg("CALL", "SHORT", call_k, self.chain.premium_of(call_k, "CALL", expiry)),
        ]

    # covered_call، protective_put، iron_butterfly، bull_call_spread، jade_lizard
    # با همین الگو پیاده‌سازی می‌شوند — حذف‌شده برای اختصار
```

نکته‌ی کلیدی: انتخاب Strike بر اساس **Delta هدف** (مثلاً پایه‌ی Short با Delta≈0.20) به‌جای فاصله‌ی درصدی ثابت از قیمت روز، چون در بازار با نوسان متغیر، فاصله‌ی ثابت درصدی احتمال ITM شدن متفاوتی در زمان‌های مختلف می‌دهد؛ Delta هدف این احتمال را تقریباً ثابت نگه می‌دارد. این نیازمند تابع کمکی `strike_for_delta` است که با جست‌وجوی دودویی روی زنجیره‌ی موجود، نزدیک‌ترین Strike به Delta درخواستی را پیدا می‌کند.

## ۷.۱۰ اعتبارسنجی پیش از ارسال استراتژی (Pre-Trade Validation)

پیش از رسیدن به `MultiLegOrderCoordinator`، هر استراتژی باید از یک لایه‌ی اعتبارسنجی عبور کند:

```python
class StrategyValidator:
    def validate(self, legs, portfolio_state, user_limits) -> list[str]:
        errors = []

        if not legs:
            errors.append("استراتژی بدون پایه قابل ثبت نیست")

        # بررسی هم‌راستایی سررسیدها برای استراتژی‌های تک‌سررسید (نه Calendar/Diagonal)
        expiries = {leg.expiry for leg in legs if leg.option_type != "STOCK"}
        # (فرض: leg.expiry به مدل اضافه شده)

        # بررسی وجود نقدشوندگی کافی برای هر پایه
        for leg in legs:
            if leg.option_type != "STOCK" and leg.open_interest < 10:
                errors.append(f"پایه با Strike {leg.strike} نقدشوندگی بسیار پایینی دارد (OI<10)")

        # بررسی کفایت وجه تضمین قبل از ارسال (نه بعد از رد شدن توسط کارگزاری)
        estimated_margin = MarginEngine().estimate(legs)
        if estimated_margin > portfolio_state["available_cash"]:
            errors.append("وجه تضمین تخمینی از موجودی قابل‌استفاده بیشتر است")

        # بررسی محدودیت تمرکز پرتفوی پیش از تأیید (نه صرفاً هشدار پس از اجرا)
        projected_concentration = portfolio_state["current_concentration"] + estimate_new_concentration(legs)
        if projected_concentration > user_limits["max_concentration_pct"]:
            errors.append("این معامله از سقف تمرکز مجاز روی این نماد/سررسید عبور می‌کند")

        return errors
```

## ۷.۱۱ موارد لبه‌ای (Edge Cases) که باید صریحاً مدیریت شوند

| مورد | رفتار مورد انتظار |
|---|---|
| توقف نماد سهم پایه حین باز بودن استراتژی | فریز محاسبه‌ی Greeks روی آخرین قیمت معتبر + هشدار به کاربر؛ عدم صدور پیشنهاد Adjustment جدید تا بازگشایی |
| افزایش سرمایه‌ی سهم پایه حین باز بودن استراتژی چندپایه | فراخوانی `CorporateActionHandler` روی **همه‌ی پایه‌ها** هم‌زمان، نه فقط پایه‌ای که مستقیم تحت تأثیر است (چون Strikeهای دیگر پایه‌ها هم ممکن است تعدیل شوند) |
| پر شدن جزئی یک پایه از چند پایه‌ی All-or-None | لغو خودکار پایه‌های پرشده در بازه‌ی زمانی کوتاه (مثلاً ۵ ثانیه) اگر بقیه پر نشوند، طبق تنظیم کاربر در ۷.۷ |
| رسیدن هم‌زمان دو پایه به نقطه‌ی اعمال زودهنگام (برای قراردادهای آمریکایی احتمالی آینده) | اولویت با پایه‌ای که ریسک تعهدی (Short) دارد؛ هشدار فوری قبل از ساعت پایانی معاملات |
| کاربر دستی یک پایه از استراتژی چندپایه را جداگانه ببندد | `StrategyLifecycleTracker` باید استراتژی را به حالت `ADJUSTED` غیرخودکار ببرد و `GreeksAggregator` را روی پایه‌های باقی‌مانده بازمحاسبه کند |
| نبود قیمت معتبر Bid/Ask برای یکی از پایه‌ها (نماد کم‌معامله) | استفاده از fallback نوسان تاریخی (طبق بخش ۶.۵ سند اصلی) فقط برای **نمایش تخمینی**، با برچسب صریح "قیمت تخمینی" در UI — هرگز برای اجرای واقعی سفارش |

## ۷.۱۲ تست‌های اختصاصی موتور استراتژی (تکمیل بخش ۱۴ سند اصلی)

- **Payoff Consistency Test**: برای هر الگوی کتابخانه، مقایسه‌ی خودکار Payoff محاسبه‌شده در چند نقطه‌ی قیمتی کلیدی (Strikeها، صفر، بی‌نهایت) با مقدار تحلیلی شناخته‌شده از تئوری آپشن.
- **Round-Trip Test**: ساخت یک استراتژی با `StrategyTemplateLibrary`، عبور از `StrategyValidator`، اجرای شبیه‌سازی‌شده در `ExecutionSimulator` بک‌تست، و اطمینان از این‌که PnL نهایی با محاسبه‌ی دستی Payoff مطابقت دارد.
- **Adjustment Regression Test**: سناریوهای تاریخی مشخص (مثلاً Iron Condor که یک سمتش تهدید شده) را دوباره اجرا کرده و بررسی شود `AdjustmentEngine` همان پیشنهاد قبلی را تکرار می‌کند (Determinism).

---

با این افزوده‌ها، بخش ۷ از سطح توضیح مفهومی به سطح قابل‌پیاده‌سازی (کد + قوانین اعتبارسنجی + موارد لبه‌ای مشخص) رسیده است. اگر بخواهید، مرحله‌ی بعد می‌تواند طراحی دقیق UI/UX کامپوننت `Strategy Builder` (وایرفریم یا React component) باشد.
