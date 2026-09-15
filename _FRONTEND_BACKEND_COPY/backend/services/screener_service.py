"""Screener Service â€” Multi-Stage Pipeline for Smart Money Stock Selection.

5-Phase Architecture (matching the mathematical spec):
  1. Liquidity Screening   â€” RVOL, value turnover, minimum value
  2. Power & Ownership     â€” Buyer power, net real money flow, concentration
  3. Price Structure       â€” Compression, relative strength, close location
  4. Order Flow            â€” Absorption, microstructure, order imbalance
  5. Trigger Score         â€” Breakout readiness, resistance proximity

Each phase produces a sub-score in [0, 1].  The final Smart Money Composite
Score (SMC) is the primary ranking metric.

Data Sources (all real, no synthetic/mock data):
  - brsapi_symbol_snapshots  â€” realtime quote (price, volume, orderbook, real/legal)
  - brsapi_historical_daily  â€” daily OHLCV history
  - brsapi_historical_real_legal â€” daily real/legal buy/sell breakdown
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from core.db_utils import safe_row_float
from services.smart_money.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTL Cache with periodic purge and hard eviction bounds
# ---------------------------------------------------------------------------


class _CacheManager:
    """Thread-safe (asyncio single-thread) TTL cache with LRU eviction.

    Features:
      - TTL-based expiry (entries older than ``ttl`` seconds are evicted)
      - Periodic purge on every access (not just when size exceeds limit)
      - Hard eviction of oldest entries when ``max_size`` is exceeded
      - LRU semantics: accessing an entry refreshes its timestamp

    Args:
        max_size: Maximum number of entries before hard eviction kicks in.
        ttl: Time-to-live in seconds. Entries older than this are evicted.
        purge_interval: Minimum seconds between periodic purges (default: 5s).
    """

    def __init__(self, max_size: int = 200, ttl: float = 30.0, purge_interval: float = 5.0) -> None:
        self._max_size = max_size
        self._ttl = ttl
        self._purge_interval = purge_interval
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._last_purge: float = time.time()
        self._total_hits: int = 0
        self._total_misses: int = 0
        self._total_evictions: int = 0

    def get(self, key: str) -> Any | None:
        """Retrieve a cached value, refreshing its LRU position.

        Returns the cached value if it exists and hasn't expired, else None.
        """
        entry = self._store.get(key)
        if entry is None:
            self._total_misses += 1
            return None

        ts, value = entry
        now = time.time()
        if now - ts > self._ttl:
            # Expired â€” remove and treat as miss
            del self._store[key]
            self._total_misses += 1
            return None

        # Move to end (most-recently used) and refresh timestamp
        del self._store[key]
        self._store[key] = (now, value)
        self._total_hits += 1
        return value

    def put(self, key: str, value: Any) -> None:
        """Insert or update a cache entry, evicting if necessary."""
        now = time.time()

        # If key exists, update in-place (move to end)
        if key in self._store:
            self._store[key] = (now, value)
            self._store.move_to_end(key)
            return

        # Periodic purge before insertion
        if now - self._last_purge >= self._purge_interval:
            self._purge_expired()
            self._last_purge = now

        # Hard eviction if still over limit (evict oldest / least-recently used)
        # After purge, at most 1 over capacity â€” single popitem suffices
        if len(self._store) >= self._max_size:
            evicted_key, _ = self._store.popitem(last=False)  # remove oldest
            self._total_evictions += 1
            logger.debug("Cache hard-evicted: %s (total evictions: %d)", evicted_key, self._total_evictions)

        self._store[key] = (now, value)

    def _purge_expired(self) -> int:
        """Remove all expired entries. Returns the number of entries removed."""
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug("Cache purged %d expired entries (remaining: %d)", len(expired), len(self._store))
        return len(expired)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._store.clear()

    @property
    def size(self) -> int:
        """Current number of entries in the cache."""
        return len(self._store)

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics for monitoring."""
        total = self._total_hits + self._total_misses
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "hits": self._total_hits,
            "misses": self._total_misses,
            "hit_rate_pct": round(self._total_hits / total * 100, 1) if total else 0.0,
            "evictions": self._total_evictions,
            "ttl_seconds": self._ttl,
        }


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------


