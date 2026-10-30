"""Phase 1 data-terminal contract — engine inputs mocked, no database.

Pins the behaviours the Phase 1 ticket relies on:

* physical/fund/certificate rows are built from the Phase 0 engine, not a
  second formula;
* BrsApi physical/currency quotes are Toman and are surfaced as Rial;
* a missing NAV, composition, or contract weight is ``None`` (fail-closed),
  never zero;
* the what-if surface only previews and is labelled ``SAMPLE``;
* no order, wallet, custody, delivery, or buy/sell route exists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db_session
from src.gold_desk import phase1, pricer
from src.gold_desk.api import router as gold_router
from src.gold_desk.constants import GOLD_PURITY_18K, GOLD_PURITY_24K, TROY_OUNCE_GRAMS
from src.gold_desk.phase1_schemas import (
    TerminalCapabilities,
    TerminalResponse,
)

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
FRESH = (NOW - timedelta(seconds=30)).isoformat()
STALE = (NOW - timedelta(days=3)).isoformat()

XAU_USD = 4000.0
USD_TOMAN = 100_000.0
USD_RIAL = USD_TOMAN * 10

MARKET = {
    "XAUUSD": {
        "symbol": "XAUUSD",
        "price": XAU_USD,
        "change_value": 10.0,
        "change_percent": 0.25,
        "fetched_at": FRESH,
    },
    "USD": {
        "symbol": "USD",
        "price": USD_TOMAN,
        "change_value": 1_000.0,
        "change_percent": 1.0,
        "fetched_at": FRESH,
    },
    "IR_GOLD_18K": {
        "symbol": "IR_GOLD_18K",
        "price": 6_800_000.0,
        "change_value": 100_000.0,
        "change_percent": 1.5,
        "fetched_at": FRESH,
    },
}

FUND = {
    "symbol": "عیار",
    "name": "صندوق طلای عیار مفید",
    "price_last": 11_000.0,
    "price_last_change": 100.0,
    "price_last_change_pct": 0.92,
    "price_close": 10_900.0,
    "price_close_change": 50.0,
    "price_close_change_pct": 0.46,
    "trade_volume": 1_234_567,
    "trade_value": 13_580_237_000.0,
    "market_value": 50_000_000_000_000.0,
    "time": "12:29:59",
    "fetched_at": FRESH,
}

NAV = {
    "symbol": "عیار",
    "nav_issue": 10_000.0,
    "nav_redemption": 10_000.0,
    "date": "1405-07-12",
    "time": "17:00:00",
    "fetched_at": STALE,
}


def _physical_row(row: dict | None = MARKET["IR_GOLD_18K"], *, now: datetime = NOW):
    references = phase1.build_references(MARKET, now=now)
    return phase1.build_physical_row(
        "IR_GOLD_18K",
        "طلای ۱۸ عیار",
        "gram",
        row,
        xau_usd=references.xau_usd,
        usd_irt_rial=references.usd_irt_rial,
        ref_quality=references.quality,
        now=now,
    )


def _terminal_fixture(now: datetime = NOW) -> TerminalResponse:
    references = phase1.build_references(MARKET, now=now)
    return TerminalResponse(
        generated_at=now,
        references=references,
        ticker=phase1.build_ticker_items(MARKET, now=now),
        physical=[_physical_row(now=now)],
        funds=[phase1.build_fund_row(FUND, NAV, now=now)],
        certificates=[],
    )


# ════════════════════════════════════════════════════════════════
# 1. Physical table — Phase 0 engine, Rial units, trust quality
# ════════════════════════════════════════════════════════════════


class TestPhysicalRow:
    def test_price_and_change_are_converted_from_toman_to_rial(self) -> None:
        row = _physical_row()

        assert row.price == 68_000_000.0
        assert row.change_amount == 1_000_000.0
        assert row.change_pct == 1.5

    def test_intrinsic_comes_from_the_phase0_engine(self) -> None:
        row = _physical_row()
        expected = float(
            pricer.round_to_rial(
                pricer.fair_value("IR_GOLD_18K", XAU_USD, USD_RIAL, unit="rial"),
                "rial",
            )
        )

        assert row.intrinsic == pytest.approx(expected)
        assert row.intrinsic_quality == "LIVE"

    def test_bubble_is_relative_to_intrinsic_in_rial(self) -> None:
        row = _physical_row()

        assert row.bubble_amount == pytest.approx(row.price - row.intrinsic)
        assert row.bubble_pct == pytest.approx(
            (row.price - row.intrinsic) / row.intrinsic * 100.0, abs=0.01
        )
        assert row.bubble_pct == pytest.approx(-29.51, abs=0.01)

    def test_implied_usd_inverts_the_same_engine(self) -> None:
        row = _physical_row()
        grams_24k = GOLD_PURITY_18K / GOLD_PURITY_24K
        expected = row.price * TROY_OUNCE_GRAMS / (USD_RIAL * grams_24k)

        assert row.implied_usd == pytest.approx(expected, abs=0.01)
        assert row.implied_usd == pytest.approx(2819.77, abs=0.01)

    def test_fresh_row_is_live_and_stale_row_is_delayed(self) -> None:
        assert _physical_row().quality == "LIVE"
        stale = dict(MARKET["IR_GOLD_18K"], fetched_at=STALE)
        assert _physical_row(stale).quality == "DELAYED"

    def test_missing_row_is_no_data_and_is_not_zero(self) -> None:
        row = _physical_row(None)

        assert row.price is None
        assert row.intrinsic is not None  # references exist, engine still runs
        assert row.bubble_pct is None
        assert row.implied_usd is None
        assert row.quality == "NO_DATA"
        assert any("قیمت بازار" in gap for gap in row.data_gaps)

    def test_missing_references_make_intrinsic_null_with_a_reason(self) -> None:
        references = phase1.build_references({}, now=NOW)
        row = phase1.build_physical_row(
            "IR_COIN_EMAMI",
            "سکه امامی",
            "coin",
            {"price": 50_000_000.0, "change_value": 0.0, "change_percent": 0.0, "fetched_at": FRESH},
            xau_usd=references.xau_usd,
            usd_irt_rial=references.usd_irt_rial,
            ref_quality=references.quality,
            now=NOW,
        )

        assert references.quality == "NO_DATA"
        assert row.intrinsic is None
        assert row.bubble_pct is None
        assert row.intrinsic_quality == "NO_DATA"
        assert any("ارزش ذاتی" in gap for gap in row.data_gaps)


# ════════════════════════════════════════════════════════════════
# 2. Funds — nominal bubble from NAV, everything else fail-closed
# ════════════════════════════════════════════════════════════════


class TestFundRow:
    def test_known_nav_produces_the_nominal_bubble(self) -> None:
        row = phase1.build_fund_row(FUND, NAV, now=NOW)

        assert row.price == 11_000.0
        assert row.nav == 10_000.0
        assert row.bubble_nominal_pct == pytest.approx(10.0)
        assert row.bubble_nominal_amount == pytest.approx(1_000.0)

    def test_nav_jalali_date_is_converted_to_utc(self) -> None:
        row = phase1.build_fund_row(FUND, NAV, now=NOW)

        assert row.nav_date == "1405-07-12"
        assert row.nav_as_of == datetime(2026, 10, 4, 13, 30, tzinfo=UTC)
        assert row.nav_quality == "DELAYED"

    def test_missing_nav_is_null_and_never_zero(self) -> None:
        row = phase1.build_fund_row(FUND, None, now=NOW)

        assert row.nav is None
        assert row.bubble_nominal_pct is None
        assert row.bubble_nominal_amount is None
        assert row.nav_quality == "NO_DATA"
        assert any("NAV" in gap for gap in row.data_gaps)

    def test_composition_and_intrinsic_bubble_are_explicitly_unavailable(self) -> None:
        row = phase1.build_fund_row(FUND, NAV, now=NOW)

        assert row.composition is None
        assert row.composition_status == "needs_composition"
        assert row.intrinsic_price is None
        assert row.bubble_intrinsic_pct is None
        assert row.bubble_real_pct is None
        assert row.implied_usd is None
        assert any("ترکیب" in gap for gap in row.data_gaps)

    def test_ime_feed_has_no_trade_date_so_it_stays_null(self) -> None:
        row = phase1.build_fund_row(FUND, NAV, now=NOW)

        assert row.last_trade_date is None
        assert row.last_trade_time == "12:29:59"
        assert any("تاریخ معامله" in gap for gap in row.data_gaps)

    def test_close_price_is_used_when_last_trade_is_missing(self) -> None:
        row = phase1.build_fund_row(dict(FUND, price_last=None), NAV, now=NOW)

        assert row.price == 10_900.0
        assert row.change_amount == 50.0
        assert any("قیمت پایانی" in gap for gap in row.data_gaps)


# ════════════════════════════════════════════════════════════════
# 3. Certificates — intrinsic blocked by ambiguous contract size
# ════════════════════════════════════════════════════════════════


class TestCertificateRow:
    def test_intrinsic_stays_null_with_an_explicit_reason(self) -> None:
        row = phase1.build_certificate_row(
            {
                "contract_code": "GoldBar",
                "commodity": "شمش طلا",
                "contract_description": "گواهی سپرده کالایی شمش طلا",
                "contract_size": 10,
                "contract_size_unit": "ضریب تبدیل نماد به گروه انبار",
                "price_last": 65_000_000.0,
                "price_last_change": 500_000.0,
                "price_last_change_pct": 0.78,
                "trade_volume": 120,
                "trade_value": 7_800_000_000.0,
                "trade_value_unit": "ریال",
                "date_update": "1405-07-26",
                "time_update": "15:30:00",
                "fetched_at": FRESH,
            },
            now=NOW,
        )

        assert row.price == 65_000_000.0
        assert row.intrinsic is None
        assert row.bubble_pct is None
        assert row.bubble_amount is None
        assert row.implied_usd is None
        assert row.intrinsic_quality == "NO_DATA"
        assert any("contract_size" in gap for gap in row.data_gaps)

    def test_contract_size_is_exposed_but_not_treated_as_grams(self) -> None:
        row = phase1.build_certificate_row(
            {
                "contract_code": "GoldCoin",
                "contract_size": 1,
                "contract_size_unit": "ضریب تبدیل نماد به گروه انبار",
                "price_last": 70_000_000.0,
                "fetched_at": FRESH,
            },
            now=NOW,
        )

        assert row.contract_size == 1.0
        assert row.contract_size_unit == "ضریب تبدیل نماد به گروه انبار"
        assert row.intrinsic is None


# ════════════════════════════════════════════════════════════════
# 4. Ticker + fund universe
# ════════════════════════════════════════════════════════════════


class TestTicker:
    def test_rial_items_convert_and_ounce_stays_usd(self) -> None:
        items = {item.key: item for item in phase1.build_ticker_items(MARKET, now=NOW)}

        assert items["XAUUSD"].price == XAU_USD
        assert items["XAUUSD"].unit == "ounce"
        assert items["IR_GOLD_18K"].price == 68_000_000.0
        assert items["IR_GOLD_18K"].unit == "rial"
        assert items["USD"].price == USD_RIAL
        assert items["USD"].change_amount == 10_000.0
        assert all(item.quality == "LIVE" for key, item in items.items() if key != "GOLD_FUND_INDEX")

    def test_missing_ticker_item_is_no_data_with_a_note(self) -> None:
        items = {item.key: item for item in phase1.build_ticker_items({}, now=NOW)}

        assert items["XAUUSD"].price is None
        assert items["XAUUSD"].quality == "NO_DATA"
        assert items["XAUUSD"].note is not None

    def test_gold_fund_index_is_under_construction_not_fake(self) -> None:
        index = {item.key: item for item in phase1.build_ticker_items(MARKET, now=NOW)}[
            "GOLD_FUND_INDEX"
        ]

        assert index.status == "under_construction"
        assert index.quality == "NO_DATA"
        assert index.price is None


class TestFundUniverse:
    @pytest.mark.parametrize(
        ("symbol", "name"),
        [
            ("نقران", "صندوق س.کالای کهربا1"),
            ("سیلور", "صندوق س.بازده نقره نوا"),
            ("سیگما", "صندوق س.کالای سیگما"),
            ("پلاتین", "صندوق پلاتین"),
            ("عیار2", "صندوق طلای عیار"),
            ("کهربا1", "صندوق س.کالای کهربا"),
        ],
    )
    def test_silver_and_placeholder_counterparts_are_excluded(self, symbol: str, name: str) -> None:
        assert phase1.is_gold_fund(symbol, name) is False

    @pytest.mark.parametrize(
        ("symbol", "name"),
        [
            ("عیار", "صندوق طلای عیار مفید"),
            ("طلا", "صندوق طلای لوتوس"),
            ("کهربا", "صندوق س.کالای کهربا"),
            ("گنج", "صندوق س. سیمای کاردان"),
        ],
    )
    def test_gold_funds_are_kept(self, symbol: str, name: str) -> None:
        assert phase1.is_gold_fund(symbol, name) is True


# ════════════════════════════════════════════════════════════════
# 5. What-if — preview only, SAMPLE-labelled, no writes
# ════════════════════════════════════════════════════════════════


class TestWhatIf:
    @pytest.fixture()
    def frozen_terminal(self, monkeypatch: pytest.MonkeyPatch):
        async def _fake_terminal(session, *, now=None):
            return _terminal_fixture()

        monkeypatch.setattr(phase1, "build_terminal", _fake_terminal)

    async def test_two_input_pairs_produce_two_different_previews(self, frozen_terminal) -> None:
        first = await phase1.build_what_if(None, 4000.0, 1_000_000.0, now=NOW)
        second = await phase1.build_what_if(None, 4000.0, 2_000_000.0, now=NOW)

        row_first = first.physical[0]
        row_second = second.physical[0]
        assert first.inputs.usd_irt_toman == pytest.approx(100_000.0)
        assert second.inputs.usd_irt_toman == pytest.approx(200_000.0)
        assert row_first.preview_intrinsic == pytest.approx(96_461_886.0, abs=1.0)
        assert row_second.preview_intrinsic == pytest.approx(192_923_772.0, abs=2.0)
        assert row_first.preview_bubble_pct != row_second.preview_bubble_pct
        assert row_first.preview_quality == "SAMPLE"
        assert row_second.preview_quality == "SAMPLE"

    async def test_market_price_and_live_quality_are_not_rewritten(self, frozen_terminal) -> None:
        base = _terminal_fixture()
        preview = await phase1.build_what_if(None, 5000.0, 1_500_000.0, now=NOW)

        assert preview.physical[0].market_price == base.physical[0].price
        assert preview.physical[0].quality == base.physical[0].quality == "LIVE"
        assert preview.physical[0].base_intrinsic == base.physical[0].intrinsic

    async def test_fund_nominal_bubble_is_nav_based_and_unchanged(self, frozen_terminal) -> None:
        preview = await phase1.build_what_if(None, 5000.0, 1_500_000.0, now=NOW)

        fund = preview.funds[0]
        assert fund.nominal_bubble_pct_before == pytest.approx(10.0)
        assert fund.nominal_bubble_pct_after == pytest.approx(10.0)
        assert fund.real_bubble_pct_after is None
        assert fund.implied_usd_after is None

    async def test_preview_never_touches_the_database(self) -> None:
        """``build_what_if`` must only read: the stub records every write hook."""

        class _EmptyResult:
            def scalars(self):
                return self

            def all(self):
                return []

        class _ReadOnlySession:
            def __init__(self) -> None:
                self.writes: list[str] = []

            async def execute(self, *_args, **_kwargs):
                return _EmptyResult()

            def add(self, *_args, **_kwargs):
                self.writes.append("add")

            async def flush(self):
                self.writes.append("flush")

            async def commit(self):
                self.writes.append("commit")

        session = _ReadOnlySession()
        preview = await phase1.build_what_if(session, 4000.0, 1_000_000.0, now=NOW)

        assert session.writes == []
        assert preview.capabilities.preview_only is True
        assert preview.capabilities.orders is False


# ════════════════════════════════════════════════════════════════
# 6. Surface guard — no order/wallet/custody/delivery route
# ════════════════════════════════════════════════════════════════


def test_no_order_or_custody_route_is_mounted() -> None:
    forbidden_segments = {
        "order",
        "orders",
        "buy",
        "sell",
        "wallet",
        "delivery",
        "custody",
        "checkout",
    }
    paths = {getattr(route, "path", "") for route in gold_router.routes}
    offenders = sorted(
        path
        for path in paths
        if any(segment in forbidden_segments for segment in path.strip("/").split("/"))
    )

    assert not offenders, f"forbidden order/custody routes mounted: {offenders}"


def test_capabilities_declare_preview_only() -> None:
    caps = TerminalCapabilities()

    assert caps.orders is False
    assert caps.wallet is False
    assert caps.delivery is False
    assert caps.preview_only is True


def test_terminal_and_what_if_routes_are_mounted() -> None:
    paths = {getattr(route, "path", "") for route in gold_router.routes}

    assert "/gold/terminal" in paths
    assert "/gold/what-if" in paths


def test_phase1_routes_survive_the_assembled_router() -> None:
    from apps.api.router import Router

    mounted = {getattr(route, "path", "") for route in Router().setup().routes}

    assert {"/gold/terminal", "/gold/what-if"} <= mounted


# ════════════════════════════════════════════════════════════════
# 7. HTTP contract on a probe app (DB dependency stubbed)
# ════════════════════════════════════════════════════════════════


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def _fake_terminal(session, *, now=None):
        return _terminal_fixture()

    monkeypatch.setattr(phase1, "build_terminal", _fake_terminal)

    probe = FastAPI()
    probe.include_router(gold_router)
    probe.dependency_overrides[get_db_session] = lambda: None
    return TestClient(probe, raise_server_exceptions=False)


def test_terminal_http_returns_rial_tables_and_capabilities(client: TestClient) -> None:
    response = client.get("/gold/terminal")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["unit"] == "rial"
    assert data["capabilities"] == {
        "orders": False,
        "wallet": False,
        "delivery": False,
        "preview_only": True,
    }
    assert data["ticker"] and data["physical"] and data["funds"]
    assert data["physical"][0]["price"] == 68_000_000.0
    assert data["funds"][0]["bubble_nominal_pct"] == pytest.approx(10.0)


def test_what_if_http_accepts_camel_case_and_returns_sample(client: TestClient) -> None:
    response = client.post(
        "/gold/what-if",
        json={"xauUsd": 5000.0, "usdIrr": 1_500_000.0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["inputs"]["xau_usd"] == 5000.0
    assert data["inputs"]["usd_irt_rial"] == 1_500_000.0
    assert data["inputs"]["usd_irt_toman"] == pytest.approx(150_000.0)
    assert data["physical"][0]["preview_quality"] == "SAMPLE"
    assert data["physical"][0]["market_price"] == 68_000_000.0


@pytest.mark.parametrize(
    "payload",
    [
        {"xau_usd": 0, "usd_irt_rial": 1_000_000.0},
        {"xau_usd": 4000.0, "usd_irt_rial": 0},
        {"xau_usd": -1, "usd_irt_rial": -1},
    ],
)
def test_what_if_http_rejects_non_positive_inputs(client: TestClient, payload: dict) -> None:
    assert client.post("/gold/what-if", json=payload).status_code == 422
