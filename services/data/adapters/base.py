"""Assistant 4 — Market Data source layer.

Uniform adapter contract.  Every adapter normalizes a raw source payload into a
:class:`MarketRecord` carrying the mandatory fields ``value``, ``unit``,
``asOf`` (ISO-8601 with timezone), ``source`` and ``quality``.

Adapters are **pure normalizers**: no network connections, no credential
storage, no invented prices, no formulas (bubble/score are owned by Assistant 1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

# Iran Standard Time (IRST = UTC+03:30).  Iran no longer observes DST.
IR_TZ = timezone(timedelta(hours=3, minutes=30))

# Keys that must never leave an adapter (logs / records / API responses).
SECRET_KEYS = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "cookie",
        "session",
        "sessionid",
        "password",
        "secret",
        "api_key",
        "apikey",
        "client_secret",
        "authorization",
        "set-cookie",
    }
)

DEFAULT_TTL_SECONDS = 900  # 15 min LIVE window (phase-3 `data_stale` gate config)

QUALITY_ORDER = {
    "LIVE": 4,
    "DELAYED": 3,
    "SAMPLE": 2,
    "EDUCATIONAL": 1,
    "UNAVAILABLE": 0,
}


class Quality(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    SAMPLE = "SAMPLE"
    EDUCATIONAL = "EDUCATIONAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class MarketRecord:
    """Canonical output of every source adapter."""

    symbol: str | None
    value: float | None
    unit: str | None
    as_of: str | None
    source: str
    quality: Quality
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": self.symbol,
            "value": self.value,
            "unit": self.unit,
            "asOf": self.as_of,
            "source": self.source,
            "quality": self.quality.value,
            "metadata": dict(self.metadata),
        }
        return payload


class BaseAdapter(ABC):
    """Base class for source adapters.

    Subclasses set ``source`` (static source tag) and implement
    ``extract(raw)`` returning the source-specific fields; normalization of
    asOf/quality/secrets/freshness is handled here.
    """

    source: str = "unknown"
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    # ------------------------------------------------------------------ secrets
    @staticmethod
    def _strip_secrets(raw: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in raw.items():
            if key.lower() in SECRET_KEYS:
                continue
            if isinstance(value, dict):
                value = BaseAdapter._strip_secrets(value)
            cleaned[key] = value
        return cleaned

    # ------------------------------------------------------------------ time
    @staticmethod
    def _to_iso(value: Any) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            dt = value if value.tzinfo else value.replace(tzinfo=IR_TZ)
            return dt.astimezone(IR_TZ).isoformat()
        if isinstance(value, str):
            s = value.strip()
            if not s or s == "—not set—":
                return None
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IR_TZ)
            return dt.astimezone(IR_TZ).isoformat()
        return None

    @staticmethod
    def _age_seconds(as_of: str | None, now: datetime) -> int | None:
        if as_of is None:
            return None
        try:
            dt = datetime.fromisoformat(as_of)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IR_TZ)
        delta = now.astimezone(IR_TZ) - dt.astimezone(IR_TZ)
        return int(delta.total_seconds())

    # ------------------------------------------------------------------ quality
    @classmethod
    def _freshness(cls, age: int | None, ttl: int | None) -> tuple[str | None, bool]:
        if age is None:
            return ("unknown", False)
        limit = ttl or cls.ttl_seconds
        stale = age > limit
        return ("stale" if stale else "fresh", stale)

    @classmethod
    def _resolve_quality(
        cls,
        raw_quality: str | None,
        age: int | None,
        now: datetime,
    ) -> tuple[Quality, str | None, bool]:
        """Return (quality, as_of, stale_flag).

        * SAMPLE / EDUCATIONAL are **never** promoted to LIVE.
        * LIVE older than ttl → DELAYED (+ staleFlag).
        * Missing/unparseable source time → UNAVAILABLE.
        """
        ttl = cls.ttl_seconds
        freshness, stale = cls._freshness(age, ttl)
        source_q = Quality(raw_quality) if raw_quality in {q.value for q in Quality} else None

        if source_q in {Quality.SAMPLE, Quality.EDUCATIONAL}:
            return source_q, None, stale  # keep badge; never upgrade

        if source_q is None or age is None:
            return Quality.UNAVAILABLE, None, stale

        if source_q == Quality.LIVE and stale:
            return Quality.DELAYED, None, stale

        return source_q, None, stale

    # ------------------------------------------------------------------ template
    @abstractmethod
    def extract(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Source-specific field extraction (no quality/time policy here)."""

    def normalize(self, raw: dict[str, Any], now: datetime | None = None) -> MarketRecord:
        if now is None:
            now = datetime.now(IR_TZ)
        clean = self._strip_secrets(raw or {})
        extracted = self.extract(clean) or {}

        as_of = self._to_iso(extracted.get("asOf") or clean.get("asOf"))
        age = self._age_seconds(as_of, now)
        quality, _asof_unused, stale = self._resolve_quality(
            extracted.get("quality") or clean.get("quality"),
            age,
            now,
        )

        freshness, _ = self._freshness(age, self.ttl_seconds)

        metadata: dict[str, Any] = {
            "ageSeconds": age,
            "freshness": freshness,
            "staleFlag": bool(stale),
        }
        # Carry source-specific read-only metadata (settlement, expiry, ...)
        for key in ("settlement", "expiry", "distance_from_spot_pct", "risks_simple", "labels", "note", "reason"):
            if key in extracted:
                metadata[key] = extracted[key]

        # Source tag: explicit raw source wins; adapter tag only when payload
        # carries data; a fully empty/raw-missing payload is "unknown".
        source = extracted.get("source")
        if source is None:
            source = self.source if (raw or clean) else "unknown"

        return MarketRecord(
            symbol=extracted.get("symbol"),
            value=extracted.get("value"),
            unit=extracted.get("unit"),
            as_of=as_of,
            source=source,
            quality=quality,
            metadata=metadata,
        )

    def freshness_mark(self, record: MarketRecord, now: datetime | None = None) -> dict[str, Any]:
        """Standalone staleness marker for Assistant 1's ``data_stale`` gate."""
        if now is None:
            now = datetime.now(IR_TZ)
        age = self._age_seconds(record.as_of, now)
        freshness, stale = self._freshness(age, self.ttl_seconds)
        return {"ageSeconds": age, "freshness": freshness, "staleFlag": bool(stale)}