def _parse_numeric(value: Any) -> float | None:
    """Convert a value to float, tolerating Persian/English formatting.

    Handles strings with commas, thousand separators, and percent signs.
    Returns None if the value cannot be parsed as a number.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Strip common formatting characters: commas, Persian/Arabic thousand separator, %
        cleaned = value.strip().replace(",", "").replace("٬", "").replace("%", "").replace("+", "")
        # Support negative numbers
        if cleaned.startswith("-"):
            negative = True
            cleaned = cleaned[1:]
        else:
            negative = False
        try:
            result = float(cleaned)
            return -result if negative else result
        except ValueError:
            return None
    return None


def _is_numeric(value: Any) -> bool:
    return _parse_numeric(value) is not None


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ScreenedSymbol:
    """Result of running the full pipeline on one instrument."""

    symbol: str
    name: str
    market: str
    industry: str
    last_price: float
    change_pct: float
    volume: int
    value: float

    # Phase scores (0 â€“ 1)
    liquidity_score: float = 0.0
    power_score: float = 0.0
    structure_score: float = 0.0
    orderflow_score: float = 0.0
    trigger_score: float = 0.0

    # Composite
    smc_score: float = 0.0
    phase: str = "neutral"

    # Extra info
    rank: int = 0
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Real data builders â€” map DB snapshots to engine-expected dicts
# ---------------------------------------------------------------------------


def build_real_quote_from_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    """Build engine quote dict directly from a brsapi_symbol_snapshots row.

    All values are real â€” no random/mock data.
    """
    close = float(snap.get("price_close") or 0)
    open_ = float(snap.get("price_first") or close)
    high = float(snap.get("price_max") or close)
    low = float(snap.get("price_min") or close)
    last = float(snap.get("price_last") or close)
    volume = int(snap.get("trade_volume") or 0)
    value = float(snap.get("trade_value") or 0)

    # Real / Legal volumes and counts from snapshot
    buy_real_vol = int(snap.get("buy_real_volume") or 0)
    buy_legal_vol = int(snap.get("buy_legal_volume") or 0)
    sell_real_vol = int(snap.get("sell_real_volume") or 0)
    sell_legal_vol = int(snap.get("sell_legal_volume") or 0)
    buy_real_cnt = int(snap.get("buy_real_count") or 0)
    buy_legal_cnt = int(snap.get("buy_legal_count") or 0)
    sell_real_cnt = int(snap.get("sell_real_count") or 0)
    sell_legal_cnt = int(snap.get("sell_legal_count") or 0)

    total_buy_vol = buy_real_vol + buy_legal_vol
    total_sell_vol = sell_real_vol + sell_legal_vol
    total_buy_cnt = buy_real_cnt + buy_legal_cnt
    total_sell_cnt = sell_real_cnt + sell_legal_cnt

    # avg_buy / avg_sell = average trade size per order
    avg_buy = (total_buy_vol / total_buy_cnt) if total_buy_cnt > 0 else 0.0
    avg_sell = (total_sell_vol / total_sell_cnt) if total_sell_cnt > 0 else 0.0

    # real_buy_value / real_sell_value = value of real (Ø­Ù‚ÛŒÙ‚ÛŒ) trades
    # Approximate: real volume * average price of that day
    avg_price = (high + low + close) / 3.0 if (high + low + close) > 0 else close or 1.0
    real_buy_value = buy_real_vol * avg_price
    real_sell_value = sell_real_vol * avg_price

    return {
        "symbol": snap.get("symbol", ""),
        "price_open": open_,
        "price_close": close,
        "price_high": high,
        "price_low": low,
        "price_last": last,
        "price_change": float(snap.get("price_last_change") or 0),
        "price_change_pct": float(snap.get("price_last_change_pct") or 0),
        "volume": volume,
        "value": value,
        "trade_count": int(snap["trade_count"]) if snap.get("trade_count") is not None else None,
        "avg_buy": avg_buy,
        "avg_sell": avg_sell,
        "real_buy_value": real_buy_value,
        "real_sell_value": real_sell_value,
        "real_buy_count": buy_real_cnt,
        "real_sell_count": sell_real_cnt,
        "date": snap.get("date", ""),
        "time": snap.get("time", ""),
    }


def build_real_history_from_rows(
    daily_rows: list[dict[str, Any]],
    rl_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build engine history list from real brsapi_historical_daily rows,
    enriched with real/legal data from brsapi_historical_real_legal.

    Returns list sorted oldest-first (engine expects chronological order).
    """
    if not daily_rows:
        return []

    # Build lookup for real/legal data by date
    rl_by_date: dict[str, dict[str, Any]] = {}
    if rl_rows:
        for r in rl_rows:
            dt = r.get("date", "")
            if dt:
                rl_by_date[dt] = r

    history: list[dict[str, Any]] = []
    for row in daily_rows:
        dt = row.get("date", "")
        close = float(row.get("price_close") or 0)
        open_ = float(row.get("price_first") or close)
        high = float(row.get("price_max") or close)
        low = float(row.get("price_min") or close)
        last = float(row.get("price_last") or close)
        volume = int(row.get("trade_volume") or 0)
        value = float(row.get("trade_value") or 0)

        # Merge real/legal data if available
        rl = rl_by_date.get(dt, {})
        buy_real_vol = int(rl.get("buy_real_volume") or 0)
        sell_real_vol = int(rl.get("sell_real_volume") or 0)
        buy_real_cnt = int(rl.get("buy_real_count") or 0)
        sell_real_cnt = int(rl.get("sell_real_count") or 0)
        buy_legal_vol = int(rl.get("buy_legal_volume") or 0)
        sell_legal_vol = int(rl.get("sell_legal_volume") or 0)
        buy_legal_cnt = int(rl.get("buy_legal_count") or 0)
        sell_legal_cnt = int(rl.get("sell_legal_count") or 0)

        total_buy_vol = buy_real_vol + buy_legal_vol
        total_sell_vol = sell_real_vol + sell_legal_vol
        total_buy_cnt = buy_real_cnt + buy_legal_cnt
        total_sell_cnt = sell_real_cnt + sell_legal_cnt

        avg_buy = (total_buy_vol / total_buy_cnt) if total_buy_cnt > 0 else 0.0
        avg_sell = (total_sell_vol / total_sell_cnt) if total_sell_cnt > 0 else 0.0

        avg_price = (high + low + close) / 3.0 if (high + low + close) > 0 else close or 1.0
        real_buy_value = buy_real_vol * avg_price
        real_sell_value = sell_real_vol * avg_price

        history.append(
            {
                "symbol": row.get("symbol", ""),
                "date": dt,
                "price_open": open_,
                "price_close": close,
                "price_high": high,
                "price_low": low,
                "price_last": last,
                "volume": volume,
                "value": value,
                "trade_count": int(row["trade_count"]) if row.get("trade_count") is not None else None,
                "avg_buy": avg_buy,
                "avg_sell": avg_sell,
                "real_buy_value": real_buy_value,
                "real_sell_value": real_sell_value,
                "real_buy_count": buy_real_cnt,
                "real_sell_count": sell_real_cnt,
            }
        )

    # Sort oldest first
    history.sort(key=lambda h: h.get("date", ""))
    return history


