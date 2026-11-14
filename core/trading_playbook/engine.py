"""📚 Trading playbook — the «دستیار هوشمند معاملاتی» knowledge base, searchable offline.

Ported from the standalone ``Trading_Assistant_Master`` prototype (Streamlit + a
sentence-transformers index). Three things changed on the way in:

* **No embedding model.** The 1,050 rows are 35 distinct questions × 30 context wordings
  that share 7 rules, so a ~500 MB multilingual model bought nothing a TF-IDF index over
  35 documents does not. Matching is word + character-trigram cosine, pure stdlib.
* **No pickle cache.** The index is rebuilt from the JSON in milliseconds; unpickling a
  file from disk was a code-execution risk with no upside.
* **Prototype bugs fixed.** It indexed the result *list* as if it were the best match and
  subtracted a number from a *list* of prices, so it crashed on every message.

Free of database and HTTP imports, like :mod:`core.question_bank` and
:mod:`core.scenario_bank`, so the endpoint and the unit tests share one code path.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.news_tags import normalize_persian

PLAYBOOK_PATH = Path(__file__).with_name("playbook_1050.json")

#: Round-trip ETF fee the prototype used for the breakeven (0.23 %).
ETF_ROUND_TRIP_FEE = 0.0023
#: Numbers at or below this are treated as percentages/counts, not rial prices.
MIN_PRICE_RIAL = 1000.0
#: Below this similarity (0-100) the best match is reported as not confident.
CONFIDENT_SCORE = 20.0

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_STOPWORDS = frozenset({
    "و", "در", "به", "از", "که", "را", "با", "این", "ان", "است", "هست", "یا", "تا",
    "هم", "برای", "اما", "من", "ما", "چه", "چرا", "ایا", "شده", "کنم",
})


@dataclass(frozen=True)
class PlaybookEntry:
    """One distinct question with the rule and answer blueprint that govern it."""

    id: int
    category: str
    question: str
    analysis_logic: str
    user_explanation_blueprint: str
    context_variations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "analysis_logic": self.analysis_logic,
            "user_explanation_blueprint": self.user_explanation_blueprint,
            "variation_count": len(self.context_variations),
        }


@dataclass(frozen=True)
class Match:
    entry: PlaybookEntry
    score: float  # 0-100

    @property
    def confident(self) -> bool:
        return self.score >= CONFIDENT_SCORE

    def as_dict(self) -> dict[str, Any]:
        return {**self.entry.as_dict(), "similarity_score": self.score,
                "confident": self.confident}


@dataclass(frozen=True)
class PositionSnapshot:
    """Live P&L of the user's open position at a price quoted in their message."""

    symbol: str
    buy_price: float
    current_price: float
    pnl_pct: float
    breakeven_price: int
    remaining_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "buy_price": self.buy_price,
            "current_price": self.current_price,
            "pnl_pct": self.pnl_pct,
            "breakeven_price": self.breakeven_price,
            "remaining_pct": self.remaining_pct,
        }


@dataclass(frozen=True)
class Answer:
    text: str
    matches: tuple[Match, ...]
    position: PositionSnapshot | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "matches": [m.as_dict() for m in self.matches],
            "position": self.position.as_dict() if self.position else None,
        }


def _features(text: str) -> Counter[str]:
    """Words (minus stopwords) plus character trigrams — the latter absorb Persian
    inflection («بخرم»/«خرید») that an exact-word index would miss."""
    norm = normalize_persian(text)
    words = [w for w in _WORD_RE.findall(norm) if len(w) > 1 and w not in _STOPWORDS]
    feats: Counter[str] = Counter()
    for w in words:
        feats["w:" + w] += 2  # whole words outweigh their own trigrams
        padded = f" {w} "
        for i in range(len(padded) - 2):
            feats["g:" + padded[i : i + 3]] += 1
    return feats


