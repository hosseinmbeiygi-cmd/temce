"""Unit tests for FundService.update_from_brsapi with mock BrsApiQueryService.

Covers:
  - Successful update of existing fund (all fields mapped correctly)
  - Create new fund when symbol not found in DB
  - BrsApi returns None (symbol not found)
  - Edge: zero/missing values in enriched data
  - Fund type inference from name/ISIN
  - Session commit success and failure (rollback)
  - Complete vs minimal enriched data
  - Persian/Arabic symbol handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.fund_service import FundService

# ═══════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_inmemory_stores():
    """Clear the InMemoryRepository shared store before each test."""
    from repositories.base_repository import InMemoryRepository

    InMemoryRepository._shared_store.clear()
    yield
    InMemoryRepository._shared_store.clear()


@pytest.fixture
def mock_brsapi() -> MagicMock:
    """Create a mock BrsApiQueryService."""
    brsapi = MagicMock()
    brsapi.get_enriched_symbol_detail = AsyncMock()
    return brsapi


def _make_enriched(**overrides) -> dict:
    """Build a realistic enriched symbol detail response."""
    defaults = {
        "symbol": "آگاس",
        "name": "آتیه‌اندیشان اقتصاد پایدار",
        "isin": "IRAGAS0001",
        "price_last": 15_500,
        "price_yesterday": 15_000,
        "price_close": 15_400,
        "price_max": 15_800,
        "price_min": 15_100,
        "trade_volume": 500_000,
        "trade_value": 7_750_000_000,
        "trade_count": 120,
        "buy_real_volume": 200_000,
        "buy_legal_volume": 100_000,
        "sell_real_volume": 150_000,
        "sell_legal_volume": 50_000,
        "shares_count": 10_000_000,
        "market_value": 155_000_000_000,
    }
    defaults.update(overrides)
    return defaults


# ═══════════════════════════════════════════════════════════════════
#  Tests — update_from_brsapi (InMemory mode, no session)
# ═══════════════════════════════════════════════════════════════════


class TestUpdateFromBrsapiExistingFund:
    """Scenario: Fund already exists in DB → updates fields."""

    @pytest.mark.asyncio
    async def test_updates_existing_fund_all_fields(self, mock_brsapi):
        """All enriched fields are mapped to the fund entity correctly."""
        # Arrange
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched()
        service = FundService()

        # Pre-create the fund in DB
        create_result = await service.create(
            name="آتیه‌اندیشان اقتصاد پایدار",
            symbol="آگاس",
            isin="IRAGAS0001",
            fund_type="اختصاصی",
            nav=10_000.0,
            total_units=5_000_000,
        )
        assert create_result.success
        original_id = create_result.value.id

        # Act
        result = await service.update_from_brsapi(symbol="آگاس", brsapi=mock_brsapi)

        # Assert
        assert result["symbol"] == "آگاس"
        assert result["name"] == "آتیه‌اندیشان اقتصاد پایدار"
        assert result["isin"] == "IRAGAS0001"
        assert result["nav"] == 15_500                    # price_last
        assert result["nav_change_pct"] == pytest.approx(3.33, abs=0.1)
        assert result["price_last"] == 15_500
        assert result["price_yesterday"] == 15_000
        assert result["price_max"] == 15_800
        assert result["price_min"] == 15_100
        assert result["trade_volume"] == 500_000
        assert result["trade_value"] == 7_750_000_000
        assert result["trade_count"] == 120
        assert result["buy_real_volume"] == 200_000
        assert result["buy_legal_volume"] == 100_000
        assert result["sell_real_volume"] == 150_000
        assert result["sell_legal_volume"] == 50_000
        assert result["market_value"] == 155_000_000_000
        assert result["data_source"] == "brsapi"
        assert "time" in result

        # Verify the same fund entity was updated (not a new one)
        get_result = await service.get_by_id(original_id)
        assert get_result.success
        assert get_result.value.nav == 15_500
        assert get_result.value.total_units == 10_000_000

    @pytest.mark.asyncio
    async def test_updates_existing_fund_preserves_id(self, mock_brsapi):
        """Updating an existing fund preserves its original ID."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched()
        service = FundService()

        created = await service.create(name="Old", symbol="OLD", fund_type="سهامی")
        old_id = created.value.id

        result = await service.update_from_brsapi(symbol="OLD", brsapi=mock_brsapi)

        assert result["symbol"] == "OLD"
        get_result = await service.get_by_id(old_id)
        assert get_result.success
        assert get_result.value.id == old_id

    @pytest.mark.asyncio
    async def test_brsapi_called_with_correct_symbol(self, mock_brsapi):
        """BrsApiQueryService is called with the exact symbol."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched()
        service = FundService()

        await service.create(name="Test", symbol="TST", fund_type="سهامی")
        await service.update_from_brsapi(symbol="TST", brsapi=mock_brsapi)

        mock_brsapi.get_enriched_symbol_detail.assert_called_once_with("TST")

    @pytest.mark.asyncio
    async def test_nav_change_pct_positive(self, mock_brsapi):
        """nav_change_pct is correctly calculated for price increase."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            price_last=12_000,
            price_yesterday=10_000,
        )
        service = FundService()
        await service.create(name="Up Fund", symbol="UP", fund_type="سهامی")

        result = await service.update_from_brsapi(symbol="UP", brsapi=mock_brsapi)

        # (12000 - 10000) / 10000 * 100 = 20%
        assert result["nav_change_pct"] == 20.0

    @pytest.mark.asyncio
    async def test_nav_change_pct_negative(self, mock_brsapi):
        """nav_change_pct is correctly calculated for price decrease."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            price_last=9_000,
            price_yesterday=10_000,
        )
        service = FundService()
        await service.create(name="Down Fund", symbol="DOWN", fund_type="سهامی")

        result = await service.update_from_brsapi(symbol="DOWN", brsapi=mock_brsapi)

        assert result["nav_change_pct"] == -10.0

    @pytest.mark.asyncio
    async def test_nav_change_zero_when_no_yesterday(self, mock_brsapi):
        """nav_change is 0 when price_yesterday is 0 or missing."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            price_last=15_000,
            price_yesterday=0,  # No yesterday price
        )
        service = FundService()
        await service.create(name="No Yesterday", symbol="NY", fund_type="سهامی")

        result = await service.update_from_brsapi(symbol="NY", brsapi=mock_brsapi)

        assert result["nav_change"] == 0
        assert result["nav_change_pct"] == 0.0