# ---------------------------------------------------------------------------
# Filter value extraction â€” maps field names to real snapshot data
# ---------------------------------------------------------------------------


#: Comprehensive filter field catalog.
#: Maps user-facing field names to ScreenedSymbol attributes or details keys.
_FILTER_FIELD_MAP: dict[str, str] = {
    # â”€â”€ Core info â”€â”€
    "symbol": "symbol",
    "name": "name",
    "market": "market",
    "industry": "industry",
    "sector": "industry",
    # â”€â”€ Smart Money composite / phase scores â”€â”€
    "smc_score": "smc_score",
    "smart_money_score": "smc_score",
    "liquidity_score": "liquidity_score",
    "power_score": "power_score",
    "structure_score": "structure_score",
    "orderflow_score": "orderflow_score",
    "order_flow_score": "orderflow_score",
    "trigger_score": "trigger_score",
    "phase": "phase",
    # â”€â”€ Price & change â”€â”€
    "last_price": "last_price",
    "price": "last_price",
    "close": "last_price",
    "change_pct": "change_pct",
    "price_change_pct": "change_pct",
    "price_change_value": "price_change_value",
    "price_change": "price_change_value",
    "price_first": "price_first",
    "open": "price_first",
    "price_yesterday": "price_yesterday",
    "price_min": "price_min",
    "low": "price_min",
    "price_max": "price_max",
    "high": "price_max",
    # â”€â”€ Volume / turnover â”€â”€
    "volume": "volume",
    "trade_volume": "volume",
    "value": "value",
    "trade_value": "value",
    "turnover": "value",
    "trade_count": "trade_count",
    "trades": "trade_count",
    "shares_count": "shares_count",
    # â”€â”€ Fundamental â”€â”€
    "pe_ratio": "pe_ratio",
    "pe": "pe_ratio",
    "p/e": "pe_ratio",
    "eps": "eps",
    "market_value": "market_value",
    "market_cap": "market_value",
    "roe": "roe",
    "debt_to_equity": "debt_to_equity",
    "d/e": "debt_to_equity",
    "net_margin": "net_margin",
    # â”€â”€ V2 advanced analytics (stored in item.details by V2 engine) â”€â”€
    "rsi": "rsi",
    "rsi_14": "rsi",
    "macd_histogram": "macd_histogram",
    "macd": "macd_histogram",
    "bb_pct": "bb_pct",
    "bollinger_pct": "bb_pct",
    "atr_pct": "atr_pct",
    "atr": "atr_pct",
    "adx": "adx",
    "trend_strength": "trend_strength",
    "pattern_confidence": "pattern_confidence",
    "technical_score": "technical_score",
    "momentum_score": "momentum_score",
    "risk_score": "risk_score",
    "composite_score": "composite_score",
    "support_level": "support_level",
    "resistance_level": "resistance_level",
    "distance_to_support": "distance_to_support",
    "distance_to_resistance": "distance_to_resistance",
    "poc_price": "poc_price",
    "value_area_high": "value_area_high",
    "value_area_low": "value_area_low",
    "volume_trend": "volume_trend",
    "volatility_regime": "volatility_regime",
    "trend_direction": "trend_direction",
    "pattern_signal": "pattern_signal",
    "cci": "cci",
    "mfi": "mfi",
    "williams_r": "williams_r",
    "williams": "williams_r",
    "stochastic_k": "stochastic_k",
    "stochastic": "stochastic_k",
    "composite_signal": "composite_signal",
}


