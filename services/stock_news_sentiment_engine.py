"""🧠 Persian Financial News Sentiment Engine — NLP سنتیمنت واقعی بازار سرمایه ایران.

بخش ۹.۳ و تب ۶ معماری Enterprise سهام:
  - تحلیل احساسات اخبار فارسی مالی با دیکشنری تخصصی + کلیدواژه‌های رگولاتوری
  - تشخیص رویدادهای پرتاثیر: توقف/بازگشایی نماد، تغییر نرخ خوراک، معافیت مالیاتی،
    افزایش سرمایه/آورده، تحریم، تسعیر ارز، مجمع، قیمت‌گذاری دستوری ...
  - امتیاز سنتیمنت [-1, +1] با تضعیف/تشدیدکننده‌ها و مکث منفی
  - تگ تأثیر رگولاتوری (impact_tag) برای هر خبر + تخمین تأثیر بر EPS

بدون وابستگی به سرویس خارجی؛ همیشه deterministic و قابل تست.

قاعده: هیچ کلیدی هاردکد نمی‌شود؛ فقط قواعد زبانی.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

# ── دیکشنری سنتیمنت فارسی مالی (وزن: -1..+1) ────────────────────────────────

SENTIMENT_LEXICON: dict[str, float] = {
    # مثبت قوی
    "جهش": 1.0, "جهشی": 1.0, "رکورد": 0.9, "رکوردزنی": 1.0, "افزایش سرمایه": 0.6,
    "سودآور": 0.8, "سودسازی": 0.8, "حاشیه سود بالا": 0.9,
    # مثبت
    "افزایش": 0.4, "رشد": 0.5, "بهبود": 0.5, "صعود": 0.5, "صعودی": 0.5,
    "مثبت": 0.4, "تقویت": 0.4, "قوی": 0.4, "مطلوب": 0.3, "مناسب": 0.2,
    "رونق": 0.5, "توسعه": 0.3, "پیشرفت": 0.4, "موفق": 0.4, "موفقیت": 0.5,
    "بازگشایی": 0.7, "دریافت": 0.3, "اخذ": 0.3, "کسب": 0.4, "برنده": 0.6,
    "مناقصه": 0.2, "قرارداد": 0.2, "سفارش": 0.2, "تأیید": 0.3, "تایید": 0.3,
    "معافیت": 0.6, "معافیت مالیاتی": 0.9, "تسعیر": 0.4, "ارزیابی مجدد": 0.5,
    "تجدید ارزیابی": 0.5, "پیش‌بینی": 0.1, "جبران": 0.3, "احیا": 0.4,
    "تخصیص": 0.3, "افتتاح": 0.3, "راه‌اندازی": 0.4, "تولید": 0.2,
    "بالا": 0.2, "خوش‌بینانه": 0.5, "امیدبخش": 0.5, "حل": 0.4, "رفع": 0.3,
    # منفی قوی
    "توقف": -1.0, "متوقف": -1.0, "توقف نماد": -1.0, "سرمایه‌گذاری ممنوع": -0.9,
    "شکست": -0.6, "ضرر": -0.7, "زیان": -0.8, "زیان‌ده": -0.9, "ضررده": -0.8,
    "ورشکستگی": -1.0, "ورشکست": -1.0, "تحریم": -0.8, "جریمه": -0.7,
    "مجازات": -0.8, "ممنوع": -0.8, "ممنوعیت": -0.8, "لغو": -0.6, "ابطال": -0.7,
    "فسخ": -0.6, "برکناری": -0.5, "استعفا": -0.5, "اخلال": -0.6,
    # منفی
    "کاهش": -0.4, "افت": -0.5, "سقوط": -0.8, "نزول": -0.5, "نزولی": -0.5,
    "منفی": -0.4, "ضعیف": -0.4, "تضعیف": -0.5, "ضعف": -0.4,
    "نامطلوب": -0.4, "نامناسب": -0.3, "نگرانی": -0.4, "نگران": -0.4,
    "بحران": -0.7, "تهدید": -0.5, "خطر": -0.5, "ریسک": -0.3, "تورم": -0.2,
    "رکود": -0.5, "رکودی": -0.5, "کاهش سرمایه": -0.7, "انحلال": -0.9,
    "تعدیل نزولی": -0.8, "پیش‌بینی ضرر": -0.9, "قاون": -0.6,
    "تعلیق": -0.7, "تعلیق نماد": -1.0, "بلوکه": -0.3, "بدهی": -0.2,
    "مدیون": -0.5, "چک برگشتی": -0.6, "تبعیض": -0.2, "تأخیر": -0.3,
    "تاخیر": -0.3, "انباشت": -0.3, "کسری": -0.4, "کاهش قیمت": -0.5,
    "قیمت‌گذاری دستوری": -0.5, "ذخیره": -0.2, "موضوعیت": -0.1,
}

# شدت‌بخش‌ها (تشدید)
INTENSIFIERS = {"بسیار": 1.5, "شدید": 1.5, "شدیداً": 1.6, "قابل توجه": 1.3, "فاحش": 1.5, "عمده": 1.2}
# تضعیف‌کننده‌های «قبل از عبارت» (نفی پیشین)
NEGATORS = {"نمی": 1.0, "عدم": -0.8, "خیر": 1.0, "نه": 1.0, "لغو": 1.0, "انصراف": 1.0}
# نقیض‌های «بعد از عبارت» (نفی پسین): «سودآور نیست»، «رشد نبود» ...
POST_NEGATORS = ("نیست", "نیستند", "نبود", "نبودند", "نشد", "نخواهد", "نشود")

# ── کلیدواژه‌های رگولاتوری بازار ایران → impact_tag ────────────────────────

REGULATORY_PATTERNS: list[tuple[str, str, float]] = [
    # (tag, الگو regex، تأثیر پایه بر سنتیمنت)
    ("halting", r"توقف\s+نماد|متوقف\s+شدن\s+نماد|متوقف\s+شد|توقف\s+سپرده|معاملات\s+نماد\s+متوقف", -0.9),
    ("halting", r"بازگشایی\s+نماد|بازگشایی\s+سهم", 0.6),
    ("feed_rate", r"نرخ\s+خوراک|گاز\s+خوراک|قیمت\s+گاز|الکتروسیته|برق\s+مصرفی", -0.2),
    ("tax", r"معافیت\s+مالیاتی|مالیات\s+عملکرد|بخشنامه\s+مالیاتی", 0.5),
    ("dilution", r"افزایش\s+سرمایه\s+(از\s+)?(آورده|مازاد|سود)|حق\s+تقدم", 0.1),
    ("sanction", r"تحریم|ممنوعیت\s+صادرات|ممنوعیت\s+واردات", -0.7),
    ("fx", r"تسعیر\s+ارز|نرخ\s+دلار|ارز\s+ترجیحی|ارز\s+نیما|دلار\s+آزاد", 0.2),
    ("assembly", r"مجمع\s+عمومی|مجمع\s+عادی|مجمع\s+فوق‌العاده", 0.1),
    ("price_control", r"قیمت‌گذاری\s+دستوری|گروه\s+کاریشناسی|عواید\s+دستوری", -0.4),
    ("listing", r"پذیرش\s+در\s+بورس|عرضه\s+اولیه", 0.3),
    ("dividend", r"تقسیم\s+سود|DPS|سود\s+نقدی", 0.3),
    ("regime", r"دامنه\s+نوسان|حجم\s+مبنا|سقف\s+قیمت|کف\s+قیمت", 0.0),
]

# ── الگوی اعداد فارسی ────────────────────────────────────────────────────────

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# محدوده حروف فارسی/عربی برای «مرز کلمه» — جلوگیری از مچ‌شدن «افت» داخل «یافت»
_PERSIAN_LETTER = r"[\u0621-\u064A\u0660-\u0669\u066E-\u06D3\u06FA-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]"


def _term_pattern(term: str) -> re.Pattern[str]:
    """الگوی تطبیق عبارت با مرز کلمه فارسی (نه داخل یک کلمه دیگر)."""
    return re.compile(
        f"(?<!{_PERSIAN_LETTER})" + re.escape(term) + f"(?!{_PERSIAN_LETTER})"
    )


@dataclass
class SentimentResult:
    """خروجی استاندارد موتور سنتیمنت."""

    sentiment: str = "neutral"          # positive | neutral | negative
    score: float = 0.0                  # -1..+1
    confidence: float = 0.0             # 0..1 — بر اساس تعداد شواهد
    impact_tag: str | None = None       # halting | tax | fx | ...
    regulatory_hits: list[dict[str, Any]] = field(default_factory=list)
    positive_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)
    eps_impact_hint: float = 0.0        # -1..+1 — تخمین کیفی تأثیر بر EPS

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentiment": self.sentiment,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 3),
            "impact_tag": self.impact_tag,
            "regulatory_hits": self.regulatory_hits,
            "positive_terms": self.positive_terms,
            "negative_terms": self.negative_terms,
            "eps_impact_hint": round(self.eps_impact_hint, 3),
        }


class PersianNewsSentimentEngine:
    """موتور تحلیل احساسات فارسی مالی — keyword-based با قواعد رگولاتوری."""

    def __init__(self) -> None:
        # عبارت‌های چندکلمه‌ای باید قبل از تک‌کلمه‌ها بررسی شوند + کامپایل با مرز کلمه
        self._compiled: list[tuple[re.Pattern[str], str, float]] = [
            (_term_pattern(term), term, weight)
            for term, weight in sorted(
                SENTIMENT_LEXICON.items(), key=lambda kv: len(kv[0]), reverse=True
            )
        ]

    # ── API اصلی ──

    def analyze(self, text: str) -> SentimentResult:
        """تحلیل سنتیمنت یک متن خبر/اطلاعیه."""
        result = SentimentResult()
        if not text or not text.strip():
            return result

        normalized = self._normalize(text)

        pos_score, neg_score = self._scan_lexicon(normalized, result)
        reg_score = self._scan_regulatory(normalized, result)

        raw = pos_score + neg_score + reg_score
        # نرمال‌سازی تانژانتی برای مهار دنباله‌های بلند
        result.score = max(-1.0, min(1.0, math.tanh(raw / 2.0)))
        n_evidence = len(result.positive_terms) + len(result.negative_terms) + len(result.regulatory_hits)
        result.confidence = min(1.0, n_evidence / 5.0)

        if result.score >= 0.15:
            result.sentiment = "positive"
        elif result.score <= -0.15:
            result.sentiment = "negative"
        else:
            result.sentiment = "neutral"

        # تأثیر EPS: رویدادهای رگولاتوری وزن بیشتری دارند؛ tag پرتاثیرترین هیت برمی‌گردد
        if result.regulatory_hits:
            result.eps_impact_hint = max(
                (h["impact"] for h in result.regulatory_hits), key=abs, default=0.0
            )
            result.impact_tag = max(
                result.regulatory_hits, key=lambda h: abs(h["impact"])
            )["tag"]
        else:
            result.eps_impact_hint = result.score * 0.4

        return result

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        return [self.analyze(t) for t in texts]

    # ── پیاده‌سازی ──

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.translate(_PERSIAN_DIGITS)
        # نیم‌فاصله → فاصله برای تطبیق عبارات
        text = text.replace("\u200c", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _scan_lexicon(self, text: str, result: SentimentResult) -> tuple[float, float]:
        pos = neg = 0.0
        matched_spans: list[tuple[int, int]] = []
        for rx, term, weight in self._compiled:
            for m in rx.finditer(text):
                idx, end = m.start(), m.end()
                # اگر داخل عبارت قبلی (بلندتر) است، پرش
                if any(s <= idx < e for s, e in matched_spans):
                    continue
                matched_spans.append((idx, end))

                # تشدید/تضعیف در پنجره ۲ کلمه‌ای قبل
                window = text[max(0, idx - 20): idx]
                factor = 1.0
                for inten, f in INTENSIFIERS.items():
                    if inten in window:
                        factor = max(factor, f)

                # نفی پیشین («نمی‌شود افزایش داد») یا نفی پسین («سودآور نیست»)
                after_window = text[end: end + 14]
                flipped = any(n in window for n in NEGATORS) or any(
                    n in after_window for n in POST_NEGATORS
                )
                weight_eff = -weight if flipped else weight

                w = weight_eff * factor
                if w > 0:
                    pos += w
                    result.positive_terms.append(term)
                else:
                    neg += w
                    result.negative_terms.append(term)
        return pos, neg

    def _scan_regulatory(self, text: str, result: SentimentResult) -> float:
        total = 0.0
        for tag, pattern, base_impact in REGULATORY_PATTERNS:
            m = re.search(pattern, text)
            if m:
                result.regulatory_hits.append({
                    "tag": tag,
                    "match": m.group(0)[:60],
                    "impact": base_impact,
                })
                total += base_impact
        # tag نهایی در analyze بر اساس |impact| انتخاب می‌شود
        return total


# ── singleton ملایم ──────────────────────────────────────────────────────────

_engine: PersianNewsSentimentEngine | None = None


def get_sentiment_engine() -> PersianNewsSentimentEngine:
    global _engine
    if _engine is None:
        _engine = PersianNewsSentimentEngine()
    return _engine