class TestUpdateFromBrsapiNewFund:
    """Scenario: Fund not in DB → creates a new fund."""

    @pytest.mark.asyncio
    async def test_creates_new_fund_when_not_in_db(self, mock_brsapi):
        """When symbol not found in DB, a new fund is created."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            symbol="NEWFUND",
            name="صندوق جدید",
            isin="IRNEW001",
            price_last=10_000,
            price_yesterday=9_500,
        )
        service = FundService()

        result = await service.update_from_brsapi(symbol="NEWFUND", brsapi=mock_brsapi)

        assert result["symbol"] == "NEWFUND"
        assert result["name"] == "صندوق جدید"
        assert result["isin"] == "IRNEW001"
        assert result["nav"] == 10_000
        assert result["fund_type"] == "سهامی"  # Default type

        # Verify persisted
        get_result = await service.get_by_symbol("NEWFUND")
        assert get_result.success
        assert get_result.value.name == "صندوق جدید"

    @pytest.mark.asyncio
    async def test_creates_fund_with_inferred_type(self, mock_brsapi):
        """Fund type is inferred from name/ISIN when creating new fund."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            symbol="GOLD",
            name="صندوق طلا",
            isin="IRGOLD001",
        )
        service = FundService()

        result = await service.update_from_brsapi(symbol="GOLD", brsapi=mock_brsapi)

        assert result["fund_type"] == "بخشی"  # "طلا" → بخشی

    @pytest.mark.asyncio
    async def test_creates_fund_with_name_as_symbol_fallback(self, mock_brsapi):
        """When name is empty, symbol is used as name."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            symbol="UNKNOWN",
            name="",  # Empty name
            price_last=5_000,
        )
        service = FundService()

        result = await service.update_from_brsapi(symbol="UNKNOWN", brsapi=mock_brsapi)

        # Name falls back to symbol
        assert result["name"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_creates_multiple_new_funds(self, mock_brsapi):
        """Multiple sequential creates work correctly."""
        service = FundService()

        # Fund 1
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            symbol="FUND_A", name="Fund A", price_last=10_000,
        )
        r1 = await service.update_from_brsapi(symbol="FUND_A", brsapi=mock_brsapi)
        assert r1["symbol"] == "FUND_A"

        # Fund 2
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            symbol="FUND_B", name="Fund B", price_last=20_000,
        )
        r2 = await service.update_from_brsapi(symbol="FUND_B", brsapi=mock_brsapi)
        assert r2["symbol"] == "FUND_B"

        # Both persisted
        assert (await service.count()) == 2


class TestUpdateFromBrsapiErrors:
    """Error scenarios for update_from_brsapi."""

    @pytest.mark.asyncio
    async def test_brsapi_returns_none(self, mock_brsapi):
        """When BrsApi returns None, an error dict is returned."""
        mock_brsapi.get_enriched_symbol_detail.return_value = None
        service = FundService()

        result = await service.update_from_brsapi(symbol="GHOST", brsapi=mock_brsapi)

        assert result["symbol"] == "GHOST"
        assert "error" in result
        assert "یافت نشد" in result["error"]

    @pytest.mark.asyncio
    async def test_brsapi_returns_empty_dict(self, mock_brsapi):
        """BrsApi returns {} — {} is falsy so triggers early error return."""
        mock_brsapi.get_enriched_symbol_detail.return_value = {}
        service = FundService()
        await service.create(name="Empty", symbol="EMPTY", fund_type="سهامی")

        result = await service.update_from_brsapi(symbol="EMPTY", brsapi=mock_brsapi)

        # {} is falsy → `if not enriched:` triggers → error dict
        assert result["symbol"] == "EMPTY"
        assert "error" in result
        assert "یافت نشد" in result["error"]

    @pytest.mark.asyncio
    async def test_brsapi_exception_handling(self, mock_brsapi):
        """Exception from BrsApi propagates naturally."""
        mock_brsapi.get_enriched_symbol_detail.side_effect = Exception("API timeout")
        service = FundService()

        with pytest.raises(Exception, match="API timeout"):
            await service.update_from_brsapi(symbol="ERR", brsapi=mock_brsapi)


class TestUpdateFromBrsapiFundTypeInference:
    """Tests for _infer_fund_type logic via update_from_brsapi."""

    @pytest.mark.parametrize("name,isin,expected_type", [
        ("صندوق طلا", "IRGOLD001", "بخشی"),
        ("طلا", "IRX001", "بخشی"),
        ("صندوق درآمد ثابت", "IRFIX001", "درآمد ثابت"),
        ("صندوق با درآمد", "IRX002", "درآمد ثابت"),
        ("صندوق سرمایه‌گذاری ثابت", "IRX003", "درآمد ثابت"),
        ("صندوق اهرمی", "IRLEV001", "اهرمی"),
        ("اهرم", "IRX004", "اهرمی"),
        ("صندوق اختصاصی", "IRX005", "اختصاصی"),
        ("صندوق سهامی", "IRX006", "سهامی"),
        ("صندوق شاخصی", "IRX007", "سهامی"),
        ("صندوق مختلط", "IRX008", "مختلط"),
        ("صندوق بی‌نام", "IRX009", "سهامی"),  # Default
        ("ETF نمونه", "IRX010", "سهامی"),  # Default
    ])
    @pytest.mark.asyncio
    async def test_infer_fund_type(
        self, mock_brsapi, name: str, isin: str, expected_type: str,
    ):
        """Fund type is correctly inferred from name/ISIN."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            symbol="TEST",
            name=name,
            isin=isin,
            price_last=10_000,
        )
        service = FundService()
        result = await service.update_from_brsapi(symbol="TEST", brsapi=mock_brsapi)
        assert result["fund_type"] == expected_type, f"Expected {expected_type} for name={name}"


