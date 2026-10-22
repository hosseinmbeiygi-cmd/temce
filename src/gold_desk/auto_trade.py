"""Auto-Trade — سیستم معامله خودکار با dry-run + broker adapter.

این ماژول دو حالت دارد:
1. **dry-run** (پیش‌فرض): فقط سیگنال می‌دهد، هیچ معامله‌ای انجام نمی‌شود
2. **live**: با broker API واقعی (نیاز API key) معامله می‌کند

جریان:
1. snapshot → score → decision
2. اگه GREEN و dry_run=False → معامله خودکار
3. ثبت trade در DB
4. ارسال alert (Telegram)
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from core.time import utc_now_naive

from .portfolio import get_current_prices, get_holdings_grouped

logger = logging.getLogger(__name__)

REDIS_KEY_AUTOTRADE_CONFIG = "golddesk:autotrade:config"
REDIS_KEY_AUTOTRADE_LOG = "golddesk:autotrade:log"

Action = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class AutoTradeConfig:
    """تنظیمات auto-trade."""

    enabled: bool
    dry_run: bool  # True = فقط لاگ، False = broker API
    max_position_irt: float  # سقف خرید هر معامله
    min_score_to_buy: int  # حداقل score برای خرید (مثلاً 75)
    min_score_to_sell: int  # حداقل score برای فروش
    cooldown_hours: int  # فاصله بین معاملات

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TradeSignal:
    """سیگنال تولید‌شده توسط auto-trade."""

    action: Action
    symbol: str
    amount_irt: float
    confidence: float
    reason: str
    dry_run: bool
    ts: datetime

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat()
        return d


def default_config() -> AutoTradeConfig:
    return AutoTradeConfig(
        enabled=False,  # به‌صورت پیش‌فرض غیرفعال
        dry_run=True,
        max_position_irt=50_000_000,
        min_score_to_buy=80,
        min_score_to_sell=20,
        cooldown_hours=24,
    )


def decide_action(
    score: int,
    config: AutoTradeConfig,
    current_position_value: float,
) -> tuple[Action, str]:
    """تصمیم‌گیری بر اساس score + config + position."""
    if not config.enabled:
        return "hold", "auto-trade غیرفعال"

    if score >= config.min_score_to_buy:
        if current_position_value >= config.max_position_irt * 2:
            return "hold", f"position کافی ({current_position_value:,.0f} تومان)"
        return "buy", f"score {score} ≥ {config.min_score_to_buy} (سبز)"

    if score <= config.min_score_to_sell:
        if current_position_value < 1_000_000:
            return "hold", "position برای فروش کم است"
        return "sell", f"score {score} ≤ {config.min_score_to_sell} (قرمز)"

    return "hold", f"score {score} در ناحیه زرد"


async def get_config() -> AutoTradeConfig:
    """بارگذاری config از Redis یا default."""
    with contextlib.suppress(Exception):
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(REDIS_KEY_AUTOTRADE_CONFIG)
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return AutoTradeConfig(**data)
    return default_config()


async def save_config(config: AutoTradeConfig) -> None:
    """ذخیره config."""
    try:
        from core.cache import get_cache

        cache = get_cache()
        await cache.set(REDIS_KEY_AUTOTRADE_CONFIG, json.dumps(config.to_dict()), ttl=None)
    except Exception as exc:
        logger.warning("save_config failed: %s", exc)


async def generate_signal(
    session: AsyncSession,
    snapshot: dict,
    config: AutoTradeConfig | None = None,
) -> TradeSignal | None:
    """تولید سیگنال بر اساس snapshot + portfolio."""
    if config is None:
        config = await get_config()

    if not config.enabled:
        return None

    score = snapshot.get("score", {}).get("total", 0)
    prices = get_current_prices(snapshot)

    # portfolio موجود
    try:
        portfolio = await get_holdings_grouped(session, prices)
        current_position = portfolio.total_value
    except Exception:
        current_position = 0

    action, reason = decide_action(score, config, current_position)

    if action == "hold":
        return None  # فقط buy/sell لاگ می‌شود

    # استفاده از coin_emami به‌عنوان default symbol
    symbol = "IR_COIN_EMAMI"
    # مبلغ = سقف پیکربندی؛ پیش‌تر با سقف ثابت ۵۰M بریده می‌شد و مقدار config
    # (مثلاً ۵۰۰M) نادیده می‌رفت (GS-18).
    amount = config.max_position_irt

    return TradeSignal(
        action=action,
        symbol=symbol,
        amount_irt=amount,
        confidence=score / 100.0,
        reason=reason,
        dry_run=config.dry_run,
        ts=utc_now_naive(),
    )


async def execute_signal(
    session: AsyncSession,
    signal: TradeSignal,
) -> dict:
    """اجرای سیگنال (dry-run یا live).

    dry-run هیچ معامله‌ای ثبت نمی‌کند — پیش‌تر یک ردیف ``gold_trades`` با
    ``quantity=0, price=0`` درج می‌کرد که داده معامله‌گر را آلوده می‌کرد (GS-18).
    """
    if signal.dry_run:
        logger.info(
            "[DRY-RUN] %s %s %s", signal.action, signal.symbol, f"{signal.amount_irt:,.0f}"
        )
        return {
            "status": "dry_run",
            "executed": False,
            "persisted": False,
            "simulated": signal.to_dict(),
        }

    # Live: نیاز broker API واقعی که پیاده‌سازی نشده است؛ هرگز اجرا/موفق گزارش نمی‌شود.
    broker = os.getenv("GOLD_BROKER_API", "").strip()
    if not broker:
        logger.warning("GOLD_BROKER_API not set, skipping live trade")
        return {"status": "skipped", "reason": "no broker configured", "executed": False}
    logger.error("live trading is not implemented; refusing to report execution (broker=%s)", broker)
    return {
        "status": "not_implemented",
        "broker": broker,
        "executed": False,
        "reason": "live broker adapter is not implemented",
    }
