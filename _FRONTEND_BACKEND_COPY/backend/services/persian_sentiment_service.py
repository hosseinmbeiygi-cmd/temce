from __future__ import annotations

import os
import re
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

from core.logging import get_logger

logger = get_logger(__name__)

# ── Persian financial keyword lists ────────────────────────────────────────────

POSITIVE_KEYWORDS = [
    "رشد",
    "افزایش",
    "صعود",
    "جهش",
    "مثبت",
    "سود",
    "بهره",
    "منفعت",
    "خرید",
    "تقاضا",
    "شکست مقاومت",
    "حمایت",
    "تجمع",
    "انباشت",
    "بهبود",
    "توسعه",
    "گسترش",
    "پیشرفت",
    "موفقیت",
    "رکوردشکنی",
    "بازدهی",
    "درآمد",
    "سودآوری",
    "افزایش سرمایه",
    "تقسیم سود",
    "پیشنهاد خرید",
    "توصیه خرید",
    "همراه با رشد",
    "روند صعودی",
    "کف‌سازی",
    "شکست سقف",
    "عبور از مقاومت",
    "سیگنال خرید",
    "پتانسیل رشد",
    "چشم‌انداز مثبت",
    "عملکرد قوی",
    "افزایش حجم",
    "ورود پول هوشمند",
    "جمع‌آوری",
    "تثبیت قیمت",
    "بازگشت صعودی",
]

NEGATIVE_KEYWORDS = [
    "کاهش",
    "افت",
    "سقوط",
    "ریزش",
    "منفی",
    "زیان",
    "ضرر",
    "خسارت",
    "فروش",
    "عرضه",
    "شکست حمایت",
    "مقاومت",
    "توزیع",
    "تخلیه",
    "تخریب",
    "فروپاشی",
    "بحران",
    "رکود",
    "تورم",
    "کمبود",
    "کاهش درآمد",
    "زیان‌دهی",
    "انحلال",
    "ورشکستگی",
    "تحریم",
    "پیشنهاد فروش",
    "توصیه فروش",
    "همراه با افت",
    "روند نزولی",
    "سقف‌سازی",
    "شکست کف",
    "سقوط از حمایت",
    "سیگنال فروش",
    "پتانسیل افت",
    "چشم‌انداز منفی",
    "عملکرد ضعیف",
    "کاهش حجم",
    "خروج پول هوشمند",
    "توزیع سنگین",
    "شکست قیمت",
    "بازگشت نزولی",
    "تهدید",
    "ریسک بالا",
    "هشدار",
    "فشار فروش",
    "عدم اطمینان",
]

INTENSIFIERS = ["بسیار", "شدیداً", "قابل توجه", "چشمگیر", "بی‌سابقه", "تاریخی", "عظیم"]
NEGATORS = ["نیست", "نشد", "نکرد", "نبود", "بدون", "هیچ", "نه", "خلاف"]

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sentiment_models")


