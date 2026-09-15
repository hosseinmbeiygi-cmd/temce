"""FX Adapter — validates and normalizes currency price data.

Architecture follows the gold pattern (document §5.2):
- MAX_JUMP_PCT = 0.08: reject ticks jumping >8% from previous price
- quality_flag=2 for suspicious data (preserves data for review instead of dropping)
- Validates price > 0 and timestamp presence
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


@dataclass
class FxValidationResult:
    """Result of FX data validation."""

    clean_rows: list[dict[str, Any]] = None  # type: ignore[assignment]
    dropped_count: int = 0
    suspicious_count: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.clean_rows is None:
            self.clean_rows = []
        if self.errors is None:
            self.errors = []


class FxAdapter:
    """Validates and normalizes FX/currency price data.

    This adapter enforces jump detection on currency prices to catch
    source data errors while preserving suspicious data for later review
    rather than silently dropping it.

    Usage::

        adapter = FxAdapter()
        result = adapter.validate(raw_prices, last_known_prices)
        normalized = adapter.normalize(result.clean_rows)

    Configuration (env vars):
        BRSAPI_FX_MAX_JUMP_PCT: Maximum allowed price jump percentage (default: 0.08)
        BRSAPI_FX_PRIMARY_SYMBOLS: Comma-separated list of primary symbols to track
    """

    # Maximum allowed price change between consecutive ticks.
    # 8% is generous enough for normal FX volatility but catches
    # data source errors (e.g. API returning stale/wrong prices).
    MAX_JUMP_PCT: float = 0.08

    # Primary symbols for signal generation (free market rates)
    PRIMARY_SYMBOLS: list[str] = [
        "USD",  # دلار — بازار آزاد
        "EUR",  # یورو
        "GBP",  # پوند
        "AED",  # درهم امارات
        "SAR",  # ریال عربستان
        "TRY",  # لیر ترکیه
        "USDT_IRT",  # دلار تتر (crypto proxy for USD/IRR)
    ]

    # Reference symbols (NIMA/official rates, if available from API)
    REFERENCE_SYMBOLS: list[str] = [
        # Currently BrsApi doesn't distinguish NIMA vs free market.
        # When/if it does, NIMA symbols would go here.
    ]

    def __init__(
        self,
        max_jump_pct: float | None = None,
        primary_symbols: list[str] | None = None,
    ) -> None:
        if max_jump_pct is not None:
            self.MAX_JUMP_PCT = max_jump_pct
        if primary_symbols is not None:
            self.PRIMARY_SYMBOLS = primary_symbols

    def validate(
        self,
        raw: list[dict[str, Any]],
        last_known: dict[str, float] | None = None,
    ) -> FxValidationResult:
        """Validate raw FX price data against jump thresholds.

        Args:
            raw: Raw price records from BrsApi.
            last_known: Map of symbol → last known price for jump detection.

        Returns:
            FxValidationResult with clean rows, dropped count, and suspicious count.
        """
        result = FxValidationResult()
        last_known = last_known or {}

        for row in raw:
            symbol = row.get("symbol", "")
            price = row.get("price")
            fetched_at = row.get("fetched_at")

            # Basic validation: price must exist and be positive
            if price is None or price <= 0:
                result.dropped_count += 1
                result.errors.append(f"Dropped {symbol}: invalid price {price}")
                continue

            # Fetched timestamp must exist
            if not fetched_at:
                row["fetched_at"] = datetime.now(UTC).isoformat()

            # Jump detection against last known price
            prev_price = last_known.get(symbol)
            if prev_price is not None and prev_price > 0:
                jump_pct = abs(price - prev_price) / prev_price
                if jump_pct > self.MAX_JUMP_PCT:
                    # Flag as suspicious (quality_flag=2) but DON'T drop
                    # the data — it may be legitimate extreme volatility
                    # and should be available for review.
                    row["quality_flag"] = 2
                    result.suspicious_count += 1
                    logger.warning(
                        "FX suspicious jump: %s price %.0f → %.0f (%.1f%% > %.1f%% threshold)",
                        symbol,
                        prev_price,
                        price,
                        jump_pct * 100,
                        self.MAX_JUMP_PCT * 100,
                    )
                else:
                    row["quality_flag"] = 0
            else:
                # No previous price available — can't validate jump
                row["quality_flag"] = 0

            result.clean_rows.append(row)

        if result.suspicious_count > 0:
            logger.info(
                "FX validation: %d clean, %d suspicious, %d dropped",
                len(result.clean_rows),
                result.suspicious_count,
                result.dropped_count,
            )

        return result

    def normalize(self, clean_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize validated FX rows into a consistent schema.

        Maps raw BrsApi fields to the internal representation used by
        the database models and signal engine.

        Args:
            clean_rows: Validated rows from validate().

        Returns:
            List of normalized dicts ready for DB upsert.
        """
        normalized = []
        now = datetime.now(UTC).isoformat()

        for row in clean_rows:
            symbol = row.get("symbol", "")
            name = row.get("name", "")
            price = row.get("price", 0)
            change_value = row.get("change_value", 0) or 0
            change_percent = row.get("change_percent", 0) or 0
            quality_flag = row.get("quality_flag", 0)

            normalized.append(
                {
                    # Identity
                    "symbol": symbol,
                    "name": name,
                    # Price data
                    "price": price,
                    "change_value": change_value,
                    "change_percent": change_percent,
                    # Metadata
                    "unit": row.get("unit", "IRR"),
                    "date": row.get("date", ""),
                    "time": row.get("time", ""),
                    "time_unix": row.get("time_unix"),
                    "fetched_at": row.get("fetched_at", now),
                    "raw_json": row.get("raw_json"),
                    # FX-specific
                    "quality_flag": quality_flag,
                    "market": "fx",
                }
            )

        return normalized

    def is_primary(self, symbol: str) -> bool:
        """Check if a symbol is a primary (signal-worthy) FX symbol."""
        return symbol in self.PRIMARY_SYMBOLS

    def symbol_label(self, symbol: str) -> str:
        """Return a human-readable label for the symbol."""
        labels = {
            "USD": "دلار / بازار آزاد",
            "EUR": "یورو / بازار آزاد",
            "GBP": "پوند / بازار آزاد",
            "AED": "درهم امارات",
            "SAR": "ریال عربستان",
            "TRY": "لیر ترکیه",
            "USDT_IRT": "دلار تتر",
        }
        return labels.get(symbol, symbol)


# ── FX Symbol Constants ──────────────────────────────────────────────

# Symbols tracked for 24h monitoring and signal generation.
# These are the free-market rate symbols that the signal engine uses.
FX_TRACKED_SYMBOLS: list[str] = [
    "USD",  # دلار — بازار آزاد (PRIMARY)
    "EUR",  # یورو
    "GBP",  # پوند
    "AED",  # درهم امارات
    "SAR",  # ریال عربستان
    "TRY",  # لیر ترکیه
    "USDT_IRT",  # دلار تتر
    "CNY",  # یوآن چین
    "JPY",  # ین ژاپن
    "CHF",  # فرانک سوئیس
    "CAD",  # دلار کانادا
    "AUD",  # دلار استرالیا
    "KWD",  # دینار کویت
]

# Quality gate thresholds for FX data readiness.
FX_MIN_ROWS = 200  # Minimum rows in last 24h for signal readiness
FX_MAX_STALENESS_MIN = 15  # Maximum minutes since last sync before data is stale
FX_MAX_SUSPECT_RATIO = 0.05  # Maximum ratio of suspicious (quality_flag=2) rows
