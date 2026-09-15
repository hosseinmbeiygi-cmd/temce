"""Quota-governed BrsApi client for the ``AllSymbols.php`` market scanner.

Reuse-first: transport, retry/backoff, circuit breaking, the browser
User-Agent and the persistent budget governor all already live in
:class:`brsapi.client.BrsApiClient`.  This module subclasses that client to
add only what the ingestion scope needs:

* the full browser header set the upstream site expects,
* the ingestion quota profile (300 req / 5 min, 10,000 req / day), and
* an AllSymbols-specific fetch that returns parser-ready raw rows.

No technical indicator is computed here — ingestion fetches and validates
raw data only.
"""

from __future__ import annotations

from typing import Any

from brsapi.client import BrsApiClient
from brsapi.config import BrsApiEndpoints
from brsapi.parsers.tsetmc import TsetmcParser
from core.logging import get_logger
from core.result import Result

from .quotas import (
    DEFAULT_QUOTA_PROFILE,
    IngestionQuotaTracker,
    QuotaProfile,
    build_ingestion_governor,
    build_ingestion_limiter,
)

logger = get_logger(__name__)

# Standard desktop-browser header set.  BrsApiClient already sets the
# User-Agent; the rest are added after the httpx client is built so we do not
# have to touch the shared client.
BROWSER_HEADERS: dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://brsapi.ir/",
}

# The AllSymbols endpoint supports a ``type`` param (1 = main market board).
DEFAULT_ALL_SYMBOLS_TYPE = "1"


class BrsApiIngestionClient(BrsApiClient):
    """BrsApi client bound to the ingestion quota profile.

    The limiter and the persistent governor are created together so the
    profile is enforced consistently across the in-process window and the
    Redis/file-backed daily counter.
    """

    def __init__(
        self,
        *,
        profile: QuotaProfile = DEFAULT_QUOTA_PROFILE,
        limiter: Any | None = None,
        governor: Any | None = None,
        extra_headers: dict[str, str] | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        proxy_url: str | None = None,
    ) -> None:
        active_limiter = limiter or build_ingestion_limiter(profile)
        active_governor = governor or build_ingestion_governor(
            profile,
            limiter=active_limiter,
        )
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            rate_limiter=active_limiter,
            budget_governor=active_governor,
            proxy_url=proxy_url,
        )
        self._profile = profile
        self._extra_headers = dict(extra_headers or {})
        self._quota = IngestionQuotaTracker(active_governor, profile=profile)

    @property
    def profile(self) -> QuotaProfile:
        return self._profile

    @property
    def quota(self) -> IngestionQuotaTracker:
        return self._quota

    async def start(self) -> None:
        """Start the HTTP client and install the browser header set."""
        await super().start()
        client = getattr(self, "_client", None)
        if client is not None:
            client.headers.update(BROWSER_HEADERS)
            if self._extra_headers:
                client.headers.update(self._extra_headers)
        logger.info(
            "Ingestion client started (profile=%s daily=%d five_min=%d)",
            self._profile.label,
            self._profile.daily_limit,
            self._profile.five_min_limit,
        )

    async def fetch_all_symbols(
        self,
        *,
        symbol_type: str = DEFAULT_ALL_SYMBOLS_TYPE,
    ) -> Result[list[dict[str, Any]]]:
        """Fetch and parse the whole market in a single request.

        Returns the flat, ORM-ready row dicts produced by
        :meth:`brsapi.parsers.tsetmc.TsetmcParser.parse_all_symbols`.
        """
        response = await self.fetch(BrsApiEndpoints.ALL_SYMBOLS, {"type": symbol_type})
        if not response.success:
            return Result.fail(response.error or "AllSymbols fetch failed")

        payload = response.value.data if response.value is not None else None
        rows = TsetmcParser.parse_all_symbols(payload)
        if not rows:
            preview = type(payload).__name__
            logger.warning("AllSymbols returned no usable rows (payload=%s)", preview)
            return Result.fail(f"AllSymbols payload unusable (got {preview})")

        return Result.ok(rows)

    async def health(self) -> dict[str, Any]:
        """Operational health: key readiness, quota headroom and profile drift."""
        healthy = False
        try:
            snapshot = await self._quota.snapshot()
            quota_payload = snapshot.as_dict()
            healthy = not snapshot.blocked and not snapshot.exhausted
        except Exception as exc:  # noqa: BLE001 - health must never raise
            logger.warning("Quota snapshot failed: %s", exc)
            quota_payload = {"error": str(exc)}

        return {
            "client_ready": self.is_ready,
            "healthy": healthy,
            "profile_assessment": self._quota.assessment().as_dict(),
            "quota": quota_payload,
        }
