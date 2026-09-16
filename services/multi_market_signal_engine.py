"""Multi-Market Signal Engine — generates buy/sell signals across all markets.

Covers: Stocks, Gold/Coins, Currency, Crypto, Options, Commodities, IME.
Each signal includes 6 mandatory + 5 professional fields per user spec.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from brsapi.models.commodity import (
    CommodityPriceModel,
    CurrencyPriceModel,
    Gold24hModel,
    GoldCoinHistoryModel,
    GoldCoinPriceModel,
    GoldCurrencyProDailyHistoryModel,
)
from brsapi.models.crypto import CryptoDailyHistoryModel, CryptoPriceModel
from brsapi.models.ime import ImeFutureModel
from brsapi.models.tsetmc import HistoricalDailyModel, OptionSnapshotModel, SymbolSnapshotModel
from core.logging import get_logger
from models.codal import CodalAuditSummaryModel

logger = get_logger(__name__)


# ── Signal Data Structure ────────────────────────────────────────────────────


@dataclass
class MarketSignal:
    """Unified signal across all markets — 6 mandatory + 5 professional fields."""

    # ── 6 Mandatory Fields ──
    symbol: str                           # 1. نماد
    direction: str                        # 1. جهت معامله: buy / sell / hold / wait
    timeframe: str                        # 2. بازه زمانی: daily / 2day / 3day / weekly / monthly / quarterly
    entry_zone: str                       # 3. نقطه ورود: "price" or "min-max"
    stop_loss: str                        # 4. حد ضرر
    targets: str                          # 5. اهداف سود: "target1 | target2"
    risk_reward: str                      # 6. نسبت ریسک به ریوارد

    # ── 5 Professional Fields ──
    position_sizing: str = ""             # 7. حجم پیشنهادی
    confirmation_condition: str = ""      # 8. شرط تأیید ورود
    reason: str = ""                      # 9. علت و منطق
    invalidation: str = ""                # 10. شرایط فسخ سیگنال
    trailing_stop: str = ""               # 11. مدیریت پس از ورود

    # ── Metadata ──
    market: str = ""                      # stock / gold / currency / crypto / option / commodity / ime
    name: str = ""                        # نام فارسی
    price: float = 0.0                    # قیمت فعلی
    change_pct: float = 0.0              # درصد تغییر
    score: float = 0.0                   # امتیاز کلی (0-100)
    strength: float = 0.0                # قدرت سیگنال (0-1)
    confidence: float = 0.0              # اطمینان (0-1)
    source: str = ""                     # منبع تولید سیگنال
    created_at: str = ""

    def to_standard(self) -> dict[str, Any]:
        """Return the 7-field standard signal schema required by the platform spec.

        Maps the internal signal to: ``symbol``, ``side``, ``entry_price``,
        ``stop_loss``, ``take_profit``, ``confidence``, ``timestamp``.
        Numeric price fields are parsed from the Persian-formatted strings
        (e.g. ``"۹۷۵,۰۰۰ ریال (کاهش ۵.۰٪)"`` → ``975000.0``); unparseable
        values fall back to ``None``.
        """
        entry_price = self.price if self.price and self.price > 0 else _extract_price(self.entry_zone)
        return {
            "symbol": self.symbol,
            "side": self.direction,
            "entry_price": entry_price,
            "stop_loss": _extract_price(self.stop_loss),
            "take_profit": _extract_price(self.targets),
            "confidence": round(self.confidence, 4),
            "timestamp": self.created_at or datetime.now().isoformat(),
        }


@dataclass
class SignalGenerationReport:
    """گزارش تولید سیگنال برای هر بازار"""
    market: str
    success: bool
    signal_count: int = 0
    error: str | None = None
    error_type: str | None = None
    duration_ms: float = 0.0
    data_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "success": self.success,
            "signal_count": self.signal_count,
            "error": self.error,
            "error_type": self.error_type,
            "duration_ms": round(self.duration_ms, 1),
            "data_available": self.data_available,
        }


# ── Helper: Technical Analysis Utilities ──────────────────────────────────────


def _compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """Compute RSI from list of closing prices."""
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss < 1e-10:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _compute_ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = (v - ema) * multiplier + ema
    return ema


def _compute_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period


def _momentum_score(closes: list[float], period: int) -> float:
    """Return momentum score 0-1 based on price change over period."""
    if len(closes) < period + 1 or closes[-period - 1] <= 0:
        return 0.5
    pct = (closes[-1] - closes[-period - 1]) / closes[-period - 1]
    # Map -20%..+20% to 0..1
    return max(0.0, min(1.0, 0.5 + pct * 2.5))


def _volume_trend(volumes: list[float], short: int = 5, long: int = 20) -> float:
    """Volume ratio short/long, capped at 0-1."""
    if len(volumes) < long:
        return 0.5
    avg_short = sum(volumes[-short:]) / short
    avg_long = sum(volumes[-long:]) / long
    if avg_long < 1e-10:
        return 0.5
    ratio = avg_short / avg_long
    return max(0.0, min(1.0, ratio / 3.0))


def _composite_buy_score(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    tf_days: int,
    volumes: list[float] | None = None,
    market: str = "",
) -> tuple[float, list[str]]:
    """Composite directional score from RSI + momentum + trend + volume.

    Returns ``(buy_score, reasons)`` where ``buy_score > 0.15`` → buy,
    ``< -0.15`` → sell, else hold. Used by both the live signal engine
    and the accuracy benchmark so the logic stays in one place.

    Volume is optional — when ``None`` (gold/currency have no volume
    column) a range-proxy (high-low)/close is used as activity proxy.
    """
    if len(closes) < tf_days + 1:
        return 0.0, []

    momentum = _momentum_score(closes, tf_days)
    rsi = _compute_rsi(closes, 14)
    if rsi is None:
        rsi = 50  # not enough data — not "or 50": RSI=0 (extreme oversold) is valid
    trend = _trend_direction(closes)
    buy_score = 0.0
    reasons: list[str] = []

    if momentum > 0.55:
        buy_score += 0.25
        reasons.append(f"مومنتوم {tf_days}d مثبت")
    elif momentum < 0.45:
        buy_score -= 0.25
        reasons.append(f"مومنتوم {tf_days}d منفی")

    if rsi < 35:
        buy_score += 0.30
        reasons.append(f"RSI اشباع فروش ({rsi:.0f})")
    elif rsi > 70:
        buy_score -= 0.25
        reasons.append(f"RSI اشباع خرید ({rsi:.0f})")
    elif 40 < rsi < 60:
        buy_score += 0.05

    if trend == "up":
        buy_score += 0.15
        reasons.append("روند صعودی (MA5>MA20)")
    elif trend == "down":
        buy_score -= 0.15
        reasons.append("روند نزولی (MA5<MA20)")

    # Volume trend factor — use real volumes if provided, else range proxy
    if volumes is not None:
        vol_series = volumes
    else:
        vol_series = [max(h - low, 0.0) / max(c, 1e-9) for h, low, c in zip(highs, lows, closes, strict=False)]
    vol_trend = _volume_trend(vol_series)
    if vol_trend > 0.6:
        buy_score += 0.10
        reasons.append("افزایش حجم/فعالیت")
    elif vol_trend < 0.35:
        buy_score -= 0.05
        reasons.append("کاهش حجم/فعالیت")

    # Volatility filter: reject trades in extreme-volatility regimes (mean-revert noise)
    if market in ("currency", "gold"):
        atr = _compute_atr(highs or [closes[-1]], lows or [closes[-1]], closes, 14)
        if atr and closes[-1] > 0:
            atr_pct = atr / closes[-1]
            if atr_pct > 0.03:  # > 3% daily ATR → skip (too noisy)
                reasons.append(f"نوسان بالا (ATR {atr_pct:.1%})")
                return 0.0, reasons  # force hold

    return buy_score, reasons


def _trend_direction(closes: list[float]) -> str:
    if len(closes) < 20:
        return "flat"
    sma5 = _compute_sma(closes, 5)
    sma20 = _compute_sma(closes, 20)
    if sma5 is None or sma20 is None:
        return "flat"
    if sma5 > sma20 * 1.005:
        return "up"
    elif sma5 < sma20 * 0.995:
        return "down"
    return "flat"


def _rsi_signal(rsi: float) -> tuple[str, float]:
    """Return (direction, strength) from RSI."""
    if rsi < 30:
        return "buy", min(1.0, (30 - rsi) / 30)
    elif rsi > 70:
        return "sell", min(1.0, (rsi - 70) / 30)
    return "hold", 0.0


def _compute_support_resistance(closes: list[float], period: int = 20) -> tuple[float, float]:
    if len(closes) < period:
        period = len(closes)
    recent = closes[-period:]
    return min(recent), max(recent)


def _fmt_price(price: float) -> str:
    if price is None:
        return "-"
    if price >= 1_000_000:
        return f"{price / 1_000_000:,.1f}M"
    elif price >= 1_000:
        return f"{price:,.0f}"
    else:
        return f"{price:.2f}"


_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _extract_price(text: str | None) -> float | None:
    """Extract the first numeric price from a Persian-formatted string.

    Normalizes Persian digits (۰-۹), strips thousands separators (",")
    and honors the ``M``/``K`` suffix notation emitted by :func:`_fmt_price`
    (e.g. ``"1.1M"`` → ``1100000.0``). Returns ``None`` when no number
    is present (e.g. option strings like "پریمیوم صفر").
    """
    if not text:
        return None
    normalized = text.translate(_PERSIAN_DIGITS).replace(",", "")
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([MKmk])?", normalized)
    if not match:
        return None
    try:
        value = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        if suffix == "m":
            value *= 1_000_000
        elif suffix == "k":
            value *= 1_000
        return value
    except ValueError:
        return None


def _timeframe_label(tf: str) -> str:
    labels = {
        "daily": "روزانه", "2day": "۲ روزه", "3day": "۳ روزه",
        "weekly": "هفتگی", "monthly": "ماهانه", "quarterly": "سه‌ماهه",
    }
    return labels.get(tf, tf)


def _direction_label(d: str) -> str:
    labels = {"buy": "خرید", "sell": "فروش", "hold": "نگهداری", "wait": "انتظار"}
    return labels.get(d, d)


# ── Market Signal Generators ─────────────────────────────────────────────────


class MultiMarketSignalEngine:
    """Generates trading signals across all available markets."""

    TIMEFRAMES = {
        "daily": 1, "2day": 2, "3day": 3,
        "weekly": 5, "monthly": 22, "quarterly": 66,
    }

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def generate_all(
        self,
        market_filter: str = "all",
        timeframe_filter: str = "all",
        signal_filter: str = "all",
        min_strength: float = 0.0,
        limit: int = 100,
    ) -> tuple[list[MarketSignal], list[SignalGenerationReport]]:
        """Generate signals from all markets and return ranked results with reports."""
        import time as _time

        all_signals: list[MarketSignal] = []
        reports: list[SignalGenerationReport] = []

        markets = [
            ("stock", "stock", self._signals_stocks),
            ("gold", "gold", self._signals_gold),
            ("currency", "currency", self._signals_currency),
            ("crypto", "crypto", self._signals_crypto),
            ("option", "option", self._signals_options),
            ("commodity", "commodity", self._signals_commodities),
            ("ime", "ime", self._signals_ime),
        ]

        for filter_key, market_name, method in markets:
            if market_filter in ("all", filter_key):
                start = _time.monotonic()
                try:
                    sigs = await method()
                    reports.append(SignalGenerationReport(
                        market=market_name, success=True,
                        signal_count=len(sigs),
                        duration_ms=(_time.monotonic() - start) * 1000,
                    ))
                    all_signals.extend(sigs)
                except Exception as e:
                    reports.append(SignalGenerationReport(
                        market=market_name, success=False,
                        error=str(e), error_type=type(e).__name__,
                        duration_ms=(_time.monotonic() - start) * 1000,
                    ))

        # Filter by timeframe
        if timeframe_filter != "all":
            all_signals = [s for s in all_signals if s.timeframe == timeframe_filter]

        # Filter by signal direction
        if signal_filter != "all":
            all_signals = [s for s in all_signals if s.direction == signal_filter]

        # Filter by minimum strength
        if min_strength > 0:
            all_signals = [s for s in all_signals if s.strength >= min_strength]

        # Per-market diversity: ensure each market gets representation
        by_market: dict[str, list[MarketSignal]] = {}
        for s in all_signals:
            by_market.setdefault(s.market, []).append(s)

        market_quota = max(5, limit // max(len(by_market), 1))
        diversified: list[MarketSignal] = []
        for _mkt, sigs in by_market.items():
            sigs.sort(key=lambda s: s.score, reverse=True)
            diversified.extend(sigs[:market_quota])

        # Sort by score descending
        diversified.sort(key=lambda s: s.score, reverse=True)

        return diversified[:limit], reports

    # ── Stocks ──────────────────────────────────────────────────────────────

    async def _signals_stocks(self) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        try:
            import core.database as _db

            if _db.async_session_factory is None:
                from core.database import init_database
                await init_database()
            if _db.async_session_factory is None:
                return signals

            async with _db.async_session_factory() as session:
                # Get stocks with volume
                stmt = (
                    select(
                        SymbolSnapshotModel.symbol,
                        SymbolSnapshotModel.name,
                        SymbolSnapshotModel.price_last,
                        SymbolSnapshotModel.price_close,
                        SymbolSnapshotModel.price_yesterday,
                        SymbolSnapshotModel.price_first,
                        SymbolSnapshotModel.price_max,
                        SymbolSnapshotModel.price_min,
                        SymbolSnapshotModel.trade_volume,
                        SymbolSnapshotModel.trade_value,
                        SymbolSnapshotModel.trade_count,
                        SymbolSnapshotModel.price_last_change_pct,
                        SymbolSnapshotModel.buy_real_volume,
                        SymbolSnapshotModel.buy_legal_volume,
                        SymbolSnapshotModel.sell_real_volume,
                        SymbolSnapshotModel.sell_legal_volume,
                    )
                    .where(
                        SymbolSnapshotModel.symbol.is_not(None),
                        SymbolSnapshotModel.symbol != "",
                        SymbolSnapshotModel.trade_volume > 0,
                        SymbolSnapshotModel.price_last > 0,
                    )
                    .order_by(SymbolSnapshotModel.trade_value.desc())
                    .limit(100)
                )
                stocks = (await session.execute(stmt)).fetchall()

                if not stocks:
                    return signals

                # Get historical daily data for these symbols
                syms = [row[0] for row in stocks]
                hist_stmt = (
                    select(
                        HistoricalDailyModel.symbol,
                        HistoricalDailyModel.price_close,
                        HistoricalDailyModel.trade_volume,
                        HistoricalDailyModel.price_first,
                        HistoricalDailyModel.price_max,
                        HistoricalDailyModel.price_min,
                    )
                    .where(HistoricalDailyModel.symbol.in_(syms))
                    .order_by(HistoricalDailyModel.symbol, HistoricalDailyModel.date.desc())
                    .limit(len(syms) * 100)
                )
                history_rows = (await session.execute(hist_stmt)).fetchall()

                # Group history by symbol
                history_by_sym: dict[str, list] = {}
                for row in history_rows:
                    sym = row[0]
                    if sym not in history_by_sym:
                        history_by_sym[sym] = []
                    history_by_sym[sym].append(row)

                # Fetch codal fundamental data for all symbols
                codal_data: dict[str, dict] = {}
                try:
                    codal_stmt = select(
                        CodalAuditSummaryModel.symbol,
                        CodalAuditSummaryModel.health_score,
                        CodalAuditSummaryModel.roe,
                        CodalAuditSummaryModel.gross_margin,
                        CodalAuditSummaryModel.net_margin,
                        CodalAuditSummaryModel.revenue_growth,
                        CodalAuditSummaryModel.debt_to_equity,
                        CodalAuditSummaryModel.current_ratio,
                        CodalAuditSummaryModel.forensic_risk,
                    ).where(CodalAuditSummaryModel.symbol.in_(syms))
                    for row in (await session.execute(codal_stmt)).fetchall():
                        codal_data[row[0]] = {
                            "health": row[1] or 0, "roe": row[2],
                            "gross_margin": row[3], "net_margin": row[4],
                            "revenue_growth": row[5], "debt_to_equity": row[6],
                            "current_ratio": row[7], "forensic_risk": row[8],
                        }
                except Exception as e:
                    logger.debug("Codal fundamentals unavailable, continuing without them: %s", e)

                for stock in stocks:
                    sym = stock[0]
                    name = stock[1]
                    price = stock[2] or stock[3] or 0
                    if price <= 0:
                        continue
                    change_pct = stock[11] or 0
                    volume = stock[8] or 0
                    value = stock[9] or 0

                    hist = history_by_sym.get(sym, [])
                    closes = [row[1] for row in hist if row[1] and row[1] > 0]
                    volumes = [row[2] or 0 for row in hist]
                    highs = [row[4] or row[1] or 0 for row in hist if row[1]]
                    lows = [row[5] or row[1] or 0 for row in hist if row[1]]

                    if len(closes) < 5:
                        # Minimal signal based on current data only
                        signals.append(self._minimal_stock_signal(sym, name, price, change_pct, volume, value))
                        continue

                    closes = list(reversed(closes))  # oldest first
                    volumes = list(reversed(volumes))
                    highs = list(reversed(highs))
                    lows = list(reversed(lows))

                    # Compute multi-timeframe signals
                    for tf_name, tf_days in self.TIMEFRAMES.items():
                        sig = self._compute_stock_signal(
                            sym, name, price, change_pct, volume, value,
                            closes, volumes, highs, lows, tf_name, tf_days,
                            codal=codal_data.get(sym),
                        )
                        if sig:
                            signals.append(sig)

        except Exception as e:
            logger.warning("Stock signal generation failed: %s", e, exc_info=True)

        return signals

    def _minimal_stock_signal(
        self, sym: str, name: str, price: float, change_pct: float,
        volume: int, value: float,
    ) -> MarketSignal:
        direction = "buy" if change_pct > 2 else "sell" if change_pct < -2 else "hold"
        strength = min(1.0, abs(change_pct) / 5)
        return MarketSignal(
            symbol=sym, name=name, market="stock",
            direction=direction, timeframe="daily",
            entry_zone=f"قیمت فعلی: {_fmt_price(price)}",
            stop_loss=f"{_fmt_price(price * 0.95)} (۵٪ کاهش)",
            targets=f"هدف اول: {_fmt_price(price * 1.05)} | هدف دوم: {_fmt_price(price * 1.10)}",
            risk_reward="۱ به ۱",
            reason=f"تغییر {change_pct:+.1f}٪ | حجم: {value / 1e9:.1f} میلیارد ریال",
            price=price, change_pct=change_pct,
            score=max(0, min(100, 50 + change_pct * 5)), strength=strength, confidence=0.3,
            source="snapshot_analysis", created_at=datetime.now().isoformat(),
        )

    def _compute_stock_signal(
        self, sym: str, name: str, price: float, change_pct: float,
        volume: int, value: float,
        closes: list[float], volumes: list[float],
        highs: list[float], lows: list[float],
        tf_name: str, tf_days: int,
        codal: dict | None = None,
    ) -> MarketSignal | None:
        if len(closes) < max(tf_days + 1, 14):
            return None

        # Multi-timeframe momentum
        momentum = _momentum_score(closes, tf_days)

        # RSI
        rsi = _compute_rsi(closes, 14)
        if rsi is None:
            rsi = 50

        # Trend
        trend = _trend_direction(closes)

        # Volume trend
        vol_trend = _volume_trend(volumes)

        # ATR for stop-loss
        atr = _compute_atr(highs, lows, closes, 14)
        if atr is None:
            atr = price * 0.03

        # Support / Resistance
        support, resistance = _compute_support_resistance(closes)


        # ── Direction Logic ──
        buy_score = 0.0
        reasons = []

        if momentum > 0.55:
            buy_score += 0.25
            reasons.append(f"مومنتوم {tf_name} مثبت ({momentum:.0%})")
        elif momentum < 0.45:
            buy_score -= 0.25
            reasons.append(f"مومنتوم {tf_name} منفی ({momentum:.0%})")

        if rsi < 35:
            buy_score += 0.30
            reasons.append(f"RSI اشباع فروش ({rsi:.0f})")
        elif rsi > 70:
            buy_score -= 0.25
            reasons.append(f"RSI اشباع خرید ({rsi:.0f})")
        elif 40 < rsi < 60:
            buy_score += 0.05

        if trend == "up":
            buy_score += 0.15
            reasons.append("روند صعودی (MA5 > MA20)")
        elif trend == "down":
            buy_score -= 0.15
            reasons.append("روند نزولی (MA5 < MA20)")

        if vol_trend > 0.6:
            buy_score += 0.10
            reasons.append("افزایش حجم معاملات")

        # ── Fundamental Analysis Factor (from Codal) ──
        if codal:
            health = codal.get("health", 0) or 0
            roe = codal.get("roe")
            net_margin = codal.get("net_margin")
            forensic = codal.get("forensic_risk", "")

            # Health score bonus/penalty
            if health >= 0.70:
                buy_score += 0.15
                reasons.append(f"سلامت مالی بالا ({health:.0%})")
            elif health < 0.45:
                buy_score -= 0.10
                reasons.append(f"سلامت مالی پایین ({health:.0%})")

            # ROE bonus
            if roe and roe > 0.15:
                buy_score += 0.05
                reasons.append(f"ROE بالا ({roe:.0%})")

            # Profitable company
            if net_margin and net_margin > 0.10:
                buy_score += 0.05
                reasons.append(f"حاشیه سود مثبت ({net_margin:.0%})")

            # Forensic risk penalty
            if forensic and str(forensic) not in ("0", "0.0", ""):
                with contextlib.suppress(ValueError, TypeError):
                    risk_val = float(forensic)
                    if risk_val > 0.15:
                        buy_score -= 0.10
                        reasons.append(f"ریسک تقلب بالا ({risk_val:.0%})")

        # Score to direction
        if buy_score > 0.15:
            direction = "buy"
        elif buy_score < -0.15:
            direction = "sell"
        else:
            direction = "hold"

        strength = min(1.0, max(0.0, abs(buy_score)))
        score = 50 + buy_score * 50

        # ── Entry / Stop / Targets ──
        if direction == "buy":
            entry_low = max(price * 0.98, support)
            entry_high = price
            entry_zone = f"محدوده ورود: {_fmt_price(entry_low)} تا {_fmt_price(entry_high)} ریال"
            sl = min(support * 0.98, price - atr * 1.5)
            stop_loss = f"{_fmt_price(sl)} ریال (کاهش {((price - sl) / price * 100):.1f}٪)"
            t1 = price + atr * 3
            t2 = price + atr * 5
            targets = f"هدف اول: {_fmt_price(t1)} | هدف دوم: {_fmt_price(t2)}"
            rr = (t1 - price) / max(price - sl, 1)
            risk_reward = f"۱ به {rr:.1f}"
            position = f"حداکثر ۳٪ سرمایه ({_fmt_price(price * 0.03)} ریال به ازای هر ۱۰۰ میلیون)"
            confirmation = f"تثبیت قیمت بالای {_fmt_price(support)} با حجم بیش از {volume * 0.1:,.0f}"
            trailing = f"پس از رسیدن به {_fmt_price(t1)}، حد ضرر را به {_fmt_price(price)} منتقل کنید"
            invalidation = f"شکست حمایت {_fmt_price(support)} با حجم سنگین"
        elif direction == "sell":
            entry_zone = f"فروش در محدوده: {_fmt_price(price)} تا {_fmt_price(price * 1.02)} ریال"
            sl = resistance * 1.02
            stop_loss = f"{_fmt_price(sl)} ریال (افزایش {((sl - price) / price * 100):.1f}٪)"
            t1 = price - atr * 3
            t2 = price - atr * 5
            targets = f"هدف اول: {_fmt_price(t1)} | هدف دوم: {_fmt_price(t2)}"
            rr = (price - t1) / max(sl - price, 1)
            risk_reward = f"۱ به {rr:.1f}"
            position = "فروش (در صورت داشتن موقعیت)"
            confirmation = f"عبور قیمت به زیر {_fmt_price(support)}"
            trailing = f"پس از رسیدن به {_fmt_price(t1)}، حد ضرر را به {_fmt_price(price)} منتقل کنید"
            invalidation = f"عبور قیمت به بالای {_fmt_price(resistance)}"
        else:
            entry_zone = f"انتظار — ورود در محدوده {_fmt_price(support)} تا {_fmt_price(support * 1.02)}"
            stop_loss = f"{_fmt_price(support * 0.97)} ریال"
            targets = f"هدف اول: {_fmt_price(resistance * 0.95)} | هدف دوم: {_fmt_price(resistance)}"
            risk_reward = f"۱ به {((resistance - support) / max(price - support * 0.97, 1)):.1f}"
            position = "صبر کنید — سیگنال فعال نیست"
            confirmation = f"ورود فقط در صورت شکست {_fmt_price(resistance)} با حجم بالا"
            trailing = ""
            invalidation = "سیگنال فقط مشاهده‌ای است"

        confidence = 0.3 + strength * 0.4 + (0.1 if len(reasons) > 2 else 0)

        now = datetime.now()
        return MarketSignal(
            symbol=sym, name=name, market="stock",
            direction=direction, timeframe=tf_name,
            entry_zone=entry_zone,
            stop_loss=stop_loss,
            targets=targets,
            risk_reward=risk_reward,
            position_sizing=position,
            confirmation_condition=confirmation,
            reason=" | ".join(reasons[:3]) if reasons else "تحلیل تکنیکال",
            invalidation=invalidation,
            trailing_stop=trailing,
            price=price, change_pct=change_pct,
            score=max(0, min(100, score)),
            strength=strength, confidence=min(1.0, confidence),
            source="smart_money_technical",
            created_at=now.isoformat(),
        )

    # ── Gold & Coins ────────────────────────────────────────────────────────

    async def _signals_gold(self) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        try:
            import core.database as _db

            if _db.async_session_factory is None:
                from core.database import init_database
                await init_database()
            if _db.async_session_factory is None:
                return signals

            async with _db.async_session_factory() as session:
                # Current gold coin prices
                coins_stmt = (
                    select(
                        GoldCoinPriceModel.symbol,
                        GoldCoinPriceModel.name,
                        GoldCoinPriceModel.price,
                        GoldCoinPriceModel.change_value,
                        GoldCoinPriceModel.change_percent,
                    )
                    .where(GoldCoinPriceModel.price > 0)
                    .order_by(GoldCoinPriceModel.change_percent.desc())
                )
                coins = (await session.execute(coins_stmt)).fetchall()

                # Gold 24h - fallback to gold_coin_prices if gold_24h is empty
                gold24_stmt = (
                    select(
                        Gold24hModel.symbol,
                        Gold24hModel.name,
                        Gold24hModel.price_now,
                        Gold24hModel.change_percent,
                        Gold24hModel.high_24h,
                        Gold24hModel.low_24h,
                    )
                    .where(Gold24hModel.price_now > 0)
                )
                gold24 = (await session.execute(gold24_stmt)).fetchall()
                if not gold24:
                    # Fallback: generate 24h-style signals from gold coin prices
                    gold24 = [(row[0], row[1], row[2], row[4], None, None) for row in coins if row[2] and row[2] > 0]

                # Gold history (Iranian coins)
                hist_stmt = (
                    select(
                        GoldCoinHistoryModel.symbol,
                        GoldCoinHistoryModel.price_close,
                        GoldCoinHistoryModel.price_high,
                        GoldCoinHistoryModel.price_low,
                    )
                    .where(GoldCoinHistoryModel.price_close > 0)
                    .order_by(GoldCoinHistoryModel.date.desc())
                    .limit(3000)
                )
                history = (await session.execute(hist_stmt)).fetchall()

                # XAUUSD lives in the currency-pro table (gold_coin_history has only IR_*)
                xau_stmt = (
                    select(
                        GoldCurrencyProDailyHistoryModel.symbol,
                        GoldCurrencyProDailyHistoryModel.price_close,
                        GoldCurrencyProDailyHistoryModel.price_high,
                        GoldCurrencyProDailyHistoryModel.price_low,
                    )
                    .where(
                        GoldCurrencyProDailyHistoryModel.price_close > 0,
                        GoldCurrencyProDailyHistoryModel.symbol == "XAUUSD",
                    )
                    .order_by(GoldCurrencyProDailyHistoryModel.date.desc())
                    .limit(3000)
                )
                xau_history = (await session.execute(xau_stmt)).fetchall()

                # Group history by symbol (combined)
                hist_by_sym: dict[str, list] = {}
                for row in list(history) + list(xau_history):
                    sym = row[0]
                    hist_by_sym.setdefault(sym, []).append(row)

                # Generate signals for gold coins
                covered_syms: set[str] = set()
                for coin in coins:
                    sym, name, price, chg_val, chg_pct = coin
                    if not price or price <= 0:
                        continue

                    hist = hist_by_sym.get(sym, [])
                    closes = [row[1] for row in hist if row[1] and row[1] > 0]
                    highs = [row[2] for row in hist if row[2] and row[2] > 0]
                    lows = [row[3] for row in hist if row[3] and row[3] > 0]

                    closes = list(reversed(closes))
                    highs = list(reversed(highs))
                    lows = list(reversed(lows))

                    for tf_name, tf_days in self.TIMEFRAMES.items():
                        sig = self._compute_commodity_signal(
                            sym, name or sym, price, chg_pct or 0,
                            closes, highs, lows, tf_name, tf_days, "gold",
                        )
                        if sig:
                            signals.append(sig)
                            covered_syms.add(sym)

                # Gold 24h signals — composite from OHLC history when available,
                # fallback to simple 24h change threshold otherwise
                for g in gold24:
                    sym, name, price, chg_pct, high_24h, low_24h = g
                    if not price or price <= 0:
                        continue

                    # Symbols already covered by the coin loop (composite across
                    # all timeframes) must NOT also emit the low-quality chg_pct
                    # fallback — that would defeat the composite upgrade.
                    if sym in covered_syms:
                        continue

                    hist = hist_by_sym.get(sym, [])
                    closes = [row[1] for row in hist if row[1] and row[1] > 0]
                    highs = [row[2] for row in hist if row[2] and row[2] > 0]
                    lows = [row[3] for row in hist if row[3] and row[3] > 0]

                    if len(closes) >= 2:
                        sig = self._compute_commodity_signal(
                            sym, name or sym, price, chg_pct or 0,
                            list(reversed(closes)), list(reversed(highs)), list(reversed(lows)),
                            "daily", 1, "gold",
                        )
                        if sig:
                            signals.append(sig)
                        continue

                    atr = (high_24h - low_24h) if high_24h and low_24h else price * 0.02
                    direction = "buy" if (chg_pct or 0) > 0.5 else "sell" if (chg_pct or 0) < -0.5 else "hold"
                    strength = min(1.0, abs(chg_pct or 0) / 3)

                    if direction == "buy":
                        sl = price - atr * 1.5
                        t1 = price + atr * 2
                        t2 = price + atr * 3.5
                    elif direction == "sell":
                        sl = price + atr * 1.5
                        t1 = price - atr * 2
                        t2 = price - atr * 3.5
                    else:
                        sl = price - atr * 1.5
                        t1 = price + atr * 1.5
                        t2 = price + atr * 3

                    rr = abs(t1 - price) / max(abs(price - sl), 1)

                    # Range text only when real 24h high/low data exists
                    range_txt = (
                        f" | محدوده: {_fmt_price(low_24h)} - {_fmt_price(high_24h)}"
                        if high_24h and low_24h else ""
                    )
                    chg_pct = chg_pct or 0.0

                    signals.append(MarketSignal(
                        symbol=sym, name=name or sym, market="gold",
                        direction=direction, timeframe="daily",
                        entry_zone=f"قیمت فعلی: {_fmt_price(price)} ریال",
                        stop_loss=f"{_fmt_price(sl)} ریال (کاهش {abs(price - sl) / price * 100:.1f}٪)",
                        targets=f"هدف اول: {_fmt_price(t1)} | هدف دوم: {_fmt_price(t2)}",
                        risk_reward=f"۱ به {rr:.1f}",
                        position_sizing="حداکثر ۵٪ سرمایه",
                        reason=f"تغییر ۲۴ ساعته: {chg_pct:+.1f}٪{range_txt}",
                        price=price, change_pct=chg_pct or 0,
                        score=max(0, min(100, 50 + (chg_pct or 0) * 5)),
                        strength=strength, confidence=0.4,
                        source="gold_24h_analysis",
                        created_at=datetime.now().isoformat(),
                    ))

        except Exception as e:
            logger.warning("Gold signal generation failed: %s", e, exc_info=True)

        return signals

    # ── Currency ────────────────────────────────────────────────────────────

    async def _signals_currency(self) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        try:
            import core.database as _db

            if _db.async_session_factory is None:
                from core.database import init_database
                await init_database()
            if _db.async_session_factory is None:
                return signals

            async with _db.async_session_factory() as session:
                cur_stmt = (
                    select(
                        CurrencyPriceModel.symbol,
                        CurrencyPriceModel.name,
                        CurrencyPriceModel.price,
                        CurrencyPriceModel.change_value,
                        CurrencyPriceModel.change_percent,
                    )
                    .where(CurrencyPriceModel.price > 0)
                )
                currencies = (await session.execute(cur_stmt)).fetchall()

                # OHLC history → composite RSI + volume + momentum scoring
                # (restricted to current currency symbols to avoid scanning the
                # whole history table incl. unused NIMA_* / XAUUSD rows)
                syms_in = [
                    c[0] for c in currencies
                    if re.fullmatch(r"[A-Za-z0-9_]+", c[0] or "")
                ]
                hist_by_sym: dict[str, dict[str, list[float]]] = {}
                last_dates: dict[str, str] = {}
                hist_stmt = (
                    select(
                        GoldCurrencyProDailyHistoryModel.symbol,
                        GoldCurrencyProDailyHistoryModel.date,
                        GoldCurrencyProDailyHistoryModel.price_high,
                        GoldCurrencyProDailyHistoryModel.price_low,
                        GoldCurrencyProDailyHistoryModel.price_close,
                    )
                    .where(
                        GoldCurrencyProDailyHistoryModel.price_close > 0,
                        GoldCurrencyProDailyHistoryModel.symbol.in_(syms_in or [""]),
                    )
                    .order_by(GoldCurrencyProDailyHistoryModel.date.asc())
                )
                r_hist = await session.execute(hist_stmt)
                for row in r_hist.fetchall():
                    sym, d, high, low, close = row
                    if last_dates.get(sym) == d:
                        continue  # dedupe same-date rows
                    last_dates[sym] = d
                    entry = hist_by_sym.setdefault(sym, {"closes": [], "highs": [], "lows": []})
                    entry["closes"].append(close)
                    entry["highs"].append(high or close)
                    entry["lows"].append(low or close)

                for cur in currencies:
                    sym, name, price, chg_val, chg_pct = cur
                    if not price or price <= 0:
                        continue

                    hist = hist_by_sym.get(sym)
                    if hist and len(hist["closes"]) >= 2:
                        # Composite RSI + volume + momentum across all timeframes
                        for tf_name, tf_days in self.TIMEFRAMES.items():
                            sig = self._compute_commodity_signal(
                                sym, name or sym, price, chg_pct or 0,
                                hist["closes"], hist["highs"], hist["lows"],
                                tf_name, tf_days, "currency",
                            )
                            if sig:
                                signals.append(sig)
                        continue

                    # Fallback: no OHLC history → simple 24h change threshold
                    chg_pct = chg_pct or 0.0
                    atr = price * 0.015
                    direction = "buy" if chg_pct > 0.3 else "sell" if chg_pct < -0.3 else "hold"
                    strength = min(1.0, abs(chg_pct) / 2)

                    if direction == "buy":
                        sl = price - atr * 1.5
                        t1 = price + atr * 2
                        t2 = price + atr * 3
                    elif direction == "sell":
                        sl = price + atr * 1.5
                        t1 = price - atr * 2
                        t2 = price - atr * 3
                    else:
                        sl = price - atr * 1.5
                        t1 = price + atr * 1.5
                        t2 = price + atr * 2.5

                    rr = abs(t1 - price) / max(abs(price - sl), 1)

                    signals.append(MarketSignal(
                        symbol=sym, name=name or sym, market="currency",
                        direction=direction, timeframe="daily",
                        entry_zone=f"قیمت فعلی: {_fmt_price(price)} ریال",
                        stop_loss=f"{_fmt_price(sl)} ریال (کاهش {abs(price - sl) / price * 100:.1f}٪)",
                        targets=f"هدف اول: {_fmt_price(t1)} | هدف دوم: {_fmt_price(t2)}",
                        risk_reward=f"۱ به {rr:.1f}",
                        position_sizing="حداکثر ۱۰٪ سرمایه",
                        reason=f"تغییر ۲۴ ساعته: {chg_pct:+.1f}٪",
                        price=price, change_pct=chg_pct or 0,
                        score=max(0, min(100, 50 + (chg_pct or 0) * 5)),
                        strength=strength, confidence=0.35,
                        source="currency_24h_analysis",
                        created_at=datetime.now().isoformat(),
                    ))

        except Exception as e:
            logger.warning("Currency signal generation failed: %s", e, exc_info=True)

        return signals

    # ── Crypto ──────────────────────────────────────────────────────────────

    async def _signals_crypto(self) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        try:
            import core.database as _db

            if _db.async_session_factory is None:
                from core.database import init_database
                await init_database()
            if _db.async_session_factory is None:
                return signals

            async with _db.async_session_factory() as session:
                crypto_stmt = (
                    select(
                        CryptoPriceModel.symbol,
                        CryptoPriceModel.name,
                        CryptoPriceModel.price_usd,
                        CryptoPriceModel.price_toman,
                        CryptoPriceModel.change_percent,
                        CryptoPriceModel.market_cap,
                        CryptoPriceModel.volume_24h,
                        CryptoPriceModel.rank,
                    )
                    .where(
                        CryptoPriceModel.price_usd > 0,
                        CryptoPriceModel.rank <= 50,
                    )
                    .order_by(CryptoPriceModel.market_cap.desc())
                    .limit(30)
                )
                cryptos = (await session.execute(crypto_stmt)).fetchall()

                for crypto in cryptos:
                    sym, name, price_usd, price_toman, chg_pct, mcap, vol24h, rank = crypto
                    if not price_usd or price_usd <= 0:
                        continue

                    price = price_usd
                    atr_est = price * abs(chg_pct or 0) / 100 * 2 if chg_pct else price * 0.03

                    # Multi-timeframe via daily history
                    crypto_hist_stmt = (
                        select(CryptoDailyHistoryModel.price_close)
                        .where(
                            CryptoDailyHistoryModel.symbol == sym,
                            CryptoDailyHistoryModel.price_close > 0,
                        )
                        .order_by(CryptoDailyHistoryModel.date.desc())
                        .limit(100)
                    )
                    hist = (await session.execute(crypto_hist_stmt)).fetchall()
                    closes = list(reversed([row[0] for row in hist if row[0]]))

                    # If no history, generate basic signal from current data only
                    if not closes:
                        chg_pct = chg_pct or 0.0
                        atr_est = price * abs(chg_pct) / 100 * 2 if chg_pct else price * 0.03
                        direction = "buy" if chg_pct > 1 else "sell" if chg_pct < -1 else "hold"
                        strength = min(1.0, abs(chg_pct) / 5)
                        sl = price - atr_est * 1.5 if direction == "buy" else price + atr_est * 1.5
                        t1 = price + atr_est * 2 if direction == "buy" else price - atr_est * 2
                        t2 = price + atr_est * 3.5 if direction == "buy" else price - atr_est * 3.5
                        rr = abs(t1 - price) / max(abs(price - sl), 1)
                        signals.append(MarketSignal(
                            symbol=sym, name=name or sym, market="crypto",
                            direction=direction, timeframe="daily",
                            entry_zone=f"${price:,.2f} (تومان: {_fmt_price(price_toman or 0)})",
                            stop_loss=f"${sl:,.2f} (کاهش {abs(price - sl) / price * 100:.1f}%)",
                            targets=f"هدف اول: ${t1:,.2f} | هدف دوم: ${t2:,.2f}",
                            risk_reward=f"1 به {rr:.1f}",
                            position_sizing="حداکثر 2% سرمایه",
                            reason=f"تغییر 24 ساعته: {chg_pct:+.1f}% | رتبه #{rank}",
                            price=price, change_pct=chg_pct,
                            score=max(0, min(100, 50 + chg_pct * 5)),
                            strength=strength, confidence=0.3,
                            source="crypto_price_analysis",
                            created_at=datetime.now().isoformat(),
                        ))
                        continue

                    for tf_name, tf_days in self.TIMEFRAMES.items():
                        if len(closes) < tf_days + 1:
                            continue

                        momentum = _momentum_score(closes, tf_days)
                        rsi = _compute_rsi(closes, 14)
                        if rsi is None:
                            rsi = 50  # not "or 50": RSI=0 (extreme oversold) is valid
                        trend = _trend_direction(closes)

                        buy_score = 0.0
                        reasons = []

                        if momentum > 0.55:
                            buy_score += 0.3
                            reasons.append(f"مومنتوم {tf_name} مثبت")
                        elif momentum < 0.45:
                            buy_score -= 0.3
                            reasons.append(f"مومنتوم {tf_name} منفی")

                        if rsi < 30:
                            buy_score += 0.3
                            reasons.append(f"RSI اشباع فروش ({rsi:.0f})")
                        elif rsi > 70:
                            buy_score -= 0.3
                            reasons.append(f"RSI اشباع خرید ({rsi:.0f})")

                        if trend == "up":
                            buy_score += 0.15
                            reasons.append("روند صعودی")
                        elif trend == "down":
                            buy_score -= 0.15
                            reasons.append("روند نزولی")

                        if vol24h and mcap and mcap > 0:
                            vol_ratio = vol24h / mcap
                            if vol_ratio > 0.05:
                                buy_score += 0.1
                                reasons.append("حجم بالا نسبت به ارزش بازار")

                        direction = "buy" if buy_score > 0.15 else "sell" if buy_score < -0.15 else "hold"
                        strength = min(1.0, max(0.0, abs(buy_score)))
                        score = 50 + buy_score * 50

                        sl = price - atr_est * 1.5
                        t1 = price + atr_est * 2
                        t2 = price + atr_est * 3.5
                        rr = abs(t1 - price) / max(abs(price - sl), 1)

                        signals.append(MarketSignal(
                            symbol=sym, name=name or sym, market="crypto",
                            direction=direction, timeframe=tf_name,
                            entry_zone=f"${price:,.2f} (تومان: {_fmt_price(price_toman or 0)})",
                            stop_loss=f"${sl:,.2f} (کاهش {abs(price - sl) / price * 100:.1f}٪)",
                            targets=f"هدف اول: ${t1:,.2f} | هدف دوم: ${t2:,.2f}",
                            risk_reward=f"۱ به {rr:.1f}",
                            position_sizing="حداکثر ۲٪ سرمایه",
                            reason=" | ".join(reasons[:2]) if reasons else f"رتبه #{rank}",
                            price=price, change_pct=chg_pct or 0,
                            score=max(0, min(100, score)),
                            strength=strength, confidence=0.3 + strength * 0.3,
                            source="crypto_analysis",
                            created_at=datetime.now().isoformat(),
                        ))

        except Exception as e:
            logger.warning("Crypto signal generation failed: %s", e, exc_info=True)

        return signals

    # ── Options ─────────────────────────────────────────────────────────────

    async def _signals_options(self) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        try:
            import core.database as _db

            if _db.async_session_factory is None:
                from core.database import init_database
                await init_database()
            if _db.async_session_factory is None:
                return signals

            async with _db.async_session_factory() as session:
                # Get options with volume
                opt_stmt = (
                    select(
                        OptionSnapshotModel.underlying_symbol,
                        OptionSnapshotModel.option_type,
                        OptionSnapshotModel.strike_price,
                        OptionSnapshotModel.price_last,
                        OptionSnapshotModel.trade_volume,
                        OptionSnapshotModel.open_interest,
                        OptionSnapshotModel.days_remaining,
                        OptionSnapshotModel.underlying_price_last,
                        OptionSnapshotModel.price_yesterday,
                        OptionSnapshotModel.price_max,
                        OptionSnapshotModel.price_min,
                    )
                    .where(
                        OptionSnapshotModel.trade_volume > 0,
                        OptionSnapshotModel.price_last > 0,
                        OptionSnapshotModel.underlying_price_last > 0,
                    )
                    .order_by(OptionSnapshotModel.trade_volume.desc())
                    .limit(200)
                )
                options = (await session.execute(opt_stmt)).fetchall()

                # Group by underlying
                by_underlying: dict[str, dict[str, list]] = {}
                for opt in options:
                    und = opt[0]
                    if und not in by_underlying:
                        by_underlying[und] = {"call": [], "put": []}
                    opt_type = opt[1]
                    if opt_type in ("call", "put"):
                        by_underlying[und][opt_type].append(opt)

                for und, chains in by_underlying.items():
                    calls = chains["call"]
                    puts = chains["put"]

                    if not calls and not puts:
                        continue

                    # Underlying price
                    und_price = 0
                    for c in calls + puts:
                        if c[7] and c[7] > 0:
                            und_price = c[7]
                            break
                    if und_price <= 0:
                        continue

                    # Put-Call Ratio by volume
                    call_vol = sum(c[4] or 0 for c in calls)
                    put_vol = sum(p[4] or 0 for p in puts)
                    pcr = put_vol / max(call_vol, 1)

                    # Max pain (strike with highest total OI)
                    oi_by_strike: dict[float, int] = {}
                    for c in calls + puts:
                        s = c[2] or 0
                        oi_by_strike[s] = oi_by_strike.get(s, 0) + (c[5] or 0)
                    max_pain = max(oi_by_strike, key=oi_by_strike.get) if oi_by_strike else und_price

                    # Signal logic
                    reasons = []
                    buy_score = 0.0

                    if pcr > 1.2:
                        buy_score += 0.3
                        reasons.append(f"Put/Call Ratio بالا ({pcr:.2f}) — سنتیمنت نزولی (سیگنال خرید معکوس)")
                    elif pcr < 0.7:
                        buy_score -= 0.2
                        reasons.append(f"Put/Call Ratio پایین ({pcr:.2f}) — سنتیمنت صعودی (احتیاط)")
                    else:
                        reasons.append(f"Put/Call Ratio خنثی ({pcr:.2f})")

                    if und_price < max_pain * 0.97:
                        buy_score += 0.2
                        reasons.append(f"قیمت زیر Max Pain ({_fmt_price(max_pain)}) — احتمال بازگشت")
                    elif und_price > max_pain * 1.03:
                        buy_score -= 0.15
                        reasons.append(f"قیمت بالای Max Pain ({_fmt_price(max_pain)})")

                    # Short-dated options volume spike
                    short_term = [o for o in calls + puts if (o[6] or 999) <= 7 and (o[4] or 0) > 100]
                    if short_term:
                        reasons.append(f"{len(short_term)} قرارداد کوتاه‌مدت با حجم بالا")

                    direction = "buy" if buy_score > 0.15 else "sell" if buy_score < -0.15 else "hold"
                    strength = min(1.0, max(0.0, abs(buy_score)))

                    # Best call for buy signal
                    best_call = max(calls, key=lambda x: x[4] or 0) if calls else None
                    best_put = max(puts, key=lambda x: x[4] or 0) if puts else None

                    if direction == "buy" and best_call:
                        entry = f"اختیار خرید {und} اعمال {_fmt_price(best_call[2])} — پریمیوم: {_fmt_price(best_call[3])}"
                        sl = "پریمیوم صفر (از دست دادن کل پریمیوم)"
                        t1 = f"پریمیوم +۵۰٪: {_fmt_price(best_call[3] * 1.5)}"
                        t2 = f"پریمیوم +۱۰۰٪: {_fmt_price(best_call[3] * 2)}"
                        rr = "۱ به ۱.۵"
                    elif direction == "sell" and best_put:
                        entry = f"اختیار فروش {und} اعمال {_fmt_price(best_put[2])} — پریمیوم: {_fmt_price(best_put[3])}"
                        sl = "محدود — حداکثر پریمیوم دریافتی"
                        t1 = f"پریمیوم -۵۰٪: {_fmt_price(best_put[3] * 0.5)}"
                        t2 = "پریمیوم صفر (سود کامل)"
                        rr = "۱ به ۲"
                    else:
                        entry = "انتظار — ورود در صورت تغییر سنتیمنت"
                        sl = "نامحدود"
                        t1 = "-"
                        t2 = "-"
                        rr = "نامشخص"

                    signals.append(MarketSignal(
                        symbol=und, name=f"آپشن {und}", market="option",
                        direction=direction, timeframe="daily",
                        entry_zone=entry,
                        stop_loss=sl,
                        targets=f"هدف اول: {t1} | هدف دوم: {t2}",
                        risk_reward=rr,
                        position_sizing="حداکثر ۱٪ سرمایه (پریمیوم)",
                        reason=" | ".join(reasons[:3]),
                        price=und_price,
                        score=50 + buy_score * 40,
                        strength=strength, confidence=0.35,
                        source="options_pcr_analysis",
                        created_at=datetime.now().isoformat(),
                    ))

        except Exception as e:
            logger.warning("Options signal generation failed: %s", e, exc_info=True)

        return signals

    # ── Commodities ─────────────────────────────────────────────────────────

    async def _signals_commodities(self) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        try:
            import core.database as _db

            if _db.async_session_factory is None:
                from core.database import init_database
                await init_database()
            if _db.async_session_factory is None:
                return signals

            async with _db.async_session_factory() as session:
                comm_stmt = (
                    select(
                        CommodityPriceModel.symbol,
                        CommodityPriceModel.name,
                        CommodityPriceModel.price,
                        CommodityPriceModel.change_value,
                        CommodityPriceModel.change_percent,
                        CommodityPriceModel.unit,
                        CommodityPriceModel.category,
                    )
                    .where(CommodityPriceModel.price > 0)
                    .order_by(func.abs(CommodityPriceModel.change_percent).desc())
                )
                commodities = (await session.execute(comm_stmt)).fetchall()

                for com in commodities:
                    sym, name, price, chg_val, chg_pct, unit, category = com
                    if not price or price <= 0:
                        continue

                    chg_pct = chg_pct or 0.0
                    atr_est = price * abs(chg_pct) / 100 * 2 if chg_pct else price * 0.02
                    direction = "buy" if chg_pct > 1 else "sell" if chg_pct < -1 else "hold"
                    strength = min(1.0, abs(chg_pct) / 5)

                    sl = price - atr_est * 1.5 if direction == "buy" else price + atr_est * 1.5
                    t1 = price + atr_est * 2 if direction == "buy" else price - atr_est * 2
                    t2 = price + atr_est * 3.5 if direction == "buy" else price - atr_est * 3.5
                    rr = abs(t1 - price) / max(abs(price - sl), 1)

                    cat_label = {"precious_metal": "فلزات گرانبها", "base_metal": "فلزات پایه", "energy": "انرژی"}.get(category, category)

                    signals.append(MarketSignal(
                        symbol=sym, name=name or sym, market="commodity",
                        direction=direction, timeframe="daily",
                        entry_zone=f"${price:,.2f} {unit}",
                        stop_loss=f"${sl:,.2f} (کاهش {abs(price - sl) / price * 100:.1f}٪)",
                        targets=f"هدف اول: ${t1:,.2f} | هدف دوم: ${t2:,.2f}",
                        risk_reward=f"۱ به {rr:.1f}",
                        position_sizing="حداکثر ۳٪ سرمایه",
                        reason=f"تغییر: {chg_pct:+.1f}٪ | دسته: {cat_label}",
                        price=price, change_pct=chg_pct or 0,
                        score=max(0, min(100, 50 + (chg_pct or 0) * 5)),
                        strength=strength, confidence=0.3,
                        source="commodity_analysis",
                        created_at=datetime.now().isoformat(),
                    ))

        except Exception as e:
            logger.warning("Commodity signal generation failed: %s", e, exc_info=True)

        return signals

    # ── IME (Mercantile Exchange) ───────────────────────────────────────────

    async def _signals_ime(self) -> list[MarketSignal]:
        signals: list[MarketSignal] = []
        try:
            import core.database as _db

            if _db.async_session_factory is None:
                from core.database import init_database
                await init_database()
            if _db.async_session_factory is None:
                return signals

            async with _db.async_session_factory() as session:
                # IME Futures
                ime_stmt = (
                    select(
                        ImeFutureModel.contract_code,
                        ImeFutureModel.contract_description,
                        ImeFutureModel.price_last,
                        ImeFutureModel.price_yesterday,
                        ImeFutureModel.trade_volume,
                        ImeFutureModel.open_interest,
                        ImeFutureModel.days_remaining,
                        ImeFutureModel.contract_size,
                        ImeFutureModel.contract_size_unit,
                    )
                    .where(
                        ImeFutureModel.price_last > 0,
                        ImeFutureModel.trade_volume > 0,
                    )
                    .order_by(ImeFutureModel.trade_value.desc())
                    .limit(30)
                )
                futures = (await session.execute(ime_stmt)).fetchall()

                for f in futures:
                    code, desc, price, prev, vol, oi, days, size, unit = f
                    if not price or not prev or prev <= 0:
                        continue

                    chg_pct = ((price - prev) / prev * 100) if prev else 0
                    atr_est = price * abs(chg_pct) / 100 * 2 if chg_pct else price * 0.02

                    direction = "buy" if chg_pct > 0.5 else "sell" if chg_pct < -0.5 else "hold"
                    strength = min(1.0, abs(chg_pct) / 3)

                    sl = price - atr_est * 1.5 if direction == "buy" else price + atr_est * 1.5
                    t1 = price + atr_est * 2 if direction == "buy" else price - atr_est * 2
                    t2 = price + atr_est * 3 if direction == "buy" else price - atr_est * 3
                    rr = abs(t1 - price) / max(abs(price - sl), 1)

                    signals.append(MarketSignal(
                        symbol=code, name=desc or code, market="ime",
                        direction=direction, timeframe="daily",
                        entry_zone=f"{_fmt_price(price)} {unit}",
                        stop_loss=f"{_fmt_price(sl)} (کاهش {abs(price - sl) / price * 100:.1f}٪)",
                        targets=f"هدف اول: {_fmt_price(t1)} | هدف دوم: {_fmt_price(t2)}",
                        risk_reward=f"۱ به {rr:.1f}",
                        position_sizing=f"حداکثر ۵٪ سرمایه — حجم قرارداد: {size} {unit}",
                        reason=f"تغییر: {chg_pct:+.1f}٪ | سررسید: {days} روز | OI: {oi:,}",
                        price=price, change_pct=chg_pct,
                        score=max(0, min(100, 50 + chg_pct * 5)),
                        strength=strength, confidence=0.35,
                        source="ime_futures_analysis",
                        created_at=datetime.now().isoformat(),
                    ))

        except Exception as e:
            logger.warning("IME signal generation failed: %s", e, exc_info=True)

        return signals

    # ── Generic Commodity Signal ─────────────────────────────────────────────

    def _compute_commodity_signal(
        self, sym: str, name: str, price: float, chg_pct: float,
        closes: list[float], highs: list[float], lows: list[float],
        tf_name: str, tf_days: int, market: str,
        volumes: list[float] | None = None,
    ) -> MarketSignal | None:
        if len(closes) < tf_days + 1:
            return None

        atr = _compute_atr(highs or [price], lows or [price], closes, 14) or price * 0.02
        support, resistance = _compute_support_resistance(closes)

        # Single source of truth: RSI + momentum + trend + volume/activity,
        # with a volatility filter for currency/gold (see _composite_buy_score).
        buy_score, reasons = _composite_buy_score(
            closes, highs, lows, tf_days, volumes, market,
        )
        direction = "buy" if buy_score > 0.15 else "sell" if buy_score < -0.15 else "hold"
        strength = min(1.0, max(0.0, abs(buy_score)))
        score = 50 + buy_score * 50

        sl = price - atr * 1.5 if direction == "buy" else price + atr * 1.5
        t1 = price + atr * 2 if direction == "buy" else price - atr * 2
        t2 = price + atr * 3.5 if direction == "buy" else price - atr * 3.5
        rr = abs(t1 - price) / max(abs(price - sl), 1)

        return MarketSignal(
            symbol=sym, name=name, market=market,
            direction=direction, timeframe=tf_name,
            entry_zone=f"قیمت فعلی: {_fmt_price(price)}",
            stop_loss=f"{_fmt_price(sl)} (کاهش {abs(price - sl) / price * 100:.1f}٪)",
            targets=f"هدف اول: {_fmt_price(t1)} | هدف دوم: {_fmt_price(t2)}",
            risk_reward=f"۱ به {rr:.1f}",
            position_sizing="حداکثر ۵٪ سرمایه",
            reason=" | ".join(reasons[:2]) if reasons else "تحلیل تکنیکال",
            price=price, change_pct=chg_pct,
            score=max(0, min(100, score)),
            strength=strength, confidence=0.3 + strength * 0.3,
            source=f"{market}_technical_analysis",
            created_at=datetime.now().isoformat(),
        )