def _get_filter_value(item: ScreenedSymbol, watch: dict[str, Any], field: str) -> float | str | None:
    """Extract a value (numeric or string) from the screened item or watch data.

    Numeric values are returned as float, including formatted strings such as
    ``"1,234"`` or ``"12.5%"``. Non-numeric strings are returned as-is.
    """
    if not field:
        return None

    mapped = _FILTER_FIELD_MAP.get(field.lower(), field.lower())
    details = item.details or {}

    candidates: list[Any] = []
    if hasattr(item, mapped):
        candidates.append(getattr(item, mapped, None))
    candidates.append(details.get(mapped))
    if isinstance(watch, dict):
        candidates.extend(
            [
                watch.get(mapped),
                watch.get(field.lower()),
                watch.get(f"price_{field.lower()}"),
                watch.get(f"trade_{field.lower()}"),
            ]
        )

    for val in candidates:
        if val is None:
            continue
        if isinstance(val, bool):
            # Treat booleans as numeric 0/1 so operators like gte/lte work
            return float(int(val))
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str) and val.strip():
            numeric = _parse_numeric(val)
            if numeric is not None:
                return numeric
            return val


def _get_sort_value(item: ScreenedSymbol, field: str) -> float:
    """Safe sort-key helper: returns the numeric value or 0.0 if None.

    Unlike `_get_filter_value(..., {}, ...) or 0.0`, this correctly preserves
    actual zero values (e.g. pe_ratio=0) rather than treating them as falsy.
    """
    if not field:
        return 0.0

    mapped = _FILTER_FIELD_MAP.get(field.lower(), field.lower())

    # 1. Direct attribute on ScreenedSymbol
    val = getattr(item, mapped, None)
    if val is not None:
        try:
            return float(val) if not isinstance(val, bool) else float(int(val))
        except (ValueError, TypeError):
            pass

    # 2. Inside details dict
    details = item.details or {}
    val = details.get(mapped)
    if val is not None:
        try:
            return float(val) if not isinstance(val, bool) else float(int(val))
        except (ValueError, TypeError):
            pass

    # 3. Fall back to 0.0 (sort-safe default)
    return 0.0

    return None


# ---------------------------------------------------------------------------
# Screener pipeline
# ---------------------------------------------------------------------------