class PersianSentimentService:
    """Persian-language sentiment analysis for financial text.

    Combines rule-based keyword scoring with an optional TF-IDF + LogisticRegression
    ML model that can be trained on labelled data.
    """

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._model: LogisticRegression | None = None
        self._model_loaded = False

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, text: str) -> dict[str, Any]:
        """Return sentiment score, label, and method used."""
        rule_result = self._rule_based_score(text)
        ml_result = self._ml_score(text)

        # Blend scores: if ML model available, weight it 60/40
        if ml_result is not None:
            blended = 0.4 * rule_result["score"] + 0.6 * ml_result["score"]
            method = "blended"
        else:
            blended = rule_result["score"]
            method = "rule_based"

        label = self._score_to_label(blended)
        return {
            "text": text[:200],
            "score": round(blended, 4),
            "label": label,
            "method": method,
            "rule_score": rule_result["score"],
            "ml_score": ml_result["score"] if ml_result else None,
            "keywords": rule_result["keywords"],
        }

    def analyze_batch(self, texts: list[str]) -> list[dict[str, Any]]:
        return [self.analyze(text) for text in texts]

    def train(self, texts: list[str], labels: list[str]) -> dict[str, Any]:
        """Train the TF-IDF + LogisticRegression model.

        labels should be 'positive', 'negative', or 'neutral'.
        """
        if len(texts) < 10:
            return {"success": False, "error": "Need at least 10 samples to train"}

        cleaned = [self._clean_text(t) for t in texts]

        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            analyzer="char_wb",
            min_df=1,
        )
        X = self._vectorizer.fit_transform(cleaned)

        self._model = LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",
            multi_class="multinomial",
        )

        # Cross-validation
        cv_scores = cross_val_score(self._model, X, labels, cv=min(5, len(texts)), scoring="accuracy")
        self._model.fit(X, labels)
        self._model_loaded = True

        # Save model
        self._save_model()

        return {
            "success": True,
            "cv_accuracy": round(float(cv_scores.mean()), 4),
            "cv_std": round(float(cv_scores.std()), 4),
            "n_samples": len(texts),
            "classes": list(self._model.classes_),
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "model_loaded": self._model_loaded,
            "positive_keywords": len(POSITIVE_KEYWORDS),
            "negative_keywords": len(NEGATIVE_KEYWORDS),
            "model_classes": list(self._model.classes_) if self._model else [],
        }

    # ── Rule-based scoring ────────────────────────────────────────────────────

    def _rule_based_score(self, text: str) -> dict[str, Any]:
        found_pos: list[str] = []
        found_neg: list[str] = []

        for kw in POSITIVE_KEYWORDS:
            if kw in text:
                found_pos.append(kw)
        for kw in NEGATIVE_KEYWORDS:
            if kw in text:
                found_neg.append(kw)

        # Check for negators near keywords
        negation_count = sum(1 for n in NEGATORS if n in text)
        if negation_count % 2 == 1:
            found_pos, found_neg = found_neg, found_pos

        pos_score = min(len(found_pos) * 0.2, 1.0)
        neg_score = min(len(found_neg) * 0.2, 1.0)

        total = pos_score + neg_score
        score = 0.0 if total == 0 else (pos_score - neg_score) / max(total, 1e-06)

        # Intensity boost
        intensity = sum(1 for iw in INTENSIFIERS if iw in text)
        score = score * min(1.0 + intensity * 0.1, 1.5)

        return {
            "score": round(max(-1, min(1, score)), 4),
            "keywords": found_pos + found_neg,
        }

    # ── ML scoring ────────────────────────────────────────────────────────────

    def _ml_score(self, text: str) -> dict[str, Any] | None:
        if not self._model_loaded or self._model is None or self._vectorizer is None:
            self._load_model()

        if not self._model_loaded:
            return None

        cleaned = self._clean_text(text)
        X = self._vectorizer.transform([cleaned])
        proba = self._model.predict_proba(X)[0]
        classes = self._model.classes_

        # Map to -1..1 scale
        label_scores = {"negative": -1.0, "neutral": 0.0, "positive": 1.0}
        score = sum(proba[i] * label_scores.get(classes[i], 0.0) for i in range(len(classes)))

        return {
            "score": round(score, 4),
            "probabilities": {classes[i]: round(float(proba[i]), 4) for i in range(len(classes))},
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _score_to_label(score: float) -> str:
        if score > 0.15:
            return "positive"
        if score < -0.15:
            return "negative"
        return "neutral"

    def _save_model(self) -> None:
        try:
            os.makedirs(MODEL_DIR, exist_ok=True)
            joblib.dump(self._vectorizer, os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib"))
            joblib.dump(self._model, os.path.join(MODEL_DIR, "sentiment_model.joblib"))
            logger.info("Sentiment model saved to %s", MODEL_DIR)
        except Exception as exc:
            logger.warning("Failed to save sentiment model: %s", exc)

    def _load_model(self) -> None:
        try:
            vec_path = os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib")
            model_path = os.path.join(MODEL_DIR, "sentiment_model.joblib")
            if os.path.exists(vec_path) and os.path.exists(model_path):
                self._vectorizer = joblib.load(vec_path)
                self._model = joblib.load(model_path)
                self._model_loaded = True
                logger.info("Sentiment model loaded from %s", MODEL_DIR)
            else:
                logger.info("No pre-trained sentiment model found at %s", MODEL_DIR)
        except Exception as exc:
            logger.warning("Failed to load sentiment model: %s", exc)
