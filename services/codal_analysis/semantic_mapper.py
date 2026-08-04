from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger
from services.codal_analysis.account_mapper import CANONICAL_ACCOUNTS, RULE_BASED_MAPPINGS

logger = get_logger(__name__)


@dataclass
class SemanticMappingResult:
    canonical_code: str | None
    canonical_name: str | None
    confidence: float
    method: str
    source_label: str
    alternative_matches: list[dict[str, Any]] = field(default_factory=list)
    needs_review: bool = False


FINANCIAL_EMBEDDINGS_HINT: dict[str, list[str]] = {
    "REVENUE": [
        "فروش", "درآمد", "فروش خالص", "درآمد عملیاتی", "جمع فروش",
        "خالص فروش", "فروش ویژه", "درآمد حاصل از فروش",
    ],
    "COST_OF_GOODS_SOLD": [
        "بهای تمام شده", "هزینه فروش", "بهای تمام شده فروش",
        "قیمت تمام شده", "هزینه مستقیم", "هزینه تولید",
        "بهای تمام شده کالای فروش رفته",
    ],
    "GROSS_PROFIT": [
        "سود ناخالص", "ناخالص فروش", "سود ناویژه", "سود ناخالص فروش",
    ],
    "OPERATING_EXPENSES": [
        "هزینه عمومی", "هزینه اداری", "هزینه فروش", "هزینه سربار",
        "هزینه پرسنل", "هزینه حقوق", "هزینه تشکیلاتی",
        "هزینه توزیع", "جمع هزینه های عملیاتی", "سربار",
    ],
    "OPERATING_PROFIT": [
        "سود عملیاتی", "زیان عملیاتی", "سود (زیان) عملیاتی",
        "سود قبل از مالیات", "سود عملیات",
    ],
    "FINANCIAL_COST": [
        "هزینه مالی", "هزینه بهره", "کارمزد", "هزینه تامین مالی",
        "سود تسهیلات", "سود بانکی پرداختی",
    ],
    "FINANCIAL_INCOME": [
        "درآمد مالی", "سود سپرده", "سود بانکی دریافتی",
        "درآمد حاصل از سرمایه گذاری",
    ],
    "NET_PROFIT": [
        "سود خالص", "سود ویژه", "زیان خالص", "سود (زیان) خالص",
        "خالص سود", "سود (زیان) ویژه", "سود ویژه دوره",
    ],
    "EPS": [
        "سود هر سهم", "EPS", "سود پایه", "زیان هر سهم",
        "سود (زیان) به ازای هر سهم",
    ],
    "CURRENT_ASSETS": [
        "دارایی جاری", "دارایی های جاری", "جمع دارایی جاری",
        "کل دارایی های جاری",
    ],
    "NON_CURRENT_ASSETS": [
        "دارایی غیرجاری", "دارایی غیر جاری", "دارایی ثابت",
        "دارایی بلندمدت", "دارایی های غیرجاری",
        "اموال و ماشین آلات", "سرمایه گذاری بلندمدت",
    ],
    "TOTAL_ASSETS": [
        "جمع دارایی ها", "کل دارایی", "مجموع دارایی",
        "جمع دارایی", "کل داراییها",
    ],
    "CURRENT_LIABILITIES": [
        "بدهی جاری", "بدهی های جاری", "جمع بدهی جاری",
    ],
    "TOTAL_CURRENT_LIABILITIES": [
        "جمع بدهی های جاری", "کل بدهی های جاری",
    ],
    "NON_CURRENT_LIABILITIES": [
        "بدهی غیرجاری", "بدهی بلندمدت", "بدهی های غیرجاری",
        "تسهیلات بلندمدت", "تسهیلات مالی بلندمدت",
    ],
    "TOTAL_LIABILITIES": [
        "جمع بدهی ها", "کل بدهی", "جمع بدهی",
        "مجموع بدهی ها", "کل بدهیها",
    ],
    "EQUITY": [
        "حقوق صاحبان سهام", "حقوق مالکانه", "سرمایه",
        "جمع حقوق صاحبان", "کل حقوق صاحبان سهام",
        "خالص سرمایه", "حقوق سهامداران",
    ],
    "TOTAL_EQUITY": [
        "جمع حقوق صاحبان سهام", "کل حقوق صاحبان سهام",
        "جمع حقوق و اندوخته",
    ],
    "INVENTORY": [
        "موجودی کالا", "موجودی مواد", "موجودی نهایی",
        "موجودی انبار", "موجودی مواد اولیه",
    ],
    "CASH": [
        "وجه نقد", "موجودی نقد", "نقد و بانک", "وجوه نقد",
        "سپرده بانکی", "مانده نقد",
    ],
    "ACCOUNTS_RECEIVABLE": [
        "حساب های دریافتنی", "حساب دریافتنی", "اسناد دریافتنی",
        "مطالبات", "حسابها و اسناد دریافتنی",
    ],
    "ACCOUNTS_PAYABLE": [
        "حساب های پرداختنی", "حساب پرداختنی", "اسناد پرداختنی",
        "حسابها و اسناد پرداختنی",
    ],
    "OPERATING_CASH_FLOW": [
        "وجه نقد حاصل از عملیات", "خالص وجه نقد عملیاتی",
        "خالص جریان نقد عملیاتی", "جریان نقد عملیاتی",
        "وجه نقد عملیاتی", "خالص وجه نقد حاصل از عملیات",
    ],
    "INVESTING_CASH_FLOW": [
        "وجه نقد حاصل از سرمایه گذاری", "خالص وجه نقد سرمایه گذاری",
        "خالص جریان نقد سرمایه گذاری",
    ],
    "FINANCING_CASH_FLOW": [
        "وجه نقد حاصل از تامین مالی", "خالص وجه نقد تامین مالی",
        "خالص جریان نقد تامین مالی",
    ],
    "RETAINED_EARNINGS": [
        "سود انباشته", "سود (زیان) انباشته", "سود انباشته ابتدای دوره",
        "سود انباشته پایان دوره",
    ],
    "CAPITAL": [
        "سرمایه ثبت شده", "سرمایه اسمی", "سرمایه ثبت",
        "سرمایه مجاز", "سرمایه پرداخت شده",
    ],
    "DEPRECIATION": [
        "استهلاک", "هزینه استهلاک", "استهلاک انباشته",
        "استهلاک دارایی",
    ],
    "NET_FIXED_ASSETS": [
        "اموال و ماشین آلات", "دارایی های ثابت خالص",
        "دارایی های ثابت مشهود", "خالص اموال و ماشین آلات",
    ],
}


