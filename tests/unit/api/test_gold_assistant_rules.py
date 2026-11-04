"""قرارداد HTTP برای ``GET /api/v1/gold/assistant-rules``.

صفحه‌های طلا و نقره اعداد خود (تعرفهٔ §۲۷.۱، فیلتر §۲۶، ساعت §۲۷.۳) را از همین
endpoint می‌خوانند. پس این تست دو چیز را قفل می‌کند:

* مسیر واقعاً mount شده و پاسخ، عیناً همان چیزی است که
  ``core.config.acceptance_loader`` می‌سازد — نه یک کپی دست‌ساز؛
* گیت سیگنال سمت سرور (``services.signal_decision_engine``) و این پاسخ از یک
  منبع می‌خوانند، چون اختلاف عددی بین صفحه و موتور، سیگنالی می‌سازد که صفحه
  آن را تأیید نمی‌کند.

از اپ واقعی (``apps.api.app``) استفاده می‌شود تا mount و شکل payload اعتبارسنجی
شود، مطابق الگوی ``test_golddesk_http``.
"""

from __future__ import annotations

from httpx import AsyncClient

RULES_URL = "/api/v1/gold/assistant-rules"


async def test_endpoint_is_mounted_and_serves_the_acceptance_config(
    client: AsyncClient,
) -> None:
    from core.config.acceptance_loader import get_assistant_rules

    response = await client.get(RULES_URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    # عیناً همان خروجی loader — نه نسخهٔ دست‌ساز با اعداد کپی‌شده.
    assert body["data"] == get_assistant_rules()


async def test_signal_filter_thresholds_are_served_for_the_pages(
    client: AsyncClient,
) -> None:
    """§۲۶ — کف سود خالص و نسبت ریسک/ریوارد با منشأشان سرو می‌شوند."""
    response = await client.get(RULES_URL)
    signal_filter = response.json()["data"]["signal_filter"]

    assert float(signal_filter["min_net_profit_pct"]) == 2.0
    assert float(signal_filter["min_risk_reward"]) == 2.0
    assert signal_filter["require_positive_ev"] is True
    assert signal_filter["provenance"]["min_net_profit_pct"] == "spec"
    # «۲ به ۱» در سند پیشنهاد نویسنده است و باید با همان برچسب برود (§۲۸.۲).
    assert signal_filter["provenance"]["min_risk_reward"] in {"spec", "assumption"}


async def test_page_thresholds_match_the_server_side_gate(client: AsyncClient) -> None:
    """صفحه و موتور باید یک عدد بدهند؛ وگرنه فیلتر صفحه نمایشی می‌شود."""
    from services.signal_decision_engine import _value_filter

    served = (await client.get(RULES_URL)).json()["data"]["signal_filter"]
    engine = _value_filter()

    assert float(served["min_net_profit_pct"]) == float(engine["min_net_profit_pct"])
    assert float(served["min_risk_reward"]) == float(engine["min_risk_reward"])


async def test_fee_schedule_keeps_unknown_instruments_as_null(
    client: AsyncClient,
) -> None:
    """§۲۷.۱ — ابزاری که نرخ قابت‌اتکا ندارد باید `null` بماند، نه صفر."""
    instruments = (await client.get(RULES_URL)).json()["data"]["fee_schedule"]["instruments"]

    assert instruments["commodity_fund"]["fee_per_side"] is not None
    assert instruments["commodity_fund"]["round_trip_fee_per_side"] is not None
    for unknown in ("futures", "option"):
        assert instruments[unknown]["fee_per_side"] is None
        assert instruments[unknown]["round_trip_fee_per_side"] is None
        assert instruments[unknown]["provenance"] == "unavailable"


async def test_market_hours_and_settlement_are_served(client: AsyncClient) -> None:
    """§۲۷.۳ — ساعت، دامنه و تسویهٔ بازار ایران از پیکربندی می‌آید."""
    hours = (await client.get(RULES_URL)).json()["data"]["market_hours"]

    assert hours["sat_to_wed"] == {"pre_open": "11:45", "open": "12:00", "close": "18:00"}
    assert hours["thursday"]["close"] == "15:00"
    assert hours["friday_closed"] is True
    assert float(hours["price_band_pct"]) == 10.0
    assert hours["settlement_days"] == 1
