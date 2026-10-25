"""قرارداد پاسخ سه مسیر GoldDesk (بدون دیتابیس).

* ``GET /gold/portfolio``      — ``id``/``holding_ids`` هر دارایی، ``priced_cost``،
  و ``None`` ماندن ``pnl_pct``/``current_value``/``pnl_irt`` وقتی قیمت نامعلوم است.
* ``GET /gold/backtest/strategy`` — پنج فیلد ``oos_*``.
* ``POST /gold/telegram/test`` — فقط خطای JSON decode گرفته می‌شود.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.gold_desk.api as gold_api
from apps.api.dependencies import get_db_session
from src.gold_desk.portfolio import HoldingPnL, PortfolioReturns, PortfolioSummary


def _returns() -> PortfolioReturns:
    return PortfolioReturns(
        nominal_pnl_irt=20.0,
        nominal_pnl_pct=10.0,
        nominal_xirr=0.1,
        real_xirr=0.05,
        usd_xirr=-0.01,
        cpi_basis="test-cpi",
        usd_basis="test-fx",
        unavailable={},
    )


def _priced() -> HoldingPnL:
    return HoldingPnL(
        symbol="IR_COIN_EMAMI",
        display_name="سکه امامی",
        quantity=2.0,
        avg_buy_price=100.0,
        current_price=110.0,
        cost_basis=200.0,
        current_value=220.0,
        pnl_irt=20.0,
        pnl_pct=10.0,
        n_purchases=1,
        holding_ids=(7,),
    )


def _unpriced() -> HoldingPnL:
    return HoldingPnL(
        symbol="IR_GOLD_18K",
        display_name="طلای ۱۸ عیار",
        quantity=3.0,
        avg_buy_price=50.0,
        current_price=None,
        cost_basis=150.0,
        current_value=None,
        pnl_irt=None,
        pnl_pct=None,
        n_purchases=2,
        holding_ids=(8, 9),
    )


def _summary() -> PortfolioSummary:
    holdings = [_priced(), _unpriced()]
    return PortfolioSummary(
        total_cost=350.0,
        total_value=220.0,
        total_pnl=20.0,
        total_pnl_pct=10.0,
        holdings=holdings,
        by_symbol={h.symbol: h for h in holdings},
        unpriced_holdings=1,
        priced_cost=200.0,
    )


def _strategy(*, oos: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        period_start=date(2026, 1, 1),
        period_end=date(2026, 6, 30),
        initial_capital=100_000_000.0,
        final_value=120_000_000.0,
        total_return_pct=20.0,
        buy_hold_return_pct=15.0,
        alpha_pct=5.0,
        hit_rate_pct=50.0,
        n_trades=4,
        n_successful=2,
        max_drawdown_pct=-8.0,
        sharpe_ratio=1.2,
        trades=[],
        warning=None,
        oos_start=date(2026, 5, 1) if oos else None,
        oos_total_return_pct=3.5 if oos else None,
        oos_buy_hold_return_pct=2.0 if oos else None,
        oos_alpha_pct=1.5 if oos else None,
        oos_max_drawdown_pct=-1.2 if oos else None,
    )


@pytest.fixture()
def app(monkeypatch) -> FastAPI:
    monkeypatch.setattr(gold_api, "get_hot_snapshot", _async({"snapshot_at": "2026-10-12T00:00:00"}))
    monkeypatch.setattr(gold_api, "get_holdings_grouped", _async(_summary()))
    monkeypatch.setattr(gold_api, "build_portfolio_returns", _async(_returns()))

    application = FastAPI()
    application.include_router(gold_api.router)
    application.dependency_overrides[get_db_session] = lambda: None
    return application


def _async(value):
    async def _call(*_args, **_kwargs):
        return value

    return _call


def _client(app: FastAPI, *, raise_server: bool = False) -> TestClient:
    return TestClient(app, raise_server_exceptions=raise_server)


# ── /portfolio ───────────────────────────────────────────────


def test_portfolio_returns_priced_cost_and_holding_ids(app: FastAPI) -> None:
    body = _client(app).get("/gold/portfolio").json()["data"]

    assert body["priced_cost"] == 200.0
    assert body["unpriced_holdings"] == 1

    priced, unpriced = body["holdings"]
    assert priced["id"] == 7
    assert priced["holding_ids"] == [7]
    assert unpriced["id"] is None  # گروه دو ردیفی id یکتا ندارد
    assert unpriced["holding_ids"] == [8, 9]


def test_portfolio_keeps_unknown_values_null(app: FastAPI) -> None:
    body = _client(app).get("/gold/portfolio").json()["data"]
    unpriced = body["holdings"][1]

    assert unpriced["current_value"] is None
    assert unpriced["pnl_irt"] is None
    assert unpriced["pnl_pct"] is None
    assert unpriced["current_price"] is None
    # مقدار نامعلوم نباید به صفر تبدیل شود.
    assert unpriced["pnl_pct"] != 0


# ── /backtest/strategy ───────────────────────────────────────


def test_strategy_backtest_exposes_oos_fields(app: FastAPI, monkeypatch) -> None:
    monkeypatch.setattr(gold_api, "run_strategy_backtest", _async(_strategy()))

    body = _client(app).get("/gold/backtest/strategy?days=90").json()["data"]

    assert body["oos_start"] == "2026-05-01"
    assert body["oos_total_return_pct"] == 3.5
    assert body["oos_buy_hold_return_pct"] == 2.0
    assert body["oos_alpha_pct"] == 1.5
    assert body["oos_max_drawdown_pct"] == -1.2


def test_strategy_backtest_oos_fields_are_null_when_unavailable(app: FastAPI, monkeypatch) -> None:
    monkeypatch.setattr(gold_api, "run_strategy_backtest", _async(_strategy(oos=False)))

    body = _client(app).get("/gold/backtest/strategy?days=90").json()["data"]

    for key in (
        "oos_start",
        "oos_total_return_pct",
        "oos_buy_hold_return_pct",
        "oos_alpha_pct",
        "oos_max_drawdown_pct",
    ):
        assert key in body
        assert body[key] is None


# ── /telegram/test ───────────────────────────────────────────


@pytest.fixture()
def telegram(monkeypatch) -> list[tuple[str, str | None]]:
    sent: list[tuple[str, str | None]] = []

    class _Config:
        @staticmethod
        def from_env():
            return SimpleNamespace(is_configured=lambda: True)

    async def _send(text: str, *, chat_id=None, config=None):
        sent.append((text, chat_id))
        return True

    monkeypatch.setattr(gold_api, "TelegramConfig", _Config)
    monkeypatch.setattr(gold_api, "send_message", _send)
    return sent


def test_telegram_test_reads_chat_id_from_json(app: FastAPI, telegram) -> None:
    response = _client(app).post("/gold/telegram/test", json={"chat_id": "12345"})

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert telegram[0][1] == "12345"


def test_telegram_test_ignores_a_body_that_is_not_json(app: FastAPI, telegram) -> None:
    response = _client(app).post(
        "/gold/telegram/test",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert telegram[0][1] is None


def test_telegram_test_does_not_swallow_other_errors(app: FastAPI, telegram) -> None:
    """خطای غیر-JSON (اینجا UTF-8 نامعتبر) دیگر بی‌صدا پنهان نمی‌شود."""
    client = _client(app, raise_server=True)

    with pytest.raises(UnicodeDecodeError):
        client.post(
            "/gold/telegram/test",
            content=b'"\x80"',
            headers={"content-type": "application/json"},
        )
