"""Signal Journal — تاریخچهٔ سیگنال‌های خروجی scorer + ابطال (revoke).

هر بار که compute_score() صدا زده می‌شود، نتیجه می‌تواند با
``append_journal()`` در journal ذخیره شود. این تاریخچه برای audit،
بازگردانی اشتباه و بررسی روند تغییر تصمیم مفید است.

ذخیره‌سازی: Redis (key ثابت، TTL 7 روز، حداکثر ۱۰۰ ورودی). DB نیاز ندارد.

ابطال (revoke): اگر داده‌ای که سیگنال از آن ساخته شده نادرست تشخیص داده
شود، مالک می‌تواند آن ورودی را revoke کند. ورودی revoke‌شده هنوز در journal
نمایش داده می‌شود ولی با علامت ``revoked=True`` و reason مشخص.

الگوی injectable cache از WS3/WS5 پیروی می‌کند.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from core.time import utc_now_naive
from .scorer import ScoreResult

logger = logging.getLogger(__name__)

REDIS_KEY_JOURNAL = "golddesk:signal:journal"
JOURNAL_MAX_ENTRIES: int = 100
JOURNAL_TTL_DAYS: int = 7


@dataclass(frozen=True)
class SignalJournalEntry:
    """یک رکورد در journal سیگنال‌ها.

    ``components_summary`` فقط امتیازها را نگه می‌دارد (نه دلیل‌ها)
    تا حجم Redis کم بماند.
    """

    entry_id: str
    scored_at: str          # ISO8601 UTC
    decision: str           # GREEN | YELLOW | RED | NO_DATA
    total: int
    available_weight: int
    hard_stop_active: bool
    hard_stop_reason: str | None
    components_summary: dict[str, int]  # component → score value
    revoked: bool = False
    revoke_reason: str | None = None
    revoked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_score_result(cls, result: ScoreResult) -> "SignalJournalEntry":
        """ScoreResult → SignalJournalEntry با UUID جدید."""
        return cls(
            entry_id=str(uuid.uuid4()),
            scored_at=utc_now_naive().isoformat() + "Z",
            decision=result.decision,
            total=result.total,
            available_weight=result.available_weight,
            hard_stop_active=result.hard_stop_active,
            hard_stop_reason=result.hard_stop_reason,
            components_summary={k: c.value for k, c in result.components.items()},
        )

    def as_revoked(self, reason: str) -> "SignalJournalEntry":
        """برمی‌گرداند نمونهٔ جدید با ``revoked=True``؛ نمونهٔ اصلی تغییر نمی‌کند."""
        return SignalJournalEntry(
            entry_id=self.entry_id,
            scored_at=self.scored_at,
            decision=self.decision,
            total=self.total,
            available_weight=self.available_weight,
            hard_stop_active=self.hard_stop_active,
            hard_stop_reason=self.hard_stop_reason,
            components_summary=self.components_summary,
            revoked=True,
            revoke_reason=reason,
            revoked_at=utc_now_naive().isoformat() + "Z",
        )


def _deserialize(raw: str) -> list[SignalJournalEntry]:
    """JSON ذخیره‌شده را به لیست SignalJournalEntry تبدیل می‌کند."""
    try:
        rows = json.loads(raw)
        return [SignalJournalEntry(**r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal journal deserialize failed: %s", exc)
        return []


async def append_journal(
    entry: SignalJournalEntry,
    cache=None,
) -> None:
    """ورودی جدید را به ابتدای journal اضافه می‌کند.

    اگر تعداد از ``JOURNAL_MAX_ENTRIES`` بیشتر شد، قدیمی‌ترین‌ها حذف می‌شوند.
    خطا را می‌بلعد تا مسیر اصلی (snapshot) قطع نشود.
    """
    from core.cache import get_cache

    _cache = cache if cache is not None else get_cache()
    try:
        raw = await _cache.get(REDIS_KEY_JOURNAL)
        existing: list[SignalJournalEntry] = _deserialize(raw) if raw else []
        entries = [entry] + existing  # جدیدترین اول
        entries = entries[:JOURNAL_MAX_ENTRIES]
        payload = json.dumps([e.to_dict() for e in entries], ensure_ascii=False)
        await _cache.set(
            REDIS_KEY_JOURNAL,
            payload,
            ttl=JOURNAL_TTL_DAYS * 86_400,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal journal append failed: %s", exc)


async def revoke_signal(
    entry_id: str,
    reason: str,
    cache=None,
) -> bool:
    """ورودی با ``entry_id`` مشخص را revoke می‌کند.

    Returns:
        True اگر ورودی پیدا و revoke شد؛ False اگر پیدا نشد.
    """
    from core.cache import get_cache

    _cache = cache if cache is not None else get_cache()
    try:
        raw = await _cache.get(REDIS_KEY_JOURNAL)
        if not raw:
            return False
        entries = _deserialize(raw)
        updated = []
        found = False
        for e in entries:
            if e.entry_id == entry_id:
                updated.append(e.as_revoked(reason))
                found = True
            else:
                updated.append(e)
        if not found:
            return False
        payload = json.dumps([e.to_dict() for e in updated], ensure_ascii=False)
        await _cache.set(REDIS_KEY_JOURNAL, payload, ttl=JOURNAL_TTL_DAYS * 86_400)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal journal revoke failed: %s", exc)
        return False


async def list_journal(
    cache=None,
    limit: int = 50,
) -> list[SignalJournalEntry]:
    """ورودی‌های اخیر journal را برمی‌گرداند (جدیدترین اول).

    Returns:
        لیستی از ``SignalJournalEntry``، خالی اگر journal وجود نداشته باشد.
    """
    from core.cache import get_cache

    _cache = cache if cache is not None else get_cache()
    try:
        raw = await _cache.get(REDIS_KEY_JOURNAL)
        if not raw:
            return []
        return _deserialize(raw)[:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal journal list failed: %s", exc)
        return []
