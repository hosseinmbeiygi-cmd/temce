"""Tests for :mod:`core.trading_playbook` and its wiring into the unified assistant.

The load-bearing test is :func:`test_every_reference_question_finds_itself`: if the index
cannot return a question when asked that exact question, nothing downstream is trustworthy.
"""

from __future__ import annotations

from core import trading_playbook
from core.trading_playbook import engine
from services.unified_assistant_service import (
    PLAYBOOK_FALLBACK_SCORE,
    PLAYBOOK_PRIORITY_SCORE,
    UnifiedAssistantService,
)

BOOK = trading_playbook.load()


def test_bank_shape() -> None:
    assert BOOK.source_rows == 1050
    assert len(BOOK.entries) == 35
    assert len(BOOK.categories()) == 7
    assert len({e.question for e in BOOK.entries}) == 35
    assert all(len(e.context_variations) == 30 for e in BOOK.entries)
    assert all(e.analysis_logic.strip() and e.user_explanation_blueprint.strip()
               for e in BOOK.entries)
    assert set(BOOK.architecture) >= {"market_regimes", "four_awareness_gates", "risk_rules"}


def test_every_reference_question_finds_itself() -> None:
    for entry in BOOK.entries:
        top = BOOK.search(entry.question, top_k=1)
        assert top and top[0].entry.question == entry.question, entry.question
        assert top[0].score > 99


def test_paraphrase_and_arabic_spelling_still_match() -> None:
    # Arabic yeh/kaf, no ZWNJ, reworded.
    top = BOOK.search("شاخص كل مثبته ولي هم وزن منفي شده، خرید کنم؟", top_k=1)
    assert top[0].entry.id == 1
    assert top[0].confident


def test_unrelated_text_is_not_confident() -> None:
    assert BOOK.search("", top_k=3) == []
    assert BOOK.search("12345 ???", top_k=3) == []
    result = trading_playbook.answer("pizza recipe with mushrooms")
    assert not result.matches or not result.matches[0].confident
    assert "پیدا نشد" in result.text


def test_extract_prices_handles_persian_digits_and_separators() -> None:
    assert engine.extract_prices("قیمت ۱۱۵،۰۰۰ شد و ۴ درصد سود") == [115000.0]
    assert engine.extract_prices("الان 112,500.5 است") == [112500.5]
    assert engine.extract_prices("۲ معامله") == []


def test_position_snapshot_math() -> None:
    snap = trading_playbook.position_snapshot(
        "الان قیمت 115000 است", symbol="موج", buy_price=110612, remaining_pct=50
    )
    assert snap is not None
    assert snap.current_price == 115000
    assert snap.pnl_pct == 3.97
    assert snap.breakeven_price == round(110612 * 1.0023)
    loss = trading_playbook.position_snapshot("قیمت 100000", buy_price=110612)
    assert loss is not None and loss.pnl_pct < 0
    # The buy price repeated in the message is not mistaken for the live price.
    skip = trading_playbook.position_snapshot("خریدم 110612 الان 120000", buy_price=110612)
    assert skip is not None and skip.current_price == 120000
    assert trading_playbook.position_snapshot("قیمت 115000", buy_price=0) is None
    assert trading_playbook.position_snapshot("بدون عدد", buy_price=110612) is None


def test_answer_composes_rule_position_and_risk() -> None:
    result = trading_playbook.answer(
        "الان ۴ درصد در سود هستم، نقد کنم یا نگه دارم؟ قیمت 115000",
        symbol="موج", buy_price=110612, remaining_pct=50,
    )
    best = result.matches[0].entry
    assert best.category == "مدیریت معامله و روانشناسی"
    assert best.user_explanation_blueprint in result.text
    assert best.analysis_logic in result.text
    assert "در سود" in result.text and "موج" in result.text
    assert all(rule in result.text for rule in BOOK.architecture["risk_rules"])
    assert result.position is not None


def test_buy_price_from_message() -> None:
    assert trading_playbook.buy_price_from_message("میانگین خریدم ۱۱۰،۶۱۲ است") == 110612
    assert trading_playbook.buy_price_from_message("خریدم 98000 الان 101000") == 98000
    assert trading_playbook.buy_price_from_message("۴ درصد در سود هستم") is None
    assert trading_playbook.buy_price_from_message("خرید ۲ سهم") is None


# ── Wiring into the app's existing assistant (UnifiedAssistantService) ──────────


class _NoStockAssistant:
    async def process_message(self, text: str) -> dict:
        return {"type": "unknown", "text": ""}


def _assistant() -> UnifiedAssistantService:
    svc = UnifiedAssistantService()
    svc._stock_assistant = _NoStockAssistant()
    return svc


async def test_assistant_answers_playbook_question_before_intent_routing() -> None:
    # detect_intent misreads this as analyze_symbol; the playbook must win.
    result = await _assistant()._route_intent(
        "analyze_symbol", {}, "صندوق اهرمی صف فروش شده، میانگین کم کنم؟"
    )
    assert result["type"] == "playbook"
    assert result["data"]["category"] == "صندوق‌های اهرمی و حباب"
    assert "ممنوعیت میانگین کم کردن" in result["text"]
    assert len(result["suggestions"]) == 3


async def test_assistant_computes_position_from_message() -> None:
    result = await _assistant()._route_intent(
        None, {}, "الان ۴ درصد در سود هستم، نقد کنم یا نگه دارم؟ میانگین خریدم 100000 الان 104000"
    )
    assert result["type"] == "playbook"
    assert result["data"]["position"]["pnl_pct"] == 4.0


def test_existing_commands_are_not_hijacked() -> None:
    svc = _assistant()
    for command in (
        "تحلیل فولاد", "بازار چطوره؟", "بهترین سهم‌ها", "سهم ارزنده", "پول هوشمند وارد شده",
        "اخبار بازار", "قیمت بیت کوین", "قیمت طلا", "پرتفوی من", "شاخص کل چنده",
        "حباب صندوق اهرم چقدره", "الان بخرم فولاد؟", "فولاد رو بفروشم یا نگه دارم", "help",
    ):
        assert svc._handle_playbook(command, PLAYBOOK_PRIORITY_SCORE) is None, command


def test_fallback_bar_rejects_noise() -> None:
    svc = _assistant()
    assert svc._handle_playbook("pizza recipe", PLAYBOOK_FALLBACK_SCORE) is None
    assert svc._handle_playbook("سلام", PLAYBOOK_FALLBACK_SCORE) is None
