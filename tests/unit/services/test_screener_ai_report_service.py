"""Unit tests for the AI-style report service.

Covers:
  - ``_fmt`` number formatting helpers
  - ``_build_symbol_text`` narrative for model / signal / profile / flow /
    technical / track-record sections
  - ``_build_market_text`` market narrative
  - ``generate_symbol_report`` and ``generate_market_report`` with a mocked
    session and mocked 110-column model
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.screener_ai_report_service import ScreenerAIReportService, _fmt

# ── Helpers ───────────────────────────────────────────────────────────────


def _row(values: list, mapping: dict | None = None) -> MagicMock:
    """Fake SQLAlchemy row supporting row[0] and row._mapping."""
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda idx: values[idx])
    row._mapping = mapping if mapping is not None else {}
    return row


def _make_session() -> MagicMock:
    return MagicMock()


# ── _fmt ──────────────────────────────────────────────────────────────────


class TestFmt:
    def test_none_returns_dash(self) -> None:
        assert _fmt(None) == "—"

    def test_zero_returns_zero(self) -> None:
        assert _fmt(0) == "0"

    def test_large_suffixes(self) -> None:
        assert _fmt(1.5e12) == "1.50T"
        assert _fmt(2e9) == "2.00B"
        assert _fmt(3e6) == "3.0M"
        assert _fmt(4e3) == "4.0K"

    def test_small_number_uses_digits(self) -> None:
        assert _fmt(12.345) == "12.35"
        assert _fmt(12.345, digits=0) == "12"

    def test_non_numeric_passthrough(self) -> None:
        assert _fmt("up") == "up"


# ── _build_symbol_text ────────────────────────────────────────────────────


class TestBuildSymbolText:
    def test_header_contains_symbol_and_industry(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta={"name": "فولاد مبارکه", "industry": "فلزات اساسی"},
            profile=None,
            signal=None,
            model=None,
            signals_history=[],
            legal_30d=None,
            daily_60=[],
        )
        assert "فولاد" in text
        assert "فولاد مبارکه" in text
        assert "فلزات اساسی" in text
        assert "هنوز توسط مدل ۱۱۰ ستونی ارزیابی نشده" in text

    def test_model_buy_decision(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta=None,
            profile=None,
            signal=None,
            model={"decision": "خرید", "final_score": 82.0, "adjusted_score": 80.0},
            signals_history=[],
            legal_30d=None,
            daily_60=[],
        )
        assert "✅ خرید" in text
        assert "82.0" in text
        assert "کاندید خرید است" in text

    def test_model_risk_reject(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="خودرو",
            meta=None,
            profile=None,
            signal=None,
            model={"decision": "رد_ریسک", "final_score": 90.0},
            signals_history=[],
            legal_30d=None,
            daily_60=[],
        )
        assert "🛑 رد — فیلتر ریسک" in text
        assert "به دلیل فعال بودن فیلترهای ریسک" in text

    def test_score_breakdown_labels(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta=None,
            profile=None,
            signal=None,
            model={"decision": "خرید", "final_score": 75.0, "score_technical": 80.0},
            signals_history=[],
            legal_30d=None,
            daily_60=[],
        )
        assert "تفکیک نمرات مدل" in text
        assert "تکنیکال: 80.0" in text

    def test_signal_fallback_when_no_model(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta=None,
            profile=None,
            signal={"decision": "نخرید", "final_score": 55.0},
            model=None,
            signals_history=[],
            legal_30d=None,
            daily_60=[],
        )
        assert "⏸ نخرید (نگه‌داری)" in text
        assert "55.0" in text

    def test_profile_fundamentals_and_filters(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta=None,
            profile={
                "eps_current": 1000,
                "eps_prev_year": 800,
                "industry_pe": 6.5,
                "f77_dollar_eps_growth": 1,
                "f80_yield_gt_bank": 1,
            },
            signal=None,
            model=None,
            signals_history=[],
            legal_30d=None,
            daily_60=[],
        )
        assert "رشد EPS: +25.0٪" in text
        assert "P/E میانگین صنعت: 6.5" in text
        assert "رشد دلاری EPS > ۱۵٪" in text
        assert "بازده > سود بانکی" in text

    def test_legal_flow_net_calculation(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta=None,
            profile=None,
            signal=None,
            model=None,
            signals_history=[],
            legal_30d={"legal_buy": 1_000_000, "legal_sell": 400_000, "days": 20},
            daily_60=[],
        )
        assert "خرید حقوقی: 1.0M" in text
        assert "600.0K" in text  # net = 1M - 400K

    def test_daily_60_technical_section(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta=None,
            profile=None,
            signal=None,
            model=None,
            signals_history=[],
            legal_30d=None,
            daily_60=[
                {"price_close": 1000, "price_max": 1200, "price_min": 900, "price_last_change_pct": 1.5},
                {"price_close": 1100, "price_max": 1200, "price_min": 950, "price_last_change_pct": 2.0},
            ],
        )
        assert "نقاط تکنیکال" in text
        assert "میانگین ۵ روزه" in text
        assert "سقف ۶۰ روزه: 1.2K" in text

    def test_track_record_section(self) -> None:
        text = ScreenerAIReportService()._build_symbol_text(
            symbol="فولاد",
            meta=None,
            profile=None,
            signal=None,
            model={"decision": "خرید", "final_score": 70.0},
            signals_history=[
                {"generated_at": datetime(2026, 1, 1, tzinfo=UTC), "decision": "خرید", "final_score": 71.0},
            ],
            legal_30d=None,
            daily_60=[],
        )
        assert "سابقه سیگنال‌های این نماد" in text
        assert "✅ خرید" in text


# ── _build_market_text ────────────────────────────────────────────────────


class TestBuildMarketText:
    def test_stats_and_buy_signals(self) -> None:
        text = ScreenerAIReportService()._build_market_text(
            buy_signals=[{"symbol": "فولاد", "final_score": 85.0, "live_pe": 5.0, "current_price": 5000, "stop_loss_price": 4500}],
            top_signals=[],
            stats={"total": 300, "buys": 12, "risk_rejects": 5, "avg_score": 60.0},
            latest_ts=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert "نمادهای ارزیابی‌شده: 300" in text
        assert "سیگنال خرید: 12" in text
        assert "فولاد" in text
        assert "85.0" in text

    def test_no_buy_signals_falls_back_to_top(self) -> None:
        text = ScreenerAIReportService()._build_market_text(
            buy_signals=[],
            top_signals=[{"symbol": "خودرو", "final_score": 50.0, "decision": "نخرید"}],
            stats={"total": 10, "buys": 0, "risk_rejects": 0, "avg_score": 40.0},
            latest_ts=None,
        )
        assert "هیچ سیگنال خریدی صادر نشد" in text
        assert "بالاترین نمرات" in text
        assert "خودرو" in text


# ── generate_symbol_report ────────────────────────────────────────────────


class TestGenerateSymbolReport:
    @pytest.mark.asyncio
    async def test_db_unreachable_fallback(self) -> None:
        """No injectable session and an empty session generator → fallback dict."""
        svc = ScreenerAIReportService(session=None)

        async def _empty():
            if False:
                yield None

        with patch("core.database.get_session", _empty):
            report = await svc.generate_symbol_report("فولاد")

        assert report["symbol"] == "فولاد"
        assert report["model"] is None
        assert "امکان اتصال به دیتابیس وجود ندارد" in report["text"]

    @pytest.mark.asyncio
    async def test_returns_all_sections_with_mocked_session(self) -> None:
        svc = ScreenerAIReportService(session=_make_session())

        meta = {"symbol": "فولاد", "name": "فولاد مبارکه", "industry": "فلزات اساسی"}
        model = {"decision": "خرید", "final_score": 78.0, "adjusted_score": 76.0}

        with (
            patch.object(svc, "_load_symbol_meta", new=AsyncMock(return_value=meta)),
            patch.object(svc, "_load_profile", new=AsyncMock(return_value=None)),
            patch.object(svc, "_load_latest_signal", new=AsyncMock(return_value=None)),
            patch.object(svc, "_load_signals_history", new=AsyncMock(return_value=[])),
            patch.object(svc, "_load_legal_30d", new=AsyncMock(return_value=None)),
            patch.object(svc, "_load_daily_60", new=AsyncMock(return_value=[])),
            patch("services.screener110_service.Screener110Service", return_value=MagicMock(run_symbol=AsyncMock(return_value=model))),
        ):
            report = await svc.generate_symbol_report("فولاد")

        assert report["symbol"] == "فولاد"
        assert report["name"] == "فولاد مبارکه"
        assert report["industry"] == "فلزات اساسی"
        assert report["model"] == model
        assert "فولاد مبارکه" in report["text"]

    @pytest.mark.asyncio
    async def test_model_failure_is_tolerated(self) -> None:
        svc = ScreenerAIReportService(session=_make_session())

        with (
            patch.object(svc, "_load_symbol_meta", new=AsyncMock(return_value=None)),
            patch.object(svc, "_load_profile", new=AsyncMock(return_value=None)),
            patch.object(svc, "_load_latest_signal", new=AsyncMock(return_value=None)),
            patch.object(svc, "_load_signals_history", new=AsyncMock(return_value=[])),
            patch.object(svc, "_load_legal_30d", new=AsyncMock(return_value=None)),
            patch.object(svc, "_load_daily_60", new=AsyncMock(return_value=[])),
            patch("services.screener110_service.Screener110Service", side_effect=RuntimeError("boom")),
        ):
            report = await svc.generate_symbol_report("فولاد")

        assert report["model"] is None
        assert "هنوز توسط مدل ۱۱۰ ستونی ارزیابی نشده" in report["text"]

    @pytest.mark.asyncio
    async def test_uses_injected_session_for_queries(self) -> None:
        session = _make_session()
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(fetchone=MagicMock(return_value=_row([], {"symbol": "فولاد", "name": "X", "industry": "I"}))),
                MagicMock(fetchone=MagicMock(return_value=None)),
                MagicMock(fetchone=MagicMock(return_value=None)),
                MagicMock(fetchall=MagicMock(return_value=[])),
                MagicMock(fetchone=MagicMock(return_value=None)),
                MagicMock(fetchall=MagicMock(return_value=[])),
                # Catch-all so a future query doesn't raise StopIteration.
                MagicMock(fetchone=MagicMock(return_value=None)),
            ]
        )
        svc = ScreenerAIReportService(session=session)

        with patch("services.screener110_service.Screener110Service", return_value=MagicMock(run_symbol=AsyncMock(return_value=None))):
            report = await svc.generate_symbol_report("فولاد")

        assert report["name"] == "X"
        # The injected session should have been used for the queries.
        assert session.execute.await_count >= 6


# ── generate_market_report ────────────────────────────────────────────────


class TestGenerateMarketReport:
    @pytest.mark.asyncio
    async def test_db_unreachable_fallback(self) -> None:
        """No session available → fallback market dict with empty buy signals."""
        svc = ScreenerAIReportService(session=None)

        async def _empty():
            if False:
                yield None

        with patch("core.database.get_session", _empty):
            report = await svc.generate_market_report()

        assert report["buy_signals"] == []
        assert "امکان اتصال به دیتابیس وجود ندارد" in report["text"]

    @pytest.mark.asyncio
    async def test_returns_stats_and_buy_signals(self) -> None:
        session = _make_session()
        session.execute = AsyncMock(
            side_effect=[
                # latest MAX(generated_at)
                MagicMock(fetchone=MagicMock(return_value=_row([datetime(2026, 1, 1, tzinfo=UTC)]))),
                # latest signals
                MagicMock(
                    fetchall=MagicMock(
                        return_value=[
                            _row([], {"symbol": "فولاد", "final_score": 90.0, "decision": "خرید"}),
                            _row([], {"symbol": "خودرو", "final_score": 55.0, "decision": "نخرید"}),
                        ]
                    )
                ),
                # stats
                MagicMock(
                    fetchone=MagicMock(
                        return_value=_row([], {"total": 300, "buys": 12, "risk_rejects": 5, "avg_score": 60.0, "max_score": 90.0})
                    )
                ),
            ]
        )
        svc = ScreenerAIReportService(session=session)

        report = await svc.generate_market_report(limit=25)

        assert report["generated_at"] == "2026-01-01T00:00:00+00:00"
        assert report["stats"]["buys"] == 12
        assert len(report["buy_signals"]) == 1
        assert report["buy_signals"][0]["symbol"] == "فولاد"
        assert "سیگنال خرید: 12" in report["text"]
