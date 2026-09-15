"""تست chatbot — pure functions فقط."""

from __future__ import annotations

from src.gold_desk.chat import _fallback_response, build_system_prompt

SAMPLE_SNAP = {
    "score": {"total": 80, "decision": "GREEN"},
    "references": {"xau_usd": 2750.0, "usd_irt": 68500.0, "aed_gap_pct": 0.5},
    "coins": {"coin_emami": {"bubble_pct": 12.5, "market_price": 53_000_000}},
    "funds": [{"symbol": "عیار"}, {"symbol": "کهربا"}],
}


def test_system_prompt_with_snapshot():
    prompt = build_system_prompt(SAMPLE_SNAP, None, None)
    assert "80" in prompt
    assert "GREEN" in prompt
    assert "2750" in prompt
    assert "حباب" in prompt
    assert "اونس" in prompt or "دلار" in prompt


def test_system_prompt_with_portfolio():
    portfolio = {"total_value": 105_000_000, "total_cost": 100_000_000, "total_pnl": 5_000_000, "total_pnl_pct": 5.0}
    prompt = build_system_prompt(SAMPLE_SNAP, portfolio, None)
    assert "105" in prompt
    assert "5,000,000" in prompt or "5000000" in prompt
    assert "P&L" in prompt or "سود" in prompt


def test_system_prompt_with_patterns():
    patterns = {
        "patterns": [
            {"type": "mean_reversion", "confidence": 0.8, "description": "test desc", "expected_direction": "down"}
        ],
        "recommendation": "صبر کنید",
        "summary": "الگوی غالب: mean_reversion",
    }
    prompt = build_system_prompt(SAMPLE_SNAP, None, patterns)
    assert "test desc" in prompt
    assert "80%" in prompt
    assert "صبر" in prompt


def test_fallback_bubble():
    snap = {"coins": {"coin_emami": {"bubble_pct": 3.0}}}
    ans = _fallback_response("حباب سکه چقدره؟", snap, None)
    assert "3.0" in ans
    assert "خرید" in ans or "امن" in ans


def test_fallback_bubble_high():
    snap = {"coins": {"coin_emami": {"bubble_pct": 30.0}}}
    ans = _fallback_response("حباب سکه؟", snap, None)
    assert "30.0" in ans
    assert "صبر" in ans or "اشباع" in ans


def test_fallback_buy_question():
    snap = {"score": {"total": 85, "decision": "GREEN"}}
    ans = _fallback_response("الان بخرم؟", snap, None)
    assert "85" in ans
    assert "GREEN" in ans or "خرید" in ans


def test_fallback_pnl():
    portfolio = {"total_pnl": 1500000, "total_pnl_pct": 3.0}
    ans = _fallback_response("P&L من چقدره؟", None, portfolio)
    assert "1,500,000" in ans
    assert "3.00" in ans or "3.0" in ans


def test_fallback_unknown():
    ans = _fallback_response("یه سؤال عجیب", None, None)
    assert len(ans) > 0
    assert "سؤال" in ans or "تحلیل" in ans or "تب" in ans
