"""Paper Trading (Gold Desk) — شبیه‌سازی معاملات طلا بدون پول واقعی.

این ماژول کاملاً مجزا از ``portfolio.py`` (معاملات واقعی) و
``services/paper_trading_service.py`` (کاغذی سهام) است.

ویژگی‌ها:
- **paper account جداگانه**: هر portfolio_id یک حساب کاغذی مستقل.
- **team view**: هر کسی می‌تواند همه portfolio‌ها را ببیند (list_paper_portfolios).
- **Redis-backed** (TTL 30 روز)؛ نیازی به DB ندارد.
- **میانگین هزینهٔ موزون** (WAV) برای محاسبه موقعیت‌ها.
- **InsufficientPaperHoldingError** اگر فروش بیش از موجودی.

الگوی injectable cache از WS3/WS5/WS8 پیروی می‌کند.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from core.time import utc_now_naive

logger = logging.getLogger(__name__)

REDIS_KEY_PAPER = "golddesk:paper:portfolios"
PAPER_TTL_DAYS: int = 30

# حداقل مقدار float برای تشخیص «کاملاً بسته»
_QTY_EPS = 1e-9


# ─── خطاها ───────────────────────────────────────────────────────────────────

class InsufficientPaperHoldingError(ValueError):
    """فروش بیش از موجودی کاغذی."""


# ─── dataclasses ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PaperGoldTrade:
    """یک معاملهٔ کاغذی طلا."""

    trade_id: str
    portfolio_id: str
    symbol: str           # مثال: IR_COIN_EMAMI، XAUUSD
    direction: str        # "buy" | "sell"
    quantity: float       # گرم یا عدد سکه
    price: float          # قیمت هر واحد (تومان یا دلار)
    traded_at: str        # ISO8601 UTC
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperGoldPosition:
    """موقعیت فعلی کاغذی برای یک نماد."""

    symbol: str
    quantity: float
    avg_cost: float       # میانگین هزینهٔ موزون هر واحد
    total_cost: float     # quantity × avg_cost

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperGoldPortfolio:
    """یک portfolio کاغذی طلا با مجموعه‌ای از معاملات."""

    portfolio_id: str
    display_name: str
    created_at: str       # ISO8601 UTC
    initial_cash: float   # سرمایهٔ اولیهٔ فرضی
    trades: list[PaperGoldTrade]  # list داخل frozen: ref ثابت، محتوا تغییر نمی‌کند

    def to_dict(self) -> dict[str, Any]:
        d = {
            "portfolio_id": self.portfolio_id,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "initial_cash": self.initial_cash,
            "trades": [t.to_dict() for t in self.trades],
        }
        return d


# ─── محاسبهٔ موقعیت‌ها (pure function) ───────────────────────────────────────

def compute_paper_positions(trades: list[PaperGoldTrade]) -> list[PaperGoldPosition]:
    """لیست معاملات → لیست موقعیت‌های فعال (WAV cost basis).

    Raises:
        InsufficientPaperHoldingError: اگر فروش بیش از موجودی باشد.
    """
    qty: dict[str, float] = {}
    cost: dict[str, float] = {}   # symbol → total cost (qty × avg)

    for trade in trades:
        sym = trade.symbol
        if trade.direction == "buy":
            prev_qty = qty.get(sym, 0.0)
            prev_cost = cost.get(sym, 0.0)
            new_qty = prev_qty + trade.quantity
            new_cost = prev_cost + trade.quantity * trade.price
            qty[sym] = new_qty
            cost[sym] = new_cost
        elif trade.direction == "sell":
            held = qty.get(sym, 0.0)
            if trade.quantity > held + _QTY_EPS:
                raise InsufficientPaperHoldingError(
                    f"فروش {trade.quantity} واحد {sym!r} بیش از موجودی {held:.6f} است"
                )
            new_qty = held - trade.quantity
            if new_qty < _QTY_EPS:
                # کاملاً بسته شد
                qty[sym] = 0.0
                cost[sym] = 0.0
            else:
                # avg_cost تغییر نمی‌کند
                prev_avg = cost.get(sym, 0.0) / held if held > _QTY_EPS else 0.0
                qty[sym] = new_qty
                cost[sym] = new_qty * prev_avg

    positions = []
    for sym, q in qty.items():
        if q <= _QTY_EPS:
            continue
        c = cost.get(sym, 0.0)
        avg = c / q if q > _QTY_EPS else 0.0
        positions.append(PaperGoldPosition(
            symbol=sym,
            quantity=q,
            avg_cost=avg,
            total_cost=c,
        ))
    return sorted(positions, key=lambda p: p.symbol)


# ─── Redis helpers ────────────────────────────────────────────────────────────

def _load_all(raw: str | None) -> dict[str, PaperGoldPortfolio]:
    """JSON ذخیره‌شده → dict[portfolio_id → PaperGoldPortfolio]."""
    if not raw:
        return {}
    try:
        data: dict[str, Any] = json.loads(raw)
        result = {}
        for pid, pdata in data.items():
            trades = [PaperGoldTrade(**t) for t in pdata.get("trades", [])]
            result[pid] = PaperGoldPortfolio(
                portfolio_id=pdata["portfolio_id"],
                display_name=pdata["display_name"],
                created_at=pdata["created_at"],
                initial_cash=pdata["initial_cash"],
                trades=trades,
            )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("paper trading deserialize failed: %s", exc)
        return {}


def _dump_all(portfolios: dict[str, PaperGoldPortfolio]) -> str:
    return json.dumps(
        {pid: p.to_dict() for pid, p in portfolios.items()},
        ensure_ascii=False,
    )


# ─── API توابع async ──────────────────────────────────────────────────────────

async def create_paper_portfolio(
    portfolio_id: str,
    display_name: str,
    initial_cash: float = 0.0,
    cache=None,
) -> PaperGoldPortfolio:
    """یک portfolio کاغذی جدید می‌سازد و در Redis ذخیره می‌کند.

    اگر portfolio_id از قبل وجود داشت، بازنویسی می‌شود.
    """
    from core.cache import get_cache

    _cache = cache if cache is not None else get_cache()
    portfolio = PaperGoldPortfolio(
        portfolio_id=portfolio_id,
        display_name=display_name,
        created_at=utc_now_naive().isoformat() + "Z",
        initial_cash=initial_cash,
        trades=[],
    )
    try:
        raw = await _cache.get(REDIS_KEY_PAPER)
        all_p = _load_all(raw)
        all_p[portfolio_id] = portfolio
        await _cache.set(REDIS_KEY_PAPER, _dump_all(all_p), ttl=PAPER_TTL_DAYS * 86_400)
    except Exception as exc:  # noqa: BLE001
        logger.warning("paper portfolio create failed: %s", exc)
    return portfolio


async def get_paper_portfolio(
    portfolio_id: str,
    cache=None,
) -> PaperGoldPortfolio | None:
    """یک portfolio را برمی‌گرداند؛ None اگر پیدا نشود."""
    from core.cache import get_cache

    _cache = cache if cache is not None else get_cache()
    try:
        raw = await _cache.get(REDIS_KEY_PAPER)
        return _load_all(raw).get(portfolio_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("paper portfolio get failed: %s", exc)
        return None


async def add_paper_trade(
    trade: PaperGoldTrade,
    cache=None,
) -> None:
    """معامله را به portfolio اضافه می‌کند.

    ابتدا موقعیت‌های جدید را محاسبه می‌کند تا InsufficientPaperHoldingError
    قبل از ذخیره‌سازی رخ دهد (portfolio دست‌نخورده می‌ماند اگر خطا باشد).

    Raises:
        KeyError: اگر portfolio_id در cache وجود نداشته باشد.
        InsufficientPaperHoldingError: اگر فروش بیش از موجودی باشد.
    """
    from core.cache import get_cache

    _cache = cache if cache is not None else get_cache()
    raw = await _cache.get(REDIS_KEY_PAPER)
    all_p = _load_all(raw)

    portfolio = all_p.get(trade.portfolio_id)
    if portfolio is None:
        raise KeyError(f"portfolio {trade.portfolio_id!r} not found")

    new_trades = list(portfolio.trades) + [trade]
    # اعتبارسنجی پیش از ذخیره
    compute_paper_positions(new_trades)  # raises InsufficientPaperHoldingError اگر لازم

    updated = PaperGoldPortfolio(
        portfolio_id=portfolio.portfolio_id,
        display_name=portfolio.display_name,
        created_at=portfolio.created_at,
        initial_cash=portfolio.initial_cash,
        trades=new_trades,
    )
    all_p[portfolio.portfolio_id] = updated
    await _cache.set(REDIS_KEY_PAPER, _dump_all(all_p), ttl=PAPER_TTL_DAYS * 86_400)


async def list_paper_portfolios(
    cache=None,
) -> list[PaperGoldPortfolio]:
    """همهٔ portfolio‌ها (team view) را برمی‌گرداند.

    Returns:
        لیستی از ``PaperGoldPortfolio``، خالی اگر هیچ portfolio‌ای نباشد.
    """
    from core.cache import get_cache

    _cache = cache if cache is not None else get_cache()
    try:
        raw = await _cache.get(REDIS_KEY_PAPER)
        return list(_load_all(raw).values())
    except Exception as exc:  # noqa: BLE001
        logger.warning("paper portfolio list failed: %s", exc)
        return []
