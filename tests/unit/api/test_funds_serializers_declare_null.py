"""Gate test: the funds API must not turn NULL into a measurement.

Every fund column is nullable, and every serializer in
``apps/api/endpoints/funds.py`` used to write ``float(r.x or 0)``. A symbol whose order-book
split, market value or NAV was never read therefore left the API with 0 — which the fund pages
ranked, charted, summed and read back as «بدون معامله» or «NAV صفر». Zero is a claim; NULL is
the absence of one, and only the second may be reported as null.
"""

from __future__ import annotations

import json
from datetime import datetime

from apps.api.endpoints import funds as funds_ep
from apps.api.endpoints.funds import _cnt, _fund_model_to_dict, _ime_fund_to_dict, _num, _snapshot_to_dict
from brsapi.models.ime import ImeFundModel
from brsapi.models.tsetmc import SymbolSnapshotModel
from models.fund import FundModel

NULLABLE_FUND_FIELDS = (
    "nav",
    "nav_change",
    "nav_change_pct",
    "price_last",
    "price_close",
    "price_yesterday",
    "price_max",
    "price_min",
    "trade_volume",
    "trade_value",
    "trade_count",
    "shares_count",
    "base_volume",
    "market_value",
    "buy_real_volume",
    "buy_legal_volume",
    "sell_real_volume",
    "sell_legal_volume",
)