class ScreenerPipeline:
    """5-phase pipeline that scores a single instrument via the Smart Money engine."""

    _score_cache = _CacheManager(max_size=300, ttl=30.0, purge_interval=5.0)

    def __init__(self) -> None:
        self._engine = ScoringEngine()

    @classmethod
    def _cache_key(cls, symbol: str, quote: dict[str, Any], history: list[dict[str, Any]]) -> str:
        q_fields = ("price_close", "price_last", "volume", "value", "price_change_pct")
        q_hash = tuple(round(quote.get(f, 0), 2) for f in q_fields)
        h_last = history[-1].get("price_close", 0) if history else 0
        return f"{symbol}:{hash(q_hash)}:{h_last:.0f}:{len(history)}"

    def run(
        self,
        symbol: str,
        name: str,
        market: str,
        industry: str,
        quote: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ScreenedSymbol:
        cache_key = self._cache_key(symbol, quote, history)
        cached = self._score_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = self._engine.analyze(quote, history)
        except Exception as exc:
            logger.warning("Screener engine failed for %s: %s", symbol, exc)
            return ScreenedSymbol(
                symbol=symbol,
                name=name,
                market=market,
                industry=industry,
                last_price=quote.get("price_close", 0.0),
                change_pct=0.0,
                volume=int(quote.get("volume", 0)),
                value=float(quote.get("value", 0)),
                reason=f"Engine error: {exc}",
            )

        scores = result.get("scores", {})
        penalties = result.get("penalties", {})
        features = result.get("features", {})
        smc = result.get("smart_money_score", 0.0)
        phase = result.get("phase", "neutral")

        # Phase scores
        rvol_n = features.get("rvol_n", 0.0)
        vtr_n = features.get("vtr_n", 0.0)
        pvs = scores.get("accumulation", 0.0)
        liquidity_score = min(1.0, max(0.0, 0.35 * rvol_n + 0.35 * vtr_n + 0.30 * pvs))

        bp_n = features.get("bp_n", 0.0)
        nrmf_n = features.get("nrmf_n", 0.0)
        bc_n = features.get("bc_n", 0.0)
        power_score = min(
            1.0, max(0.0, 0.40 * bp_n + 0.30 * nrmf_n + 0.15 * bc_n + 0.15 * scores.get("buyer_power", 0.0))
        )

        rec_n = features.get("rec_n", 0.0)
        clv_n = features.get("clv_n", 0.0)
        rrs = scores.get("breakout_readiness", 0.0)
        ess = scores.get("float_lock", 0.0)
        structure_score = min(1.0, max(0.0, 0.25 * clv_n + 0.25 * rec_n + 0.25 * rrs + 0.25 * ess))

        lss_n = features.get("lss_n", 0.0)
        rmr_n = features.get("rmr_n", 0.0)
        abs_score = scores.get("absorption", 0.0)
        dry_n = features.get("dry_n", 0.0)
        orderflow_score = min(
            1.0,
            max(
                0.0,
                0.30 * abs_score
                + 0.20 * lss_n
                + 0.20 * rmr_n
                + 0.15 * dry_n
                + 0.15 * scores.get("microstructure", 0.0),
            ),
        )

        br = scores.get("breakout_readiness", 0.0)
        trigger_score = min(1.0, max(0.0, 0.60 * br + 0.20 * rrs + 0.10 * abs_score + 0.10 * ess))

        # Composite with penalties
        dist_risk = penalties.get("distribution_risk", 0.0)
        fake_risk = penalties.get("fake_breakout_risk", 0.0)
        dead_comp = penalties.get("dead_compression", 0.0)
        penalty_factor = 1.0 - 0.15 * dist_risk - 0.10 * fake_risk - 0.08 * dead_comp
        smc_adjusted = max(0.0, smc * max(0.0, penalty_factor))

        reasons = []
        if liquidity_score > 0.6:
            reasons.append("Ù†Ù‚Ø¯Ø´ÙˆÙ†Ø¯Ú¯ÛŒ Ø¨Ø§Ù„Ø§")
        if power_score > 0.6:
            reasons.append("ÙˆØ±ÙˆØ¯ Ù¾ÙˆÙ„ Ù‚ÙˆÛŒ")
        if structure_score > 0.6:
            reasons.append("Ø³Ø§Ø®ØªØ§Ø± Ù‚ÛŒÙ…ØªÛŒ Ù…Ø³ØªØ­Ú©Ù…")
        if orderflow_score > 0.6:
            reasons.append("Ø¬Ø°Ø¨ Ø¹Ø±Ø¶Ù‡ ÙØ¹Ø§Ù„")
        if trigger_score > 0.6:
            reasons.append("Ø¢Ù…Ø§Ø¯Ù‡ Ø´Ú©Ø³Øª")
        reason = " Â· ".join(reasons) if reasons else ("Ø¯Ø± Ø­Ø§Ù„ Ù†Ø¸Ø§Ø±Øª" if smc_adjusted > 0.4 else "Ø¶Ø¹ÛŒÙ")

        details = {
            "liquidity_score": round(liquidity_score, 4),
            "power_score": round(power_score, 4),
            "structure_score": round(structure_score, 4),
            "orderflow_score": round(orderflow_score, 4),
            "trigger_score": round(trigger_score, 4),
            "smc_score": round(smc_adjusted, 4),
            "rvol_n": round(rvol_n, 4),
            "bp_n": round(bp_n, 4),
            "nrmf_n": round(nrmf_n, 4),
            "clv_n": round(clv_n, 4),
            "rec_n": round(rec_n, 4),
            "abs_score": round(abs_score, 4),
        }
        details.update({k: round(v, 4) for k, v in features.items() if isinstance(v, float) and k not in details})

        result_obj = ScreenedSymbol(
            symbol=symbol,
            name=name,
            market=market,
            industry=industry,
            last_price=quote.get("price_close", 0.0),
            change_pct=quote.get("price_change_pct", 0.0),
            volume=int(quote.get("volume", 0)),
            value=float(quote.get("value", 0)),
            liquidity_score=round(liquidity_score, 4),
            power_score=round(power_score, 4),
            structure_score=round(structure_score, 4),
            orderflow_score=round(orderflow_score, 4),
            trigger_score=round(trigger_score, 4),
            smc_score=round(smc_adjusted, 4),
            phase=phase,
            reason=reason,
            details=details,
        )

        self._score_cache.put(cache_key, result_obj)
        return result_obj


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------


class ScreenerService:
    """Main screener service â€” run the pipeline over a list of instruments.

    Uses real data from PostgreSQL:
      - brsapi_symbol_snapshots for current quote
      - brsapi_historical_daily for daily history
      - brsapi_historical_real_legal for real/legal breakdown

    history_limit: how many days of history to fetch per symbol (default 60).
    """

    _prebuilt_cache = _CacheManager(max_size=200, ttl=20.0, purge_interval=5.0)

    def __init__(self, session=None, history_limit: int = 60) -> None:
        self._pipeline = ScreenerPipeline()
        self._session = session
        self._history_limit = history_limit

    async def _fetch_real_history(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch real daily history + real/legal from PostgreSQL."""
        if self._session is None:
            return []

        from sqlalchemy import text

        # Fetch daily OHLCV from daily_history (via symbols FK)
        daily_q = text("""
            SELECT s.symbol, dh.trade_date as date, dh.price_first, dh.price_close,
                   dh.price_max, dh.price_min, dh.price_last,
                   dh.trade_volume, dh.trade_value, dh.trade_count
            FROM daily_history dh
            JOIN symbols s ON s.id = dh.symbol_id
            WHERE s.symbol = :sym
            ORDER BY dh.trade_date DESC
            LIMIT :lim
        """)
        result = await self._session.execute(daily_q, {"sym": symbol, "lim": self._history_limit})
        daily_rows = [dict(row._mapping) for row in result.fetchall()]

        if not daily_rows:
            return []

        # Fetch real/legal breakdown from daily_real_legal
        rl_q = text("""
            SELECT s.symbol, drl.trade_date as date,
                   drl.real_buy_volume as buy_real_volume,
                   drl.real_sell_volume as sell_real_volume,
                   drl.real_buy_count as buy_real_count,
                   drl.real_sell_count as sell_real_count,
                   drl.legal_buy_volume as buy_legal_volume,
                   drl.legal_sell_volume as sell_legal_volume,
                   drl.legal_buy_count as buy_legal_count,
                   drl.legal_sell_count as sell_legal_count
            FROM daily_real_legal drl
            JOIN symbols s ON s.id = drl.symbol_id
            WHERE s.symbol = :sym
            ORDER BY drl.trade_date DESC
            LIMIT :lim
        """)
        rl_result = await self._session.execute(rl_q, {"sym": symbol, "lim": self._history_limit})
        rl_rows = [dict(row._mapping) for row in rl_result.fetchall()]

        return build_real_history_from_rows(daily_rows, rl_rows)

    def _prebuild_sync(
        self, snap: dict[str, Any], history: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Build quote from snapshot (sync) + pre-fetched history."""
        quote = build_real_quote_from_snapshot(snap)
        return quote, history

    async def _prebuild(self, snap: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Build quote + fetch real history for a snapshot row."""
        sym = snap.get("symbol", "")

        cached = self._prebuilt_cache.get(sym)
        if cached is not None:
            return cached

        quote = build_real_quote_from_snapshot(snap.get("_snapshot", snap))
        history = await self._fetch_real_history(sym)
        self._prebuilt_cache.put(sym, (quote, history))
        return quote, history

    async def _fetch_fundamental_data(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch Codal fundamental data for a list of symbols."""
        if self._session is None or not symbols:
            return {}

        from sqlalchemy import text

        placeholders = ", ".join([f":sym{i}" for i in range(len(symbols))])
        params = {f"sym{i}": sym for i, sym in enumerate(symbols)}

        result = await self._session.execute(
            text(f"""
            SELECT symbol, pe_ratio, roe, debt_to_equity, net_margin, eps
            FROM codal_financial_summary
            WHERE symbol IN ({placeholders})
        """),
            params,
        )

        return {
            row[0]: {
                "pe_ratio": safe_row_float(row, idx=1),
                "roe": safe_row_float(row, idx=2),
                "debt_to_equity": safe_row_float(row, idx=3),
                "net_margin": safe_row_float(row, idx=4),
                "eps": safe_row_float(row, idx=5),
            }
            for row in result.fetchall()
        }

    def _apply_fundamental_filter(
        self,
        instruments: list[dict[str, Any]],
        fundamental_data: dict[str, dict[str, Any]],
        max_debt_to_equity: float = 5.0,
        min_roe: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Filter instruments based on fundamental criteria.

        Phase 0: Pre-filter based on Codal financial data.
        - Remove stocks with Debt-to-Equity > max_debt_to_equity
        - Remove stocks with ROE < min_roe (negative profitability)
        """
        filtered = []
        for instr in instruments:
            sym = instr.get("symbol", "")
            fund = fundamental_data.get(sym)

            if fund is None:
                # No fundamental data available â€” keep (don't filter out unknowns)
                filtered.append(instr)
                continue

            # Filter: Debt-to-Equity too high
            dte = fund.get("debt_to_equity")
            if dte is not None and dte > max_debt_to_equity:
                logger.debug("Filtered %s: D/E=%.1f > %.1f", sym, dte, max_debt_to_equity)
                continue

            # Filter: ROE negative
            roe = fund.get("roe")
            if roe is not None and roe < min_roe:
                logger.debug("Filtered %s: ROE=%.1f%% < %.1f%%", sym, roe, min_roe)
                continue

            filtered.append(instr)

        return filtered

    async def screen(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        sort_by: str = "smc_score",
        sort_order: str = "desc",
        limit: int = 50,
        min_score: float = 0.0,
        market: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        max_debt_to_equity: float = 5.0,
        min_roe: float = 0.0,
    ) -> tuple[list[ScreenedSymbol], dict[str, Any]]:
        """Run the full pipeline (Phase 0: fundamental filter + 5-phase Smart Money) over instruments."""
        watch_map: dict[str, dict[str, Any]] = {}
        for w_item in market_watch:
            watch_map[w_item.get("symbol", "")] = w_item

        # Phase 0: Apply fundamental filter if thresholds are meaningful
        # Only run if the user explicitly set non-default thresholds
        if max_debt_to_equity < 5.0 or min_roe > 0.0:
            all_syms = [i.get("symbol", "") for i in instruments if i.get("symbol")]
            fundamental_data = await self._fetch_fundamental_data(all_syms)
            if fundamental_data:
                instruments = self._apply_fundamental_filter(
                    instruments,
                    fundamental_data,
                    max_debt_to_equity=max_debt_to_equity,
                    min_roe=min_roe,
                )

        results: list[ScreenedSymbol] = []
        for instr in instruments:
            sym = instr.get("symbol", "")
            if market and instr.get("market") != market:
                continue
            w = watch_map.get(sym)
            if not w:
                continue

            quote, history = await self._prebuild(w)

            item = self._pipeline.run(
                symbol=sym,
                name=instr.get("name", sym),
                market=instr.get("market", ""),
                industry=instr.get("industry", ""),
                quote=quote,
                history=history,
            )
            if item.smc_score < min_score:
                continue
            results.append(item)

        reverse = sort_order.lower() != "asc"
        results.sort(key=lambda r: _get_sort_value(r, sort_by), reverse=reverse)

        total_before_pagination = len(results)

        for i, r in enumerate(results, 1):
            r.rank = i

        if page is not None and page_size is not None:
            offset = (page - 1) * page_size
            results = results[offset : offset + page_size]

        paginated_results = results[:limit] if page is None else results

        pagination_info = {
            "total": total_before_pagination,
            "page": page or 1,
            "page_size": page_size or limit,
            "total_pages": (total_before_pagination + (page_size or limit) - 1) // (page_size or limit)
            if page_size
            else 1,
        }

        return paginated_results, pagination_info

    async def screen_with_filters(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        filters: list[dict[str, Any]] | None = None,
        filter_logic: str = "and",
        sort_by: str = "smc_score",
        sort_order: str = "desc",
        limit: int = 100,
        min_score: float = 0.0,
        market: str | None = None,
        include_details: bool = False,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[ScreenedSymbol], dict[str, Any]]:
        """Run the pipeline with dynamic filter criteria on real data."""
        watch_map: dict[str, dict[str, Any]] = {}
        for w_item in market_watch:
            watch_map[w_item.get("symbol", "")] = w_item

        all_scored: list[ScreenedSymbol] = []
        for instr in instruments:
            sym = instr.get("symbol", "")
            if market and instr.get("market") != market:
                continue
            w = watch_map.get(sym)
            if not w:
                continue

            quote, history = await self._prebuild(w)

            item = self._pipeline.run(
                symbol=sym,
                name=instr.get("name", sym),
                market=instr.get("market", ""),
                industry=instr.get("industry", ""),
                quote=quote,
                history=history,
            )
            if item.smc_score < min_score:
                continue

            # Populate details BEFORE filtering so filters can use pe_ratio, eps, etc.
            if include_details:
                for real_field in (
                    "pe_ratio",
                    "eps",
                    "market_value",
                    "trade_count",
                    "price_change_value",
                    "price_first",
                    "price_yesterday",
                    "price_min",
                    "price_max",
                    "shares_count",
                ):
                    if real_field in w and w[real_field] is not None:
                        item.details[real_field] = float(w[real_field])

            if filters and not self._apply_filter(item, w, filters, filter_logic):
                continue

            all_scored.append(item)

        reverse = sort_order.lower() != "asc"
        all_scored.sort(key=lambda r: _get_sort_value(r, sort_by), reverse=reverse)

        for i, r in enumerate(all_scored, 1):
            r.rank = i

        total_before_pagination = len(all_scored)

        if page is not None and page_size is not None:
            offset = (page - 1) * page_size
            paginated = all_scored[offset : offset + page_size]
        else:
            paginated = all_scored[:limit]

        # Compute stats from ALL scored results, not just the paginated subset
        stats = self._compute_stats(all_scored, all_scored, market_watch)
        stats["total"] = total_before_pagination
        stats["page"] = page or 1
        stats["page_size"] = page_size or limit
        stats["total_pages"] = (
            (total_before_pagination + (page_size or limit) - 1) // (page_size or limit) if page_size else 1
        )

        return paginated, stats

    def _compute_stats(
        self,
        results: list[ScreenedSymbol],
        all_scored: list[ScreenedSymbol],
        market_watch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "avg_smc": 0.0,
                "avg_liquidity": 0.0,
                "avg_power": 0.0,
                "avg_change_pct": 0.0,
                "high_score_count": 0,
                "phase_distribution": {},
                "top_industry": "",
                "top_industry_count": 0,
            }

        avg_smc = sum(r.smc_score for r in results) / total
        avg_liq = sum(r.liquidity_score for r in results) / total
        avg_pow = sum(r.power_score for r in results) / total
        avg_chg = sum(r.change_pct for r in results) / total
        high_score = sum(1 for r in results if r.smc_score >= 0.6)

        phases: dict[str, int] = {}
        for r in results:
            phases[r.phase] = phases.get(r.phase, 0) + 1

        industries: dict[str, int] = {}
        for r in results:
            if r.industry:
                industries[r.industry] = industries.get(r.industry, 0) + 1
        top_ind = max(industries, key=industries.get) if industries else ""
        top_ind_count = industries.get(top_ind, 0)

        return {
            "total": total,
            "avg_smc": round(avg_smc, 4),
            "avg_liquidity": round(avg_liq, 4),
            "avg_power": round(avg_pow, 4),
            "avg_change_pct": round(avg_chg, 4),
            "high_score_count": high_score,
            "phase_distribution": phases,
            "top_industry": top_ind,
            "top_industry_count": top_ind_count,
        }

    @staticmethod
    def _apply_filter(
        item: ScreenedSymbol,
        watch: dict[str, Any],
        filters: list[dict[str, Any]],
        logic: str,
    ) -> bool:
        """Apply a list of dynamic filters to a single screened symbol.

        Supports numeric (gte, lte, gt, lt, eq, neq, between) and string
        (eq, neq, contains, in, not_in) operators. Numeric values tolerate
        strings with commas and percent signs.
        """
        results: list[bool] = []
        numeric_ops = {"gte", "lte", "gt", "lt", "eq", "neq", "between"}

        for f in filters:
            field = f.get("field", "")
            operator = f.get("operator", "gte")
            value = f.get("value")
            value_to = f.get("value_to")

            item_val = _get_filter_value(item, watch, field)
            if item_val is None:
                # Missing data: the only matching operators are is_null / is_not_null,
                # which are not currently supported, so fail this filter.
                results.append(False)
                continue

            # String operators always compare as strings
            if operator in {"contains", "in", "not_in"} or (
                operator in {"eq", "neq"} and isinstance(item_val, str) and _parse_numeric(item_val) is None
            ):
                item_str = str(item_val).lower()
                if operator == "eq":
                    results.append(item_str == str(value).lower())
                elif operator == "neq":
                    results.append(item_str != str(value).lower())
                elif operator == "contains":
                    results.append(str(value).lower() in item_str)
                elif operator == "in":
                    values_list = [str(v).lower() for v in (value if isinstance(value, list) else [value])]
                    results.append(item_str in values_list)
                elif operator == "not_in":
                    values_list = [str(v).lower() for v in (value if isinstance(value, list) else [value])]
                    results.append(item_str not in values_list)
                else:
                    results.append(False)
                continue

            # Numeric operators: attempt to coerce both sides to float
            item_num = _parse_numeric(item_val)
            val_num = _parse_numeric(value) if value is not None else None
            val_to_num = _parse_numeric(value_to) if value_to is not None else None

            if item_num is None:
                results.append(False)
                continue

            if operator in numeric_ops:
                if operator == "between":
                    if val_num is None or val_to_num is None:
                        results.append(False)
                    else:
                        results.append(val_num <= item_num <= val_to_num)
                elif val_num is None:
                    results.append(False)
                elif operator == "gte":
                    results.append(item_num >= val_num)
                elif operator == "lte":
                    results.append(item_num <= val_num)
                elif operator == "gt":
                    results.append(item_num > val_num)
                elif operator == "lt":
                    results.append(item_num < val_num)
                elif operator == "eq":
                    tolerance = max(abs(val_num) * 0.01, 0.001)
                    results.append(abs(item_num - val_num) < tolerance)
                elif operator == "neq":
                    results.append(item_num != val_num)
                else:
                    results.append(True)
            else:
                # Unknown operator; fail closed
                results.append(False)

        if not results:
            return True
        return any(results) if logic == "or" else all(results)

    def screen_by_symbol(
        self,
        instruments: list[dict[str, Any]],
        market_watch: list[dict[str, Any]],
        symbol: str,
    ) -> ScreenedSymbol | None:
        """Run the pipeline for a single symbol (sync mode, no async history fetch).

        Note: This method does NOT fetch history, so analysis quality is limited.
        For full analysis, use screen() or screen_with_filters() which fetch real history.
        """
        instr = next((i for i in instruments if i.get("symbol") == symbol), None)
        if not instr:
            return None
        w = next((mw for mw in market_watch if mw.get("symbol") == symbol), None)
        if not w:
            return None

        quote = build_real_quote_from_snapshot(w)
        # Try to get cached history if available
        cached_entry = self._prebuilt_cache.get(symbol)
        history = cached_entry[1] if cached_entry else []  # (quote, history) tuple
        return self._pipeline.run(
            symbol=symbol,
            name=instr.get("name", symbol),
            market=instr.get("market", ""),
            industry=instr.get("industry", ""),
            quote=quote,
            history=history,
        )