class TestUpdateFromBrsapiSession:
    """Tests for session commit/rollback behavior."""

    @pytest.mark.asyncio
    async def test_commit_on_success(self, mock_brsapi):
        """When session is present, commit is called on success."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched()
        mock_session = MagicMock()

        # Configure execute to return scalar_one_or_none=None (no existing record)
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=scalar_mock)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        service = FundService(session=mock_session)

        result = await service.update_from_brsapi(symbol="TST", brsapi=mock_brsapi)

        assert "error" not in result
        assert result["symbol"] == "TST"
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_on_commit_error(self, mock_brsapi):
        """When commit fails, rollback is called and error returned."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched()
        mock_session = MagicMock()

        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=scalar_mock)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=Exception("DB error"))
        mock_session.rollback = AsyncMock()

        service = FundService(session=mock_session)

        result = await service.update_from_brsapi(symbol="TST", brsapi=mock_brsapi)

        assert "error" in result
        assert "خطا در ذخیره‌سازی" in result["error"]
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_session_no_commit(self, mock_brsapi):
        """Without a session, no commit/rollback is attempted."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched()
        service = FundService()  # No session

        result = await service.update_from_brsapi(symbol="NEW", brsapi=mock_brsapi)

        assert "error" not in result
        # Should work fine without session


class TestUpdateFromBrsapiEdgeCases:
    """Edge cases for update_from_brsapi."""

    @pytest.mark.asyncio
    async def test_zero_values_handled_gracefully(self, mock_brsapi):
        """All numeric fields are 0 when enriched data has no values."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            price_last=0,
            price_yesterday=0,
            trade_volume=0,
            trade_value=0,
            trade_count=0,
            shares_count=0,
            market_value=0,
            buy_real_volume=0,
            buy_legal_volume=0,
            sell_real_volume=0,
            sell_legal_volume=0,
        )
        service = FundService()

        result = await service.update_from_brsapi(symbol="ZERO", brsapi=mock_brsapi)

        assert result["nav"] == 0
        assert result["nav_change"] == 0
        assert result["nav_change_pct"] == 0.0
        assert result["trade_volume"] == 0
        assert result["market_value"] == 0.0
        # حجم مبنا the one figure that must NOT be 0 here: the snapshot never carried one.
        assert result["base_volume"] is None

    @pytest.mark.asyncio
    async def test_base_volume_is_never_synthesized_from_shares(self, mock_brsapi):
        """حجم مبنا یک عدد اعلام‌شدهٔ بازار است، نه تابعی از تعداد واحدها.

        این رفتار قبلاً «۱٪ سهام» را می‌نوشت و ۵۱۲ ردیف صندوق با یک عدد نقدشوندگی ساختگی
        پر شده بود. اگر BrsApi حجم مبنا بدهد همان عدد می‌ماند، وگرنه None.
        """
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            shares_count=1_000_000,
        )
        service = FundService()

        result = await service.update_from_brsapi(symbol="BASE", brsapi=mock_brsapi)

        assert result["base_volume"] is None

        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            shares_count=1_000_000,
            base_volume=7_000,
        )
        quoted = await service.update_from_brsapi(symbol="BASE2", brsapi=mock_brsapi)

        assert quoted["base_volume"] == 7_000

    @pytest.mark.asyncio
    async def test_persian_symbol_in_url(self, mock_brsapi):
        """Persian symbols are passed correctly to BrsApi."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _make_enriched(
            symbol="فولاد",
            name="فولاد مبارکه",
        )
        service = FundService()

        result = await service.update_from_brsapi(symbol="فولاد", brsapi=mock_brsapi)

        assert result["symbol"] == "فولاد"
        assert result["name"] == "فولاد مبارکه"
        mock_brsapi.get_enriched_symbol_detail.assert_called_once_with("فولاد")

    @pytest.mark.asyncio
    async def test_missing_optional_fields(self, mock_brsapi):
        """Missing optional fields default to empty string."""
        mock_brsapi.get_enriched_symbol_detail.return_value = {
            "symbol": "MINIMAL",
            "price_last": 10_000,
            "shares_count": 1_000,
        }
        service = FundService()

        result = await service.update_from_brsapi(symbol="MINIMAL", brsapi=mock_brsapi)

        assert result["symbol"] == "MINIMAL"
        assert result["isin"] == ""
        assert result["buy_real_volume"] == 0
        assert result["buy_legal_volume"] == 0
        assert result["sell_real_volume"] == 0
        assert result["sell_legal_volume"] == 0
