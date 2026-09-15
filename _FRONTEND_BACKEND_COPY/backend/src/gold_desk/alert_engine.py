"""Alert Engine — ارزیابی قوانین + dedup + dispatch.

هر ۲ دقیقه snapshot تازه می‌گیرد، قوانین enabled را بررسی می‌کند،
اگه شرط برقرار و cooldown رعایت شده → رویداد ثبت + ارسال (in-app / telegram).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AlertEventModel, AlertRuleModel
from .schemas import SnapshotResponse
from .telegram_bot import TelegramConfig, format_alert_message, send_message

logger = logging.getLogger(__name__)


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


async def evaluate_rules(session: AsyncSession, snap: SnapshotResponse) -> list[AlertEventModel]:
    """بررسی همه قوانین enabled. بازمی‌گرداند لیست رویدادهای ثبت‌شده."""
    stmt = select(AlertRuleModel).where(AlertRuleModel.enabled == True)  # noqa: E712
    result = await session.execute(stmt)
    rules = result.scalars().all()

    events: list[AlertEventModel] = []
    now = datetime.utcnow()

    for rule in rules:
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
            message=f"{rule.name}: {value:.2f} {'>' if rule.threshold > 0 else '<'} {rule.threshold:.2f}",
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