def _fund_row(**overrides: object) -> FundModel:
    row = FundModel(
        id="f-1",
        symbol="آگاس",
        name="آتیه‌اندیشان اقتصاد پایدار",
        updated_at=datetime(2026, 9, 22, 9, 0, 0),
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _snapshot_row(**overrides: object) -> SymbolSnapshotModel:
    row = SymbolSnapshotModel(symbol="آگاس", name="آتیه‌اندیشان", fetched_at=datetime(2026, 9, 22, 9, 0, 0))
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _ime_row(**overrides: object) -> ImeFundModel:
    row = ImeFundModel(id=1, ins_id="1", symbol="عیار", name="عیار", fetched_at=datetime(2026, 9, 22, 9, 0, 0))
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


class TestNumberHelpers:
    def test_null_stays_null(self) -> None:
        assert _num(None) is None
        assert _cnt(None) is None

    def test_a_stored_zero_is_a_real_reading(self) -> None:
        # حجم مبنا and traded volume are legitimately 0 for some symbols; that must survive.
        assert _num(0) == 0.0
        assert _cnt(0) == 0

    def test_unparseable_input_is_absence_not_zero(self) -> None:
        assert _num("—") is None
        assert _cnt(object()) is None

    def test_rounding_only_applies_to_measured_values(self) -> None:
        assert _num(1.23456, 2) == 1.23
        assert _num(None, 2) is None

    def test_extra_column_is_parsed_only_when_it_is_a_json_object(self) -> None:
        assert funds_ep._fund_extra(json.dumps({"nav_basis": "nav"})) == {"nav_basis": "nav"}
        assert funds_ep._fund_extra("not json") == {}
        assert funds_ep._fund_extra("[1, 2]") == {}
        assert funds_ep._fund_extra(None) == {}


class TestFundModelSerializer:
    def test_a_row_of_nulls_exports_nulls_not_zeros(self) -> None:
        item = _fund_model_to_dict(_fund_row())

        for field in NULLABLE_FUND_FIELDS:
            assert item[field] is None, f"{field} reported 0 for a column that was never written"

    def test_real_values_pass_through_unchanged(self) -> None:
        row = _fund_row(
            nav=15_400,
            nav_change=120,
            nav_change_pct=0.78,
            trade_volume=500_000,
            base_volume=0,  # a genuine "no base volume rule"
            market_value=155_000_000_000,
            extra=json.dumps({"nav_basis": "nav"}),
        )

        item = _fund_model_to_dict(row)

        assert item["nav"] == 15_400.0
        assert item["nav_change_pct"] == 0.78
        assert item["trade_volume"] == 500_000
        assert item["base_volume"] == 0
        assert item["nav_source"] == "fund_nav"

    def test_the_price_substitute_for_nav_is_labelled(self) -> None:
        row = _fund_row(nav=15_400, extra=json.dumps({"nav_basis": "price_last"}))

        assert _fund_model_to_dict(row)["nav_source"] == "price_proxy"

    def test_an_unlabelled_nav_reports_no_basis(self) -> None:
        """Rows written before nav_basis existed must not imply a verified valuation."""
        row = _fund_row(nav=15_400, extra=None)

        assert _fund_model_to_dict(row)["nav_source"] is None


class TestSnapshotSerializer:
    def test_no_price_means_no_nav_and_no_basis(self) -> None:
        item = _snapshot_to_dict(_snapshot_row())

        assert item["nav"] is None
        assert item["nav_source"] is None
        assert item["nav_change_pct"] is None
        assert item["price_last"] is None

    def test_nav_is_labelled_as_a_price_proxy_when_no_nav_record_exists(self) -> None:
        item = _snapshot_to_dict(_snapshot_row(price_close=15_400))

        assert item["nav"] == 15_400.0
        assert item["nav_source"] == "price_proxy"

    def test_day_change_is_derived_only_from_two_real_prices(self) -> None:
        item = _snapshot_to_dict(_snapshot_row(price_close=110, price_yesterday=100))

        assert item["nav_change"] == 10
        assert item["nav_change_pct"] == 10.0

    def test_derived_change_stays_absent_without_a_previous_close(self) -> None:
        item = _snapshot_to_dict(_snapshot_row(price_close=110))

        assert item["nav_change"] is None
        assert item["nav_change_pct"] is None


class TestImeSerializer:
    def test_commodity_fund_nulls_are_not_zeros(self) -> None:
        item = _ime_fund_to_dict(_ime_row())

        for field in NULLABLE_FUND_FIELDS:
            assert item[field] is None, f"{field} invented a zero for an IME row with no data"

    def test_quoted_money_flow_survives_and_unquoted_stays_null(self) -> None:
        quoted = _ime_fund_to_dict(_ime_row(buy_real_volume=800, sell_real_volume=200))
        unquoted = _ime_fund_to_dict(_ime_row())

        assert quoted["buy_real_volume"] == 800
        assert quoted["sell_real_volume"] == 200
        assert unquoted["buy_real_volume"] is None
        assert unquoted["sell_real_volume"] is None


class TestFundServiceDict:
    def test_legacy_extra_without_a_key_does_not_default_to_zero(self) -> None:
        """Rows written before the sync stopped inventing figures simply lack the key."""
        from services.fund_service import FundService

        class _Fund:
            symbol = "آگاس"
            name = "آتیه‌اندیشان"
            isin = "IR"
            fund_type = "سهامی"
            nav = 15_400
            total_units = 10_000_000
            extra: dict = {}

        item = FundService._fund_to_dict(_Fund())  # type: ignore[arg-type]

        assert item["price_last"] is None
        assert item["trade_volume"] is None
        assert item["base_volume"] is None
        assert item["nav"] == 15_400


class TestNavBasisSurvivesPersistence:
    """The NAV-vs-price label is only useful if a save/load round keeps it.

    ``_to_orm`` used to build the row without the ``extra`` column, so the label the sync
    computed was dropped on write and every fund page read back an empty basis.
    """

    @staticmethod
    def _repo():
        from repositories.fund_repository import _FundDbRepo

        return _FundDbRepo(session=None)

    def test_a_price_standing_in_for_nav_is_still_labelled_after_a_round_trip(self) -> None:
        from domain.funds.entities import Fund

        repo = self._repo()
        fund = Fund(
            id="f-1",
            name="آتیه‌اندیشان اقتصاد پایدار",
            symbol="آگاس",
            nav=15_400,
            extra={"nav_basis": "price_last", "price_last": 15_400},
        )

        stored = repo._to_orm(fund)
        loaded = repo._to_domain(stored)

        assert loaded.extra["nav_basis"] == "price_last"

    def test_a_row_without_the_label_reports_no_basis_rather_than_a_guess(self) -> None:
        from domain.funds.entities import Fund

        repo = self._repo()
        fund = Fund(id="f-2", name="ثبات", symbol="ثبات", nav=1_000, extra={"price_last": 1_000})

        stored = repo._to_orm(fund)
        loaded = repo._to_domain(stored)

        assert stored.extra is None
        assert loaded.extra["nav_basis"] == ""
