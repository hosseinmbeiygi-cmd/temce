"""Gold Adapter — validates and normalizes gold price data.

Architecture follows the gold implementation document (section 4.2):
- Validates price > 0 and timestamp presence
- Flags suspicious data (quality_flag=2) for review
- Normalizes to consistent schema for DB storage

Gold symbols tracked:
- IR_GOLD_18K: طلای ۱۸ عیار
- IR_GOLD_24K: طلای ۲۴ عیار
- IR_GOLD_MELTED: طلای آب‌شده نقدی
- IR_COIN_EMAMI: سکه امامی
- IR_COIN_BAHAR: سکه بهار آزادی
- IR_COIN_HALF: نیم سکه
- IR_COIN_QUARTER: ربع سکه
- IR_COIN_1G: سکه یک گرمی
- XAUUSD: انس طلا (جهانی)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


@dataclass
class GoldValidationResult:
    """Result of gold data validation."""

    clean_rows: list[dict[str, Any]] = None  # type: ignore[assignment]
    dropped_count: int = 0
    suspicious_count: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.clean_rows is None:
            self.clean_rows = []
        if self.errors is None:
            self.errors = []


class GoldAdapter:
    """Validates and normalizes gold price data.

    This adapter enforces price validation on gold prices to catch
    source data errors while preserving suspicious data for later review.

    Usage::

        adapter = GoldAdapter()
        result = adapter.validate(raw_prices)
        normalized = adapter.normalize(result.clean_rows)
    """

    # Primary gold symbols for signal generation
    PRIMARY_SYMBOLS: list[str] = [
        "IR_GOLD_18K",  # طلای ۱۸ عیار
        "IR_GOLD_24K",  # طلای ۲۴ عیار
        "IR_GOLD_MELTED",  # طلای آب‌شده نقدی
        "IR_COIN_EMAMI",  # سکه امامی
        "IR_COIN_BAHAR",  # سکه بهار آزادی
        "IR_COIN_HALF",  # نیم سکه
        "IR_COIN_QUARTER",  # ربع سکه
        "IR_COIN_1G",  # سکه یک گرمی
    ]

    # Global feature symbols (for correlation analysis)
    GLOBAL_FEATURES: list[str] = [
        "XAUUSD",  # انس طلا جهانی
    ]

    def __init__(
        self,
        primary_symbols: list[str] | None = None,
    ) -> None:
        if primary_symbols is not None:
            self.PRIMARY_SYMBOLS = primary_symbols

    def validate(
        self,
        raw: list[dict[str, Any]],
        last_known: dict[str, float] | None = None,
    ) -> GoldValidationResult:
        """Validate raw gold price data.

        Args:
            raw: Raw price records from BrsApi.
            last_known: Map of symbol → last known price for jump detection.

        Returns:
            GoldValidationResult with clean rows, dropped count, and suspicious count.
        """
        result = GoldValidationResult()
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

            # Price reasonableness check (gold prices should be > 1000 IRR)
            if price < 1000:
                row["quality_flag"] = 2  # suspicious
                result.suspicious_count += 1
                logger.warning(
                    "Gold suspicious low price: %s = %.0f (expected > 1000)",
                    symbol,
                    price,
                )
            else:
                row["quality_flag"] = 0

            result.clean_rows.append(row)

        if result.suspicious_count > 0:
            logger.info(
                "Gold validation: %d clean, %d suspicious, %d dropped",
                len(result.clean_rows),
                result.suspicious_count,
                result.dropped_count,
            )

        return result

    def normalize(self, clean_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize validated gold rows into a consistent schema.

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
                    # Gold-specific
                    "quality_flag": quality_flag,
                    "market": "gold",
                }
            )

        return normalized

    def is_primary(self, symbol: str) -> bool:
        """Check if a symbol is a primary (signal-worthy) gold symbol."""
        return symbol in self.PRIMARY_SYMBOLS

    def is_global_feature(self, symbol: str) -> bool:
        """Check if a symbol is a global feature (e.g. XAUUSD)."""
        return symbol in self.GLOBAL_FEATURES

    def symbol_label(self, symbol: str) -> str:
        """Return a human-readable label for the symbol."""
        labels = {
            "IR_GOLD_18K": "طلای ۱۸ عیار",
            "IR_GOLD_24K": "طلای ۲۴ عیار",
            "IR_GOLD_MELTED": "طلای آب‌شده نقدی",
            "IR_COIN_EMAMI": "سکه امامی",
            "IR_COIN_BAHAR": "سکه بهار آزادی",
            "IR_COIN_HALF": "نیم سکه",
            "IR_COIN_QUARTER": "ربع سکه",
            "IR_COIN_1G": "سکه یک گرمی",
            "XAUUSD": "انس طلا جهانی",
        }
        return labels.get(symbol, symbol)


# ── Gold Symbol Constants ──────────────────────────────────────────────

# All gold symbols tracked for signal generation
GOLD_TRACKED_SYMBOLS: list[str] = [
    "IR_GOLD_18K",
    "IR_GOLD_24K",
    "IR_GOLD_MELTED",
    "IR_COIN_EMAMI",
    "IR_COIN_BAHAR",
    "IR_COIN_HALF",
    "IR_COIN_QUARTER",
    "IR_COIN_1G",
    "XAUUSD",
]

# Quality gate thresholds for gold data readiness
GOLD_MIN_ROWS = 200  # Minimum rows in last 24h for signal readiness
GOLD_MAX_STALENESS_MIN = 15  # Maximum minutes since last sync before data is stale
GOLD_MAX_SUSPECT_RATIO = 0.05  # Maximum ratio of suspicious rows
