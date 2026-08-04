from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger(__name__)

OPTIMISM_KEYWORDS: list[str] = [
    "افزایش", "رشد", "بهبود", "توسعه", "پیشرفت", "موفقیت", "سودآوری",
    "بهترین", "رکورد", "افزایشی", "صعودی", "مطلوب", "امیدوارکننده",
    "ظرفیت", "فرصت", "انگیزشی", "چشم‌انداز", "ارتقا", "بالا",
]

PESSIMISM_KEYWORDS: list[str] = [
    "کاهش", "افت", "ریزش", "مشکل", "چالش", "ریسک", "نوسان",
    "تحریم", "تورم", "بحران", "فشار", "نامطلوب", "نزولی",
    "زیان", "ضرر", "کمبود", "محدودیت", "توقف", "اختصاص",
    "ابهام", "عدم‌اطمینان", "نگرانی", "تنش",
]

UNCERTAINTY_KEYWORDS: list[str] = [
    "احتمالاً", "شاید", "ممکن است", "محتمل", "غیرقطعی",
    "وابسته به", "مشروط به", "بلاتکلیف", "نامشخص",
    "پیش‌بینی", "برآورد", "تخمین",
]

RISK_PHRASES: list[str] = [
    "ریسک", "خطر", "تهدید", "نوسانات", "تحریم",
    "عدم‌بازپرداخت", "نقدشوندگی", "بدهی", "تعهدات",
]


@dataclass
class TextAnalysisResult:
    sentiment_score: float
    optimism_score: float
    uncertainty_score: float
    risk_phrases_found: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    word_count: int = 0
    summary: str = ""


@dataclass
class AuditorOpinionAnalysis:
    opinion_type: str = "unmodified"
    has_emphasis_of_matter: bool = False
    has_qualification: bool = False
    key_paragraphs: list[str] = field(default_factory=list)
    is_modified: bool = False


OPINION_KEYWORDS: dict[str, list[str]] = {
    "unmodified": ["مقبول", "مطلوب", "واقعیت", "منصفانه", "بدون‌تأکید"],
    "qualified": ["مشروط", "به‌استثنای", "به جز", "مربوط به"],
    "adverse": ["عدم‌ارائه", "نامطلوب", "مغایر", "تخلف"],
    "disclaimer": ["عدم‌اظهارنظر", "محدودیت", "عدم‌دسترسی"],
}


def analyze_management_report(text: str) -> TextAnalysisResult:
    if not text or not text.strip():
        return TextAnalysisResult(sentiment_score=0, optimism_score=0, uncertainty_score=0)

    words = re.findall(r"[\w\-]+", text)
    word_count = len(words)
    if word_count == 0:
        return TextAnalysisResult(sentiment_score=0, optimism_score=0, uncertainty_score=0, word_count=0)

    optimism_count = sum(1 for kw in OPTIMISM_KEYWORDS if kw in text)
    pessimism_count = sum(1 for kw in PESSIMISM_KEYWORDS if kw in text)
    uncertainty_count = sum(1 for kw in UNCERTAINTY_KEYWORDS if kw in text)
    risk_found = [kw for kw in RISK_PHRASES if kw in text]

    total_sentiment_words = optimism_count + pessimism_count
    sentiment_score = 0
    if total_sentiment_words > 0:
        sentiment_score = (optimism_count - pessimism_count) / total_sentiment_words

    optimism_score = min(1.0, optimism_count / max(word_count * 0.05, 1))
    uncertainty_score = min(1.0, uncertainty_count / max(word_count * 0.05, 1))

    topics = []
    topic_keywords = {
        "فروش": ["فروش", "درآمد", "بازار"],
        "تولید": ["تولید", "ظرفیت", "محصول"],
        "سودآوری": ["سود", "سودآوری", "حاشیه"],
        "نقدینگی": ["نقد", "نقدینگی", "وجه نقد"],
        "سرمایه‌گذاری": ["سرمایه", "سرمایه‌گذاری", "توسعه"],
        "بدهی": ["بدهی", "تسهیلات", "تعهدات"],
    }
    for topic, keywords in topic_keywords.items():
        if any(kw in text for kw in keywords):
            topics.append(topic)

    return TextAnalysisResult(
        sentiment_score=round(sentiment_score, 4),
        optimism_score=round(optimism_score, 4),
        uncertainty_score=round(uncertainty_score, 4),
        risk_phrases_found=risk_found,
        topics=topics,
        word_count=word_count,
    )


def analyze_auditor_opinion(text: str) -> AuditorOpinionAnalysis:
    result = AuditorOpinionAnalysis()

    for opinion_type, keywords in OPINION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                if opinion_type != "unmodified":
                    result.is_modified = True
                    result.opinion_type = opinion_type if result.opinion_type == "unmodified" else result.opinion_type
                break

    if "تأکید" in text or "تاکید" in text:
        result.has_emphasis_of_matter = True
    if "مشروط" in text:
        result.has_qualification = True
        result.is_modified = True
        result.opinion_type = "qualified"

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    for p in paragraphs:
        if any(kw in p for kw in ["مهم", "تأکید", "ریسک", "عدم", "مشروط"]):
            result.key_paragraphs.append(p[:200])

    return result
