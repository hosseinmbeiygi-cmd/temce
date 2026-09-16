"""🧵 Stock Read-Through Service — تابلو زنده + میکرواستراکچر (بخش ۳-د).

الگوی Read-Through سه‌لایه:
  - L1: کش درون‌حافظه فرآیند با TTL ۳ ثانیه (Hot Tickers)
  - L2: کش Redis (Hash) برای tape زنده — TTL ۵ ثانیه در ساعات بازار
  - DB: جدول stock_live_tape + snapshots موجود (برای پاسخ < ۵۰ms)
  - JIT: Cache Miss/Stale → BrsApi (Mutex روی ``stock:{isin}:lock``)

TTL داینامیک: در ساعات بازار (۰۸:۴۵–۱۲:۳۵) کوتاه؛ خارج از بازار فریز.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from services.stock_signal_engine import (
    LayerInputs,
    compute_composite_signal,
    compute_tech_score,
)
from services.stock_tape_engine import compute_tape_reading
from services.stock_technical_engine import compute_indicator_snapshot

logger = get_logger(__name__)

# ── TTL policies ─────────────────────────────────────────────────────────────

TTL_TAPE_LIVE = int(getattr(settings, "stock_ttl_tape_live", 3))       # ۲-۵ ثانیه
TTL_TAPE_CLOSED = 3600 * 8       # خارج از بازار: تا جلسه بعد فریز
TTL_INDICATORS = 3600 * 12       # precomputed شبانه
TTL_SIGNAL = 3600                # امتیاز کامل: ساعتی
MUTEX_TTL = 30

# ── L1 درون‌حافظه (Hot Tickers) ──────────────────────────────────────────────

_L1_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_L1_LOCK = asyncio.Lock()


async def _l1_get(key: str, ttl: float) -> dict[str, Any] | None:
    async with _L1_LOCK:
        entry = _L1_CACHE.get(key)
        if entry is None:
            return None
        ts, payload = entry
        if time.monotonic() - ts > ttl:
            return None
        return payload


async def _l1_put(key: str, payload: dict[str, Any]) -> None:
    async with _L1_LOCK:
        # جلوگیری از رشد بی‌رویه
        if len(_L1_CACHE) > 5000:
            _L1_CACHE.clear()
        _L1_CACHE[key] = (time.monotonic(), payload)


# ── Mutex توزیع‌شده روی ISIN (استفاده از موتور مشترک صندوق‌ها) ───────────────

from services.fund_read_through import _shared_mutex  # noqa: E402 — reuse


def _is_market_open() -> bool:
    import datetime as dt

    try:
        import pytz

        now = datetime.now(pytz.timezone("Asia/Tehran")).time()
    except Exception:
        now = dt.datetime.now().time()
    return dt.time(8, 45) <= now <= dt.time(12, 35)


class StockReadThroughService:
    """سرویس Read-Through سهام — هر متد معادل یک تب فرانت‌اند."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._mutex = _shared_mutex

    # ── ۱. Tape زنده (تب ۱) ──

    async def get_live_tape(self, symbol: str, isin: str | None = None) -> dict[str, Any]:
        cache_key = f"tape:{symbol}"
        ttl = TTL_TAPE_LIVE if _is_market_open() else TTL_TAPE_CLOSED

        cached = await _l1_get(cache_key, ttl)
        if cached is not None:
            return {**cached, "freshness": "live"}

        # L2 — Redis
        redis_payload = await self._redis_get(cache_key)
        if redis_payload is not None:
            age = time.time() - redis_payload.get("_ts", 0)
            if age < ttl:
                await _l1_put(cache_key, redis_payload)
                return {**redis_payload, "freshness": "live"}

        # DB — آخرین tape ذخیره‌شده
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT symbol, last_price, close_price, yesterday_price, price_first,
                           price_min, price_max, price_change_pct, close_change_pct,
                           trade_volume, trade_value, trade_count,
                           buy_real_volume, sell_real_volume, buy_real_count, sell_real_count,
                           buy_real_value, sell_real_value,
                           buy_legal_volume, sell_legal_volume, buy_legal_value, sell_legal_value,
                           buy_orders_json, sell_orders_json, base_volume,
                           allowed_price_min, allowed_price_max, quoted_at
                    FROM stock_live_tape WHERE symbol = :sym
                    """
                ),
                {"sym": symbol},
            )
        ).first()

        if row is not None:
            age = (
                (datetime.utcnow() - row[27]).total_seconds()
                if row[27] is not None and isinstance(row[27], datetime)
                else 1e18
            )
            if age < ttl:
                payload = self._tape_row_to_dict(row)
                await _l1_put(cache_key, payload)
                await self._redis_put(cache_key, payload)
                return {**payload, "freshness": "live"}

        # Stale/Miss → JIT از BrsApi (Mutex روی ISIN)
        async with self._guarded(f"stock:{isin or symbol}:lock"):
            fresh = await self._fetch_and_store_tape(symbol, isin)
        if fresh is not None:
            return {**fresh, "freshness": "live"}

        # Fallback: داده کهنه از DB (Stale-While-Revalidate UX)
        if row is not None:
            payload = self._tape_row_to_dict(row)
            return {**payload, "freshness": "stale"}
        return {"symbol": symbol, "freshness": "stale", "data_available": False}

    async def _guarded(self, name: str) -> Any:
        got = await self._mutex.acquire(name)
        if got:
            return _Release(self._mutex, name)

        # منتظر سازنده (حداکثر ۸ ثانیه) سپس ادامه با داده موجود
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            await asyncio.sleep(0.3)
            row = await self.session.execute(
                text("SELECT quoted_at FROM stock_live_tape WHERE symbol = :sym"),
                {"sym": name.split(":")[1] if name.count(":") >= 2 else name},
            )
            r = row.first()
            if r is not None and r[0] is not None:
                return _NoRelease()
        return _Release(self._mutex, name, owned=False)

    async def _redis_get(self, key: str) -> dict[str, Any] | None:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            raw = await r.get(f"stocks:{key}")
            await r.aclose()
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    async def _redis_put(self, key: str, payload: dict[str, Any]) -> None:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            await r.setex(f"stocks:{key}", TTL_TAPE_LIVE * 2, json.dumps(payload, default=str))
            await r.aclose()
        except Exception:
            pass

    async def _fetch_and_store_tape(self, symbol: str, isin: str | None) -> dict[str, Any] | None:
        """واکشی از BrsApi (snapshot موجود — بدون call اضافه) و Upsert."""
        try:
            rows = (
                await self.session.execute(
                    text(
                        """
                        SELECT symbol, isin, price_last, price_close, price_yesterday, price_first,
                               price_min, price_max, price_last_change_pct, price_close_change_pct,
                               trade_volume, trade_value, trade_count,
                               buy_real_volume, sell_real_volume, buy_real_count, sell_real_count,
                               buy_real_value, sell_real_value,
                               buy_legal_volume, sell_legal_volume, buy_legal_value, sell_legal_value,
                               base_volume
                        FROM brsapi_symbol_snapshots
                        WHERE symbol = :sym
                        ORDER BY id DESC LIMIT 1
                        """
                    ),
                    {"sym": symbol},
                )
            ).first()
        except Exception:
            logger.exception("Tape fetch failed for %s", symbol)
            return None
        if rows is None:
            return None

        now = datetime.utcnow()
        payload = {
            "symbol": rows[0],
            "isin": rows[1] or isin,
            "last_price": rows[2],
            "close_price": rows[3],
            "yesterday_price": rows[4],
            "price_first": rows[5],
            "price_min": rows[6],
            "price_max": rows[7],
            "price_change_pct": rows[8],
            "close_change_pct": rows[9],
            "trade_volume": rows[10],
            "trade_value": rows[11],
            "trade_count": rows[12],
            "buy_real_volume": rows[13],
            "sell_real_volume": rows[14],
            "buy_real_count": rows[15],
            "sell_real_count": rows[16],
            "buy_real_value": rows[17],
            "sell_real_value": rows[18],
            "buy_legal_volume": rows[19],
            "sell_legal_volume": rows[20],
            "buy_legal_value": rows[21],
            "sell_legal_value": rows[22],
            "base_volume": rows[23],
            "quoted_at": str(now),
        }
        await self.session.execute(
            text(
                """
                INSERT INTO stock_live_tape (
                    symbol, isin, last_price, close_price, yesterday_price, price_first,
                    price_min, price_max, price_change_pct, close_change_pct,
                    trade_volume, trade_value, trade_count,
                    buy_real_volume, sell_real_volume, buy_real_count, sell_real_count,
                    buy_real_value, sell_real_value,
                    buy_legal_volume, sell_legal_volume, buy_legal_value, sell_legal_value,
                    base_volume, quoted_at, fetched_at)
                VALUES (:symbol, :isin, :last_price, :close_price, :yesterday_price, :price_first,
                        :price_min, :price_max, :price_change_pct, :close_change_pct,
                        :trade_volume, :trade_value, :trade_count,
                        :buy_real_volume, :sell_real_volume, :buy_real_count, :sell_real_count,
                        :buy_real_value, :sell_real_value,
                        :buy_legal_volume, :sell_legal_volume, :buy_legal_value, :sell_legal_value,
                        :base_volume, :quoted_at, now())
                ON CONFLICT (symbol) DO UPDATE SET
                    last_price = EXCLUDED.last_price, close_price = EXCLUDED.close_price,
                    yesterday_price = EXCLUDED.yesterday_price, price_first = EXCLUDED.price_first,
                    price_min = EXCLUDED.price_min, price_max = EXCLUDED.price_max,
                    price_change_pct = EXCLUDED.price_change_pct,
                    close_change_pct = EXCLUDED.close_change_pct,
                    trade_volume = EXCLUDED.trade_volume, trade_value = EXCLUDED.trade_value,
                    trade_count = EXCLUDED.trade_count,
                    buy_real_volume = EXCLUDED.buy_real_volume,
                    sell_real_volume = EXCLUDED.sell_real_volume,
                    buy_real_count = EXCLUDED.buy_real_count,
                    sell_real_count = EXCLUDED.sell_real_count,
                    buy_real_value = EXCLUDED.buy_real_value,
                    sell_real_value = EXCLUDED.sell_real_value,
                    buy_legal_volume = EXCLUDED.buy_legal_volume,
                    sell_legal_volume = EXCLUDED.sell_legal_volume,
                    buy_legal_value = EXCLUDED.buy_legal_value,
                    sell_legal_value = EXCLUDED.sell_legal_value,
                    base_volume = EXCLUDED.base_volume,
                    quoted_at = EXCLUDED.quoted_at, fetched_at = now()
                """
            ),
            payload,
        )
        await self.session.commit()
        await self._redis_put(f"tape:{symbol}", payload)
        return payload

    @staticmethod
    def _tape_row_to_dict(row: Any) -> dict[str, Any]:
        return {
            "symbol": row[0],
            "last_price": row[1],
            "close_price": row[2],
            "yesterday_price": row[3],
            "price_first": row[4],
            "price_min": row[5],
            "price_max": row[6],
            "price_change_pct": row[7],
            "close_change_pct": row[8],
            "trade_volume": row[9],
            "trade_value": row[10],
            "trade_count": row[11],
            "buy_real_volume": row[12],
            "sell_real_volume": row[13],
            "buy_real_count": row[14],
            "sell_real_count": row[15],
            "buy_real_value": row[16],
            "sell_real_value": row[17],
            "buy_legal_volume": row[18],
            "sell_legal_volume": row[19],
            "buy_legal_value": row[20],
            "sell_legal_value": row[21],
            "base_volume": row[24],
            "quoted_at": str(row[27]) if row[27] else None,
        }

    # ── ۲. Tabel-khani (ماتریس تابلوخوانی) ──

    async def get_tape_reading_matrix(self, symbol: str) -> dict[str, Any]:
        tape_res = await self.get_live_tape(symbol)
        tape = {k: v for k, v in tape_res.items() if k != "freshness"}

        # تاریخچه حجم ۲۰ روزه برای کشف حجم مشکوک
        vol_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT trade_volume FROM daily_history
                    WHERE symbol_id = (SELECT id FROM symbols WHERE code = :sym LIMIT 1)
                      AND trade_volume IS NOT NULL
                    ORDER BY trade_date DESC LIMIT 21
                    """
                ),
                {"sym": symbol},
            )
        ).fetchall()
        hist_vols = [float(r[0]) for r in vol_rows[1:]] if vol_rows else []
        current_vol = float(vol_rows[0][0]) if vol_rows else float(tape.get("trade_volume") or 0)

        matrix = compute_tape_reading(tape, volume_history_20d=hist_vols or None)
        matrix["current_volume"] = current_vol
        return matrix

    # ── ۳. Indicators (تب ۲) — از snapshot پیش‌محاسبه یا محاسبه JIT ──

    async def get_indicators(self, symbol: str) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT payload FROM (
                        SELECT to_jsonb(s) AS payload, s.computed_at
                        FROM stock_indicators_snapshot s
                        WHERE s.symbol = :sym
                        ORDER BY s.trade_date DESC LIMIT 1
                    ) t
                    """
                ),
                {"sym": symbol},
            )
        ).first()
        if row is not None and row[0]:
            payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            age_ok = payload.get("computed_at") is not None
            if age_ok:
                return {**payload, "source": "precomputed"}

        # JIT: از daily_history محاسبه کن
        candles = await self._load_daily_candles(symbol)
        snapshot = compute_indicator_snapshot(candles)
        if snapshot.get("ok"):
            snapshot["source"] = "jit"
        return snapshot

    async def _load_daily_candles(self, symbol: str, limit: int = 260) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT d.trade_date, d.price_first, d.price_max, d.price_min, d.price_last,
                           d.trade_volume, d.trade_value
                    FROM daily_history d
                    JOIN symbols s ON s.id = d.symbol_id
                    WHERE s.code = :sym AND d.price_last IS NOT NULL
                    ORDER BY d.trade_date DESC LIMIT :lim
                    """
                ),
                {"sym": symbol, "lim": limit},
            )
        ).fetchall()
        candles = [
            {
                "date": str(r[0]),
                "open": float(r[1] or r[4]),
                "high": float(r[2] or r[4]),
                "low": float(r[3] or r[4]),
                "close": float(r[4]),
                "volume": float(r[5] or 0),
                "value": float(r[6] or 0),
            }
            for r in reversed(rows)
        ]
        return candles

    # ── ۴. Signal کامل (کارت تصمیم‌گیری) ──

    async def get_full_signal(self, symbol: str) -> dict[str, Any]:
        tape_res = await self.get_live_tape(symbol)
        tape = {k: v for k, v in tape_res.items() if k != "freshness"}
        indicators = await self.get_indicators(symbol)
        tape_matrix = await self.get_tape_reading_matrix(symbol)

        # بنیاد سبک: P/E از snapshot، فروش ماهانه از جدول کدال
        pe_row = (
            await self.session.execute(
                text(
                    """
                    SELECT eps, pe_ratio FROM brsapi_symbol_snapshots
                    WHERE symbol = :sym AND pe_ratio IS NOT NULL
                    ORDER BY id DESC LIMIT 1
                    """
                ),
                {"sym": symbol},
            )
        ).first()
        pe_ttm = float(pe_row[1]) if pe_row and pe_row[1] else None
        mom, yoy = await self._monthly_sales_momentum(symbol)

        fund_score = estimate_fund_score_safe(pe_ttm, None, mom, yoy)
        tech_score = compute_tech_score(indicators)
        tape_score = tape_matrix.get("tape_score")

        # رژیم بازار از macro
        macro_row = (
            await self.session.execute(
                text(
                    """
                    SELECT market_regime, usd_gap_pct, akhzar_ytm FROM market_macro_indicators
                    ORDER BY indicator_date DESC LIMIT 1
                    """
                )
            )
        ).first()
        regime = macro_row[0] if macro_row and macro_row[0] else "eroding"
        macro_score = 50.0
        if macro_row:
            gap = macro_row[1]
            ytm = macro_row[2]
            if gap is not None:
                macro_score += max(-15.0, min(15.0, (gap) * 0.5))
            if ytm is not None:
                macro_score -= max(-15.0, min(15.0, (ytm - 23.0) * 2.0))

        # سوینگ برای فیبوناچی (از کندل‌ها)
        candles = await self._load_daily_candles(symbol, 120)
        swing_low = min((c["low"] for c in candles[-60:]), default=None)
        swing_high = max((c["high"] for c in candles[-60:]), default=None)
        # حمایت ساختاری: کف ۲۰ روز اخیر
        structural_support = min((c["low"] for c in candles[-20:]), default=None)

        price_last = float(tape.get("last_price") or 0)
        price_close = float(tape.get("close_price") or 0)
        atr_val = indicators.get("atr_14")

        result = compute_composite_signal(
            LayerInputs(
                tape_score=tape_score,
                tech_score=tech_score,
                fund_score=fund_score,
                peer_score=None,
                macro_score=macro_score,
            ),
            price_last=price_last,
            price_close=price_close,
            atr_14=float(atr_val) if atr_val else None,
            structural_support=structural_support,
            swing_low=swing_low,
            swing_high=swing_high,
            market_regime=regime,
        )
        return result.to_dict()

    async def _monthly_sales_momentum(self, symbol: str) -> tuple[float | None, float | None]:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT sales_mom_pct, sales_yoy_pct
                    FROM stock_monthly_sales_production
                    WHERE symbol = :sym AND sales_amount IS NOT NULL
                    ORDER BY jalali_year DESC, jalali_month DESC LIMIT 1
                    """
                ),
                {"sym": symbol},
            )
        ).first()
        return (float(row[0]), float(row[1])) if row and row[0] is not None else (None, None)


def estimate_fund_score_safe(
    pe_ttm: float | None,
    pe_industry: float | None,
    mom: float | None,
    yoy: float | None,
) -> float:
    from services.stock_signal_engine import estimate_fund_score

    return estimate_fund_score(pe_ttm, pe_industry, mom, yoy)


class _Release:
    def __init__(self, mutex: Any, name: str, owned: bool = True) -> None:
        self._m = mutex
        self._n = name
        self._owned = owned

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: Any) -> None:
        if self._owned:
            await self._m.release(self._n)


class _NoRelease:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: Any) -> None:
        return None