class SemanticAccountMapper:
    """
    AI-powered semantic account mapper using vector similarity principles.
    Combines rule-based exact matching with semantic similarity fallback
    using keyword overlap (Jaccard-like) scoring.
    """

    def __init__(self, confidence_threshold: float = 0.70, use_semantic_fallback: bool = True):
        self.confidence_threshold = confidence_threshold
        self.use_semantic_fallback = use_semantic_fallback
        self._rule_based = RULE_BASED_MAPPINGS

        self._canonical_embeddings: dict[str, set[str]] = {
            code: set().union(*(self._tokenize(phrase) for phrase in phrases))
            for code, phrases in FINANCIAL_EMBEDDINGS_HINT.items()
        }

        self._account_signatures: dict[str, dict[str, float]] = {}
        for code, terms in FINANCIAL_EMBEDDINGS_HINT.items():
            sig: dict[str, float] = {}
            for term in terms:
                tokens = self._tokenize(term)
                for token in tokens:
                    sig[token] = sig.get(token, 0) + 1
            total = sum(sig.values()) or 1
            self._account_signatures[code] = {k: v / total for k, v in sig.items()}

    def _tokenize(self, text: str) -> set[str]:
        text = text.replace("\u200c", " ")
        tokens = re.findall(r"[\wآ-ی]+", text)
        return set(tokens)

    def _jaccard_similarity(self, set1: set[str], set2: set[str]) -> float:
        if not set1 or not set2:
            return 0.0
        intersection = set1 & set2
        union = set1 | set2
        return len(intersection) / len(union) if union else 0.0

    def _weighted_similarity(self, source_tokens: set[str], account_code: str) -> float:
        sig = self._account_signatures.get(account_code, {})
        if not sig:
            return 0.0
        score = 0.0
        for token in source_tokens:
            if token in sig:
                score += sig[token]
        return min(score, 1.0)

    def map(self, label: str, industry: str | None = None) -> SemanticMappingResult:
        label_clean = label.strip().replace("\u200c", " ")
        if not label_clean:
            return SemanticMappingResult(None, None, 0.0, "empty", label)

        # Phase 1: Exact rule-based match (fast & deterministic)
        if label_clean in self._rule_based:
            code = self._rule_based[label_clean]
            acct = CANONICAL_ACCOUNTS.get(code, {})
            return SemanticMappingResult(
                canonical_code=code,
                canonical_name=acct.get("name"),
                confidence=1.0,
                method="exact_rule",
                source_label=label,
            )

        # Phase 2: Fuzzy rule-based match (contains)
        for pattern_str, code in self._rule_based.items():
            if pattern_str in label_clean:
                acct = CANONICAL_ACCOUNTS.get(code, {})
                confidence = len(pattern_str) / max(len(label_clean), 1)
                confidence = min(0.95, max(0.7, confidence))
                return SemanticMappingResult(
                    canonical_code=code,
                    canonical_name=acct.get("name"),
                    confidence=round(confidence, 4),
                    method="fuzzy_contains",
                    source_label=label,
                )

        # Phase 3: Semantic similarity (embedding-like token overlap)
        if self.use_semantic_fallback:
            source_tokens = self._tokenize(label_clean)
            if source_tokens:
                scored: list[tuple[str, float]] = []
                for code in CANONICAL_ACCOUNTS:
                    jaccard = self._jaccard_similarity(source_tokens, self._canonical_embeddings.get(code, set()))
                    weighted = self._weighted_similarity(source_tokens, code)
                    combined = jaccard * 0.4 + weighted * 0.6
                    if combined > 0.05:
                        scored.append((code, combined))

                scored.sort(key=lambda x: x[1], reverse=True)
                alternatives = []
                for code, score in scored[:3]:
                    acct = CANONICAL_ACCOUNTS.get(code, {})
                    alternatives.append({
                        "canonical_code": code,
                        "canonical_name": acct.get("name"),
                        "score": round(score, 4),
                    })

                if scored:
                    best_code, best_score = scored[0]
                    acct = CANONICAL_ACCOUNTS.get(best_code, {})
                    needs_review = best_score < self.confidence_threshold
                    return SemanticMappingResult(
                        canonical_code=best_code,
                        canonical_name=acct.get("name"),
                        confidence=round(best_score, 4),
                        method="semantic_similarity",
                        source_label=label,
                        alternative_matches=alternatives[1:],
                        needs_review=needs_review,
                    )

        return SemanticMappingResult(
            canonical_code=None,
            canonical_name=None,
            confidence=0.0,
            method="unmapped",
            source_label=label,
            needs_review=True,
        )

    def batch_map(self, labels: list[str], industry: str | None = None) -> list[SemanticMappingResult]:
        return [self.map(lbl, industry) for lbl in labels]

    def get_review_queue(self, labels: list[str], industry: str | None = None) -> list[SemanticMappingResult]:
        return [r for r in self.batch_map(labels, industry) if r.needs_review]

    def get_unmapped(self, labels: list[str], industry: str | None = None) -> list[str]:
        return [r.source_label for r in self.batch_map(labels, industry) if r.canonical_code is None]
