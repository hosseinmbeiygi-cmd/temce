"""Unit tests for the Persian news sentiment engine (services/stock_news_sentiment_engine.py).

فرمول‌های سنتیمنت، کلیدواژه‌های رگولاتوری و نرمال‌سازی — بدون دیتابیس.
"""

from __future__ import annotations

import pytest

from services.stock_news_sentiment_engine import (
    PersianNewsSentimentEngine,
    get_sentiment_engine,
)


@pytest.fixture(scope="module")
def engine() -> PersianNewsSentimentEngine:
    return PersianNewsSentimentEngine()


class TestBasicSentiment:
    def test_empty_text(self, engine):
        r = engine.analyze("")
        assert r.sentiment == "neutral"
        assert r.score == 0.0
        assert r.confidence == 0.0

    def test_positive_news(self, engine):
        r = engine.analyze("شرکت با رشد چشمگیر فروش، سودآوری مطلوبی را تجربه کرد")
        assert r.sentiment == "positive"
        assert r.score > 0.15
        assert "رشد" in r.positive_terms

    def test_negative_news(self, engine):
        r = engine.analyze("سود شرکت به دلیل کاهش فروش با افت محسوسی مواجه شد")
        assert r.sentiment == "negative"
        assert r.score <= -0.15

    def test_neutral_text(self, engine):
        r = engine.analyze("گزارش کارشناسی صنعت فولاد امروز منتشر شد")
        assert r.sentiment == "neutral"
        assert abs(r.score) < 0.15

    def test_score_bounded(self, engine):
        r = engine.analyze("جهش رکورد رکوردزنی سودآور سودآور سودآور عالی عالی عالی عالی عالی")
        assert -1.0 <= r.score <= 1.0


class TestRegulatoryKeywords:
    def test_halt_detection(self, engine):
        r = engine.analyze("نماد شرکت متوقف شد و تا اطلاع ثانوی معاملات آن متوقف است")
        assert r.impact_tag == "halting"
        assert r.sentiment == "negative"

    def test_reopening_detection(self, engine):
        r = engine.analyze("نماد پس از انتشار اطلاعات با بازگشایی نماد مواجه شد")
        assert r.impact_tag == "halting"
        # بازگشایی impact مثبت است
        assert any(h["impact"] > 0 for h in r.regulatory_hits)

    def test_tax_exemption(self, engine):
        r = engine.analyze("معافیت مالیاتی برای صادرات محصولات این شرکت ابلاغ شد")
        assert r.impact_tag == "tax"
        assert r.eps_impact_hint > 0

    def test_feed_rate(self, engine):
        r = engine.analyze("نرخ خوراک گاز صنایع فولاد افزایش یافت")
        assert r.impact_tag == "feed_rate"

    def test_capital_increase(self, engine):
        r = engine.analyze("افزایش سرمایه از آورده سهامداران در دستور کار مجمع قرار گرفت")
        assert r.impact_tag == "dilution"

    def test_sanction(self, engine):
        r = engine.analyze("تحریم جدیدی علیه شرکت اعمال شد")
        assert r.impact_tag == "sanction"
        assert r.sentiment == "negative"

    def test_fx(self, engine):
        r = engine.analyze("تسعیر ارز به نرخ نیما برای شرکت مثبت است")
        assert r.impact_tag == "fx"

    def test_regulatory_dominates_tag(self, engine):
        # چند رویداد: tag اولین الگوی پیدا شده است
        r = engine.analyze("نماد متوقف شد ولی بعداً خبر تسعیر ارز آمد")
        assert r.impact_tag == "halting"


class TestNormalization:
    def test_persian_digits(self, engine):
        r = engine.analyze("تولید ۲۰ درصد افزایش یافت")
        assert r.sentiment == "positive"

    def test_zwnj_handling(self, engine):
        # نیم‌فاصله نباید مانع تشخیص شود
        r = engine.analyze("شركت زیان‌ده اعلام شد")
        assert r.sentiment == "negative"

    def test_negation_flips(self, engine):
        r1 = engine.analyze("شرکت سودآور است")
        r2 = engine.analyze("شرکت سودآور نیست")
        # نقیض باید سنتیمنت را معکوس کند
        assert r1.score > 0
        assert r2.score < 0

    def test_confidence_grows_with_evidence(self, engine):
        r1 = engine.analyze("رشد فروش")
        r2 = engine.analyze("رشد فروش، بهبود حاشیه سود، دریافت قرارداد جدید و تقویت بازار")
        assert r2.confidence > r1.confidence


class TestBatchAndSingleton:
    def test_batch(self, engine):
        out = engine.analyze_batch(["رشد فروش", "توقف نماد", "خبری نیست"])
        assert len(out) == 3
        assert out[0].sentiment == "positive"
        assert out[1].sentiment == "negative"

    def test_singleton(self):
        assert get_sentiment_engine() is get_sentiment_engine()
