"""Alert Engine — ارزیابی قوانین + dedup + dispatch.

هر ۲ دقیقه snapshot تازه می‌گیرد، قوانین enabled را بررسی می‌کند،
اگه شرط برقرار و cooldown رعایت شده → رویداد ثبت + ارسال (in-app / telegram).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time import utc_now_naive

from .constants import (
    PORTFOLIO_CONCENTRATION_WARN_PCT,
    PORTFOLIO_DRAWDOWN_WARN_PCT,
    PORTFOLIO_DRIFT_TOLERANCE_PCT,
)
from .models import AlertEventModel, AlertRuleModel
from .schemas import SnapshotResponse
from .telegram_bot import TelegramConfig, format_alert_message, send_message

logger = logging.getLogger(__name__)


# انواع قانونی که مقدارشان از معیارهای ریسک پرتفوی می‌آید (نه snapshot).
PORTFOLIO_RULE_TYPES: frozenset[str] = frozenset(
    {
        "portfolio_concentration_above",
        "portfolio_drift_above",
        "portfolio_drawdown_above",
    }
)

# نگاشت نوع قانون → کلید معیار در ``PortfolioPerformance.risk_metrics()``
_PORTFOLIO_METRIC_KEYS: dict[str, str] = {
    "portfolio_concentration_above": "portfolio_concentration_pct",
    "portfolio_drift_above": "portfolio_drift_pct",
    "portfolio_drawdown_above": "portfolio_drawdown_pct",
}


def _get_portfolio_value(metrics: Mapping[str, float | None] | None, rule_type: str) -> float | None:
    """مقدار معیار ریسک برای قانون‌های پرتفوی (None اگر معیار در دسترس نباشد)."""
    if not metrics:
        return None
    value = metrics.get(_PORTFOLIO_METRIC_KEYS.get(rule_type, ""))
    return None if value is None else float(value)


def _get_value(snap: SnapshotResponse, rule_type: str, symbol: str | None) -> float | None:
    """استخراج مقدار مورد بررسی از snapshot."""
    if rule_type == "bubble_above" or rule_type == "bubble_below":
        # نماد پیش‌فرض: coin_emami
        sym = symbol or "coin_emami"
        coin = snap.coins.get(sym)
        return coin.bubble_pct if coin else None
    if rule_type == "nav_bubble_above":
        # صندوق پیش‌فرض: عیار
        for f in snap.funds:
            if (symbol and f.symbol == symbol) or (not symbol and "عیار" in f.symbol):
                return f.bubble_pct
        return None
    if rule_type == "price_above" or rule_type == "price_below":
        sym = symbol or "coin_emami"
        if sym in snap.coins:
            return snap.coins[sym].market_price
        if sym in snap.gold:
            return snap.gold[sym].market_price
        return None
    if rule_type == "score_above" or rule_type == "score_below":
        return float(snap.score.total)
    if rule_type == "parity_gap_above":
        return abs(snap.references.aed_gap_pct)
    return None


def _operator_for(rule_type: str, threshold: float) -> str:
    """جهت عملگر پیام از نوع قانون — نه از علامت threshold (GS-13).

    پیش‌تر مثلاً قانون ``bubble_below`` با threshold=3.0 پیام «> 3.00» رندر
    می‌کرد چون جهت از علامت threshold خوانده می‌شد.
    """
    if rule_type in ("bubble_below", "price_below", "score_below"):
        return "<"
    if rule_type in (
        "bubble_above",
        "nav_bubble_above",
        "price_above",
        "score_above",
        "parity_gap_above",
        "portfolio_concentration_above",
        "portfolio_drift_above",
        "portfolio_drawdown_above",
    ):
        return ">"
    return ">" if threshold > 0 else "<"


def _check_condition(rule_type: str, value: float, threshold: float) -> bool:
    if rule_type == "bubble_above":
        return value > threshold
    if rule_type == "bubble_below":
        return value < threshold
    if rule_type == "nav_bubble_above":
        return value > threshold
    if rule_type == "price_above":
        return value > threshold
    if rule_type == "price_below":
        return value < threshold
    if rule_type == "score_above":
        return value > threshold
    if rule_type == "score_below":
        return value < threshold
    if rule_type == "parity_gap_above":
        return value > threshold
    if rule_type in PORTFOLIO_RULE_TYPES:
        return value > threshold
    return False


async def _send_telegram(rule: AlertRuleModel, snap: SnapshotResponse, value: float) -> bool:
    cfg = TelegramConfig.from_env()
    if not cfg.is_configured():
        return False
    chat_id = rule.telegram_chat_id or cfg.default_chat_id
    if not chat_id:
        return False
    msg = format_alert_message(
        rule_name=rule.name,
        symbol=rule.symbol or "global",
        trigger_value=value,
        threshold=rule.threshold,
        extra=f"Score: {snap.score.total} | AED gap: {snap.references.aed_gap_pct:.2f}%",
    )
    return await send_message(msg, chat_id=chat_id, config=cfg)


async def evaluate_rules(
    session: AsyncSession,
    snap: SnapshotResponse,
    *,
    portfolio_metrics: Mapping[str, float | None] | None = None,
) -> list[AlertEventModel]:
    """بررسی همه قوانین enabled. بازمی‌گرداند لیست رویدادهای ثبت‌شده.

    قوانین مبتنی بر snapshot مقدارشان از ``snap`` می‌آید؛ قوانین پرتفوی
    (``PORTFOLIO_RULE_TYPES``) از ``portfolio_metrics`` — نبود معیار به‌معنای
    «ارزیابی نشد» است، نه «صفر» (هیچ هشدار کاذبی ساخته نمی‌شود).
    """
    stmt = select(AlertRuleModel).where(AlertRuleModel.enabled == True)  # noqa: E712
    result = await session.execute(stmt)
    rules = result.scalars().all()

    events: list[AlertEventModel] = []
    now = utc_now_naive()

    for rule in rules:
        if rule.rule_type in PORTFOLIO_RULE_TYPES:
            value = _get_portfolio_value(portfolio_metrics, rule.rule_type)
        else:
            value = _get_value(snap, rule.rule_type, rule.symbol)
        if value is None:
            continue
        if not _check_condition(rule.rule_type, value, rule.threshold):
            continue

        # Cooldown check
        if rule.last_fired_at:
            elapsed = now - rule.last_fired_at
            if elapsed < timedelta(minutes=rule.cooldown_minutes):
                continue

        # ساخت رویداد
        event = AlertEventModel(
            rule_id=rule.id,
            rule_name=rule.name,
            symbol=rule.symbol,
            trigger_value=value,
            threshold=rule.threshold,
            message=(
                f"{rule.name}: {value:.2f} {_operator_for(rule.rule_type, rule.threshold)} "
                f"{rule.threshold:.2f}"
            ),
            channel=rule.channel,
        )
        session.add(event)
        rule.last_fired_at = now
        events.append(event)

        # ارسال telegram
        if rule.channel in ("telegram", "both"):
            await _send_telegram(rule, snap, value)

    if events:
        await session.commit()
        logger.info("Alert engine: %d events fired", len(events))
    return events


# ── Seed قوانین پیش‌فرض ────────────────────────────────────────

DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "name": "حباب سکه بالا (سبز→قرمز)",
        "rule_type": "bubble_above",
        "symbol": "coin_emami",
        "threshold": 22.0,
        "channel": "both",
        "cooldown_minutes": 60,
    },
    {
        "name": "حباب سکه پایین (فرصت خرید)",
        "rule_type": "bubble_below",
        "symbol": "coin_emami",
        "threshold": 3.0,
        "channel": "both",
        "cooldown_minutes": 120,
    },
    {
        "name": "NAV صندوق عیار بالا",
        "rule_type": "nav_bubble_above",
        "symbol": "عیار",
        "threshold": 3.0,
        "channel": "inapp",
        "cooldown_minutes": 60,
    },
    {
        "name": "شکاف درهم شدید",
        "rule_type": "parity_gap_above",
        "threshold": 3.0,
        "channel": "inapp",
        "cooldown_minutes": 30,
    },
    {
        "name": "امتیاز سبز شد",
        "rule_type": "score_above",
        "threshold": 80,
        "channel": "both",
        "cooldown_minutes": 240,
    },
    # ── قوانین پرتفوی (از معیارهای ریسک واقعی — نه snapshot) ──
    {
        "name": "تمرکز پرتفوی بالا",
        "rule_type": "portfolio_concentration_above",
        "symbol": None,
        "threshold": PORTFOLIO_CONCENTRATION_WARN_PCT,
        "channel": "inapp",
        "cooldown_minutes": 720,
    },
    {
        "name": "انحراف ری‌بالانس از وزن هدف",
        "rule_type": "portfolio_drift_above",
        "symbol": None,
        "threshold": PORTFOLIO_DRIFT_TOLERANCE_PCT,
        "channel": "inapp",
        "cooldown_minutes": 720,
    },
    {
        "name": "افت سرمایهٔ پرتفوی",
        "rule_type": "portfolio_drawdown_above",
        "symbol": None,
        "threshold": PORTFOLIO_DRAWDOWN_WARN_PCT,
        "channel": "both",
        "cooldown_minutes": 720,
    },
]


async def seed_default_rules(session: AsyncSession) -> int:
    """درج قوانین پیش‌فرض در صورت عدم وجود."""
    stmt = select(AlertRuleModel).limit(1)
    if (await session.execute(stmt)).first():
        return 0

    for r in DEFAULT_RULES:
        session.add(AlertRuleModel(**r, enabled=True))
    await session.commit()
    return len(DEFAULT_RULES)


__all__ = [
    "DEFAULT_RULES",
    "PORTFOLIO_RULE_TYPES",
    "evaluate_rules",
    "seed_default_rules",
]