@dataclass(frozen=True)
class Playbook:
    architecture: dict[str, Any]
    entries: tuple[PlaybookEntry, ...]
    source_rows: int
    _idf: dict[str, float] = field(default_factory=dict, repr=False, compare=False)
    _vectors: tuple[dict[str, float], ...] = field(default=(), repr=False, compare=False)

    def categories(self) -> list[str]:
        return list(dict.fromkeys(e.category for e in self.entries))

    def _vector(self, text: str) -> dict[str, float]:
        feats = _features(text)
        vec = {f: (1 + math.log(c)) * self._idf.get(f, 0.0) for f, c in feats.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {f: v / norm for f, v in vec.items() if v} if norm else {}

    def search(self, query: str, top_k: int = 3) -> list[Match]:
        q = self._vector(query)
        if not q or top_k <= 0:
            return []
        scored = [
            (sum(w * doc.get(f, 0.0) for f, w in q.items()), i)
            for i, doc in enumerate(self._vectors)
        ]
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [
            Match(self.entries[i], round(score * 100, 2))
            for score, i in scored[:top_k]
            if score > 0
        ]


def _build(raw: dict[str, Any]) -> Playbook:
    rows = raw["questions_database"]
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        slot = grouped.setdefault(row["question"], {"row": row, "ctx": []})
        ctx = row.get("context_variation")
        if ctx and ctx not in slot["ctx"]:
            slot["ctx"].append(ctx)
    entries = tuple(
        PlaybookEntry(
            id=int(s["row"]["id"]),
            category=s["row"]["category"],
            question=s["row"]["question"],
            analysis_logic=s["row"]["analysis_logic"],
            user_explanation_blueprint=s["row"]["user_explanation_blueprint"],
            context_variations=tuple(s["ctx"]),
        )
        for s in grouped.values()
    )
    docs = [_features(e.question) for e in entries]
    df: Counter[str] = Counter(f for d in docs for f in d)
    n = len(docs)
    idf = {f: math.log((1 + n) / (1 + c)) + 1 for f, c in df.items()}
    book = Playbook(raw["core_architecture"], entries, len(rows), idf)
    object.__setattr__(book, "_vectors", tuple(book._vector(e.question) for e in entries))
    return book


@lru_cache(maxsize=1)
def load() -> Playbook:
    with PLAYBOOK_PATH.open(encoding="utf-8") as fh:
        return _build(json.load(fh))


def extract_prices(text: str) -> list[float]:
    """Rial prices quoted in a message (Persian/Arabic digits and separators allowed)."""
    cleaned = normalize_persian(text).replace(",", "").replace("،", "").replace("٬", "")
    return [n for n in map(float, _NUMBER_RE.findall(cleaned)) if n > MIN_PRICE_RIAL]


_BUY_PRICE_RE = re.compile(
    r"(?:میانگین(?:\s+خرید)?(?:\s*م)?|خریدم|خریده\s*ام|خرید(?:\s*م)?)"
    r"\s*(?:من|را|رو|با|در|روی|قیمت|:|=|\s)*(\d+(?:\.\d+)?)"
)


def buy_price_from_message(text: str) -> float | None:
    """Buy price stated in the message itself («میانگین خریدم ۱۱۰،۶۱۲ است»), if any."""
    cleaned = normalize_persian(text).replace(",", "").replace("،", "").replace("٬", "")
    m = _BUY_PRICE_RE.search(cleaned)
    if not m:
        return None
    price = float(m.group(1))
    return price if price > MIN_PRICE_RIAL else None


def position_snapshot(
    message: str,
    *,
    symbol: str = "نامشخص",
    buy_price: float = 0,
    remaining_pct: float = 100,
) -> PositionSnapshot | None:
    """P&L at the first price in ``message`` that is not the buy price itself."""
    if buy_price <= 0:
        return None
    prices = extract_prices(message)
    current = next((p for p in prices if p != buy_price), None)
    if current is None:
        return None
    return PositionSnapshot(
        symbol=symbol,
        buy_price=buy_price,
        current_price=current,
        pnl_pct=round((current - buy_price) / buy_price * 100, 2),
        breakeven_price=round(buy_price * (1 + ETF_ROUND_TRIP_FEE)),
        remaining_pct=remaining_pct,
    )


def _position_section(p: PositionSnapshot) -> str:
    if p.pnl_pct > 0:
        status = f"**{abs(p.pnl_pct)} درصد در سود**"
    elif p.pnl_pct < 0:
        status = f"**{abs(p.pnl_pct)} درصد در ضرر**"
    else:
        status = "**سر‌به‌سر**"
    return (
        f"### محاسبه زنده وضعیت معامله شما ({p.symbol})\n"
        f"* **قیمت لحظه‌ای اعلام‌شده:** {int(p.current_price):,} ریال "
        f"(نسبت به میانگین خرید {int(p.buy_price):,} ریال).\n"
        f"* **وضعیت بازدهی فعلی:** شما هم‌اکنون {status} هستید و حجم باقی‌مانده سبد "
        f"**{p.remaining_pct:g} درصد** است.\n"
        f"* **نقطه سر‌به‌سر با احتساب کارمزد صندوق:** **{p.breakeven_price:,} ریال**.\n\n"
    )


def answer(
    message: str,
    *,
    symbol: str = "نامشخص",
    buy_price: float = 0,
    remaining_pct: float = 100,
    top_k: int = 2,
) -> Answer:
    """Structured reply: matched rule, optional live P&L, and the risk reminder."""
    book = load()
    matches = tuple(book.search(message, top_k=max(top_k, 1)))
    position = position_snapshot(
        message, symbol=symbol, buy_price=buy_price, remaining_pct=remaining_pct
    )
    calc = _position_section(position) if position else ""
    risk_rules = book.architecture.get("risk_rules", [])
    risk = "".join(f"* {rule}\n" for rule in risk_rules)

    if not matches or not matches[0].confident:
        text = (
            "**سناریوی مرجعِ نزدیکی برای این پرسش در دانش‌نامه پیدا نشد.** "
            "پرسش را با جزئیات بیشتر (نماد، قیمت، وضعیت بازار) بنویسید.\n\n"
            f"{calc}### یادآوری مدیریت ریسک و شرط ابطال\n{risk}"
        )
        return Answer(text, matches, position)

    best = matches[0].entry
    extra = ""
    for m in matches[1:]:
        if m.confident and m.entry.user_explanation_blueprint != best.user_explanation_blueprint:
            extra = f"* **توصیه تکمیلی مرتبط:** {m.entry.user_explanation_blueprint}\n"
            break
    text = (
        f"**{best.user_explanation_blueprint}**\n\n"
        f"{calc}"
        f"### تحلیل منطقی سیستم (حوزه: {best.category})\n"
        f"* **تطابق با سناریوی مرجع ({matches[0].score}٪):** {best.question}\n"
        f"* **قانون حاکم:** {best.analysis_logic}\n"
        f"{extra}\n"
        f"### یادآوری مدیریت ریسک و شرط ابطال\n{risk}"
    )
    return Answer(text, matches, position)
