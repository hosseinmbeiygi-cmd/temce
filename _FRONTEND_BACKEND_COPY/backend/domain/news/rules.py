from __future__ import annotations


def validate_news_title(title: str) -> bool:
    return bool(title and title.strip())


def validate_news_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def validate_sentiment_score(score: float) -> bool:
    return -1.0 <= score <= 1.0


def validate_relevance_score(score: float) -> bool:
    return 0.0 <= score <= 1.0


def is_positive_sentiment(score: float) -> bool:
    return score > 0.1


def is_negative_sentiment(score: float) -> bool:
    return score < -0.1


def is_neutral_sentiment(score: float) -> bool:
    return -0.1 <= score <= 0.1
