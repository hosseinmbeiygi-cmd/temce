"""
BrsApi.ir HTTP Client
=====================

Async HTTP client with:
- Connection pooling via ``httpx.AsyncClient``
- Exponential backoff retry
- Circuit breaker (reuses ``core.circuit_breaker.CircuitBreaker``)
- Rate limiting (token bucket per endpoint category)
- Redis cache integration
- Raw payload capture for audit
- Comprehensive error classification
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from logging import getLogger
from typing import Any, Literal, TypeVar

import httpx
from httpx import AsyncHTTPTransport, Limits

# Fix stale Windows registry proxy BEFORE any HTTP connections
from core.fix_network import fix_network as _fix_network

_fix_network()

from brsapi.budget import (
    BrsApiBudgetGovernor,
    BudgetBlockedError,
    BudgetSoftRejectError,
    get_budget_governor,
)
from brsapi.config import BrsApiEndpoints, EndpointCategory, EndpointConfig
from brsapi.config import settings as brsapi_settings
from brsapi.rate_limiter import RateLimiter, RateLimitExhaustedError, get_rate_limiter
from core.resilience.circuit_breaker import CircuitBreaker
from core.result import Result

T = TypeVar("T")
logger = getLogger(__name__)

_SENSITIVE_QUERY_RE = re.compile(
    r"([?&](?:key|api_key|token|secret|password)=)[^&\s]+",
    re.IGNORECASE,
)


def _redact_sensitive_text(value: str) -> str:
    """Prevent credentials embedded in HTTP error URLs from being logged."""
    return _SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", value)


# ──────────────────────────────────────────────
#  Error taxonomy
# ──────────────────────────────────────────────


# Machine-readable failure reasons carried by ``Result.error_code``. Callers
# branch on these instead of matching words in the human-readable message.
BrsApiErrorCode = Literal[
    "malformed",  # body was HTML or invalid JSON
    "provider_blocked",  # 302 heavy-file redirect / block cooldown
    "quota_exhausted",  # daily budget or rate limit spent
    "budget_soft_limit",  # soft ceiling rejected a non-critical call
    "timeout",  # request timed out after retries
    "network_error",  # connection/protocol failure
    "http_error",  # explicit non-200 HTTP status
    "retries_exhausted",  # retryable statuses exhausted
    "circuit_open",  # breaker tripped; the request was never sent
    "disabled",  # BRSAPI_ENABLED=false
    "not_started",  # client used before ``start()``
    "source_error",  # anything unclassified
]

# BrsApi never serves a 3xx we should follow: the anti-abuse redirect points at
# a multi-gigabyte file. Every redirect is treated as a block signal, without
# arming the retry loop.
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Transient failures: retry with backoff / Retry-After.
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
# The account's quota is spent — retrying only burns more of it.
_QUOTA_STATUSES = frozenset({402})
# Credential/plan-level rejection — retrying cannot fix it.
_BLOCKED_STATUSES = frozenset({401, 403, 451})


class BrsApiMalformedResponseError(Exception):
    """The HTTP body was not the JSON document BrsApi promised.

    Raised for an HTML page (the provider's suspend/block page) or a body that
    is not valid JSON, so a caller can tell "the provider answered garbage"
    apart from "the provider answered with no rows".
    """

    code: BrsApiErrorCode = "malformed"


class BrsApiSourceError(Exception):
    """BrsApi answered HTTP 200 with a provider-level error envelope.

    Example: ``{"code_http": 402, "successful": false, "message_error":
    "quota exhausted"}`` — a transport success carrying an application error
    that must never be stored as data.
    """

    code: BrsApiErrorCode = "provider_blocked"

    def __init__(self, message: str, *, code: BrsApiErrorCode | None = None) -> None:
        if code is not None:
            self.code = code
        super().__init__(message)


_HTML_CONTENT_TYPE_MARKERS = ("text/html", "application/xhtml")
_HTML_BODY_PREFIXES = ("<!doctype html", "<html", "<?xml", "<!--")


def _looks_like_html(content_type: str, text: str) -> bool:
    """True when the body is an HTML/XML document rather than JSON."""
    lowered_type = (content_type or "").lower()
    if any(marker in lowered_type for marker in _HTML_CONTENT_TYPE_MARKERS):
        return True
    head = text.lstrip()[:200].lower()
    return head.startswith(_HTML_BODY_PREFIXES)


def _raise_for_provider_error(data: dict[str, Any]) -> None:
    """Raise :class:`BrsApiSourceError` for an in-band provider error envelope."""
    if data.get("successful") is not False:
        return
    raw_code = data.get("code_http")
    message = (
        data.get("message_error")
        or data.get("message")
        or data.get("status")
        or "provider error"
    )
    prefix = (
        f"BrsApi provider error (HTTP {raw_code})"
        if raw_code is not None
        else "BrsApi provider error"
    )
    try:
        http_code = int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        http_code = None
    # 402 (payment required) and 429 (too many requests) mean the account's
    # quota is spent; other in-band errors are provider-side blocks.
    error_code: BrsApiErrorCode = (
        "quota_exhausted" if http_code in (402, 429) else "provider_blocked"
    )
    raise BrsApiSourceError(f"{prefix}: {message}", code=error_code)


# ──────────────────────────────────────────────
#  Response envelope
# ──────────────────────────────────────────────


@dataclass
class BrsApiResponse:
    """Normalised response from a BrsApi endpoint call."""
    endpoint: str
    status_code: int
    data: Any                                        # Parsed JSON payload
    raw_bytes: bytes | None = None                   # Raw HTTP body (for audit)
    fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    # Naive UTC timestamp of when the body arrived; sync stamps stored rows and
    # the raw-payload log with this instead of a per-parser ``now()``.
    received_at: datetime | None = None
    elapsed_ms: float = 0.0
    error: str | None = None
    success: bool = True

    @property
    def is_empty(self) -> bool:
        """Check if the response contains no meaningful data."""
        if self.data is None:
            return True
        if isinstance(self.data, dict):
            # BrsApi sometimes returns {"code_http": 200, "successful": false, "status": "no_data"}
            if self.data.get("status") == "no_data":
                return True
            return len(self.data) == 0
        if isinstance(self.data, list):
            return len(self.data) == 0
        return False


# ──────────────────────────────────────────────
#  Client
# ──────────────────────────────────────────────


class BrsApiClient:
    """
    Async HTTP client for BrsApi.ir.

    Usage::

        client = BrsApiClient()
        await client.start()

        # Fetch all symbols
        result = await client.fetch(BrsApiEndpoints.ALL_SYMBOLS)

        # Fetch symbol detail
        result = await client.fetch(
            BrsApiEndpoints.SYMBOL_DETAIL,
            params={"l18": "فملی"},
        )

        await client.stop()
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        rate_limiter: RateLimiter | None = None,
        budget_governor: BrsApiBudgetGovernor | None = None,
        proxy_url: str | None = None,
    ) -> None:
        self._api_key = api_key or brsapi_settings.api_key
        self._base_url = (base_url or brsapi_settings.base_url).rstrip("/")
        self._timeout = brsapi_settings.request_timeout
        self._max_retries = brsapi_settings.max_retries
        self._backoff_base = brsapi_settings.retry_backoff_base
        self._backoff_max = brsapi_settings.retry_max_delay
        self._pool_size = brsapi_settings.connection_pool_size
        self._raw_sink_enabled = brsapi_settings.raw_payload_sink_enabled
        self._proxy_url = proxy_url or brsapi_settings.proxy_url
        self._verify_ssl = brsapi_settings.verify_ssl

        self._rate_limiter = rate_limiter or get_rate_limiter()
        if budget_governor is not None:
            self._governor = budget_governor
        elif rate_limiter is None:
            # Production path: shared persistent governor (Redis/file backend)
            # so restarts and replicas never spend the same daily budget twice.
            self._governor = get_budget_governor()
        else:
            # Test/custom-limiter path: in-memory governor so unit tests never
            # touch real Redis or the shared state file.
            self._governor = BrsApiBudgetGovernor(rate_limiter=self._rate_limiter, persist=False)
        self._client: httpx.AsyncClient | None = None
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # Pre-configure rate limiters per category
        self._configure_rate_limits()

    # ── Lifecycle ────────────────────────────────

    async def start(self) -> None:
        """Initialise the HTTP client session."""
        if self._client is not None:
            return
        limits = Limits(
            max_connections=self._pool_size,
            max_keepalive_connections=self._pool_size,
        )
        client_kwargs: dict[str, Any] = {
            "limits": limits,
            "timeout": httpx.Timeout(self._timeout),
            "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"},
        }
        if self._proxy_url:
            # httpx ≥0.28: proxy via a transport mount
            proxy_transport = AsyncHTTPTransport(
                verify=self._verify_ssl,
                proxy=self._proxy_url,
            )
            client_kwargs["mounts"] = {"all://": proxy_transport}
            logger.info("Using proxy: %s", self._proxy_url)
        else:
            # Explicit direct connection — httpx ≥0.28 removed proxies=.
            # On Windows, urllib may pick up a stale system proxy from the
            # registry.  An explicit transport with proxy=None forces direct.
            transport = AsyncHTTPTransport(verify=self._verify_ssl, proxy=None)
            client_kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**client_kwargs)
        logger.info("BrsApiClient started – base=%s pool=%d", self._base_url, self._pool_size)

    async def stop(self) -> None:
        """Close the HTTP client session."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("BrsApiClient stopped")

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    # ── Public fetch ─────────────────────────────

    async def fetch(
        self,
        endpoint: EndpointConfig,
        params: dict[str, str] | None = None,
        category_override: str | None = None,
    ) -> Result[BrsApiResponse]:
        """
        Fetch data from a BrsApi endpoint.

        Args:
            endpoint: The endpoint config describing path and limits.
            params: Extra URL parameters merged with defaults + API key.
            category_override: Override the rate-limiter key (defaults to
                               ``endpoint.category``).

        Returns:
            A ``Result`` wrapping ``BrsApiResponse``.
        """
        if not brsapi_settings.enabled:
            return Result.fail(
                "BrsApi disabled via BRSAPI_ENABLED=false — DB-only mode "
                "(no live API calls while the key is blocked/quota exhausted)",
                code="disabled",
            )
        if self._client is None:
            return Result.fail(
                "BrsApiClient not started – call .start() first",
                code="not_started",
            )

        url = f"{self._base_url}{endpoint.path}"
        request_params = self._build_params(endpoint, params)
        category = category_override or endpoint.category.value

        # Fail fast when the global budget is exhausted or the key is in the
        # post-302 cooldown. The budget governor checks the PERSISTED counters
        # (shared across processes/restarts) so a restarted worker or a second
        # replica cannot spend the same daily budget twice.
        if brsapi_settings.fail_fast_on_daily_exhausted:
            try:
                await self._governor.check_allowed(
                    category, endpoint.path, critical=endpoint.critical,
                )
            except BudgetSoftRejectError as exc:
                logger.warning(
                    "BrsApi budget soft ceiling — non-critical request for %s rejected",
                    endpoint.path,
                )
                return Result.fail(str(exc), code="budget_soft_limit")
            except RateLimitExhaustedError as exc:
                logger.warning("BrsApi budget exhausted — request rejected fast")
                return Result.fail(str(exc), code="quota_exhausted")
            except BudgetBlockedError as exc:
                logger.warning("BrsApi key in 302-cooldown — request rejected fast")
                return Result.fail(str(exc), code="provider_blocked")

        # Circuit breaker for this endpoint path. ``_do_fetch`` turns expected
        # failures into ``Result`` values instead of raising, so the outcome is
        # fed back explicitly — otherwise the breaker would see every call as a
        # success and never open while a provider is down.
        cb = self._circuit_breaker(endpoint.path)
        if cb.state == "open":
            return Result.fail(
                f"Circuit breaker open for {endpoint.path} — the provider kept "
                "failing; retry after the recovery window",
                code="circuit_open",
            )

        try:
            result = await self._do_fetch(
                url,
                request_params,
                category,
                endpoint,
            )
        except Exception as exc:
            cb.record_failure()
            safe_error = _redact_sensitive_text(str(exc))
            logger.warning("BrsApi fetch failed [%s]: %s", endpoint.path, safe_error)
            # Typed errors (malformed body, provider block) carry their own code;
            # anything else is an unclassified source failure.
            return Result.fail(
                safe_error, code=getattr(exc, "code", "source_error")
            )

        if result.success:
            cb.record_success()
        else:
            cb.record_failure()
        return result

    # ── Internal fetch logic ─────────────────────

    async def _do_fetch(
        self,
        url: str,
        params: dict[str, str],
        category: str,
        endpoint: EndpointConfig,
    ) -> Result[BrsApiResponse]:
        assert self._client is not None

        start = asyncio.get_event_loop().time()

        # Rate limit through the budget governor (persisted daily cap + shared
        # 5-min window + block cooldown) layered over the in-process limiter.
        try:
            await self._governor.acquire(
                category,
                endpoint=endpoint.path,
                fail_fast=brsapi_settings.fail_fast_on_daily_exhausted,
                critical=endpoint.critical,
            )
        except (RateLimitExhaustedError, BudgetBlockedError) as exc:
            code: BrsApiErrorCode = (
                "provider_blocked"
                if isinstance(exc, BudgetBlockedError)
                else "quota_exhausted"
            )
            return Result.fail(str(exc), code=code)

        # HTTP request with retry
        last_error: str | None = None
        raw_bytes: bytes | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.get(url, params=params)
                elapsed = (asyncio.get_event_loop().time() - start) * 1000
                received_at = datetime.now(UTC).replace(microsecond=0, tzinfo=None)

                raw_bytes = resp.content

                if resp.status_code == 200:
                    data = self._parse_response(
                        resp.content, resp.headers.get("content-type", "")
                    )
                    # Best effort — a successful response may clear a stale
                    # block after the cooldown; never fail the request on it.
                    try:
                        await self._governor.report_ok()
                    except Exception:  # noqa: BLE001
                        logger.debug("budget governor report_ok failed", exc_info=True)
                    brs_resp = BrsApiResponse(
                        endpoint=endpoint.path,
                        status_code=200,
                        data=data,
                        raw_bytes=raw_bytes if self._raw_sink_enabled else None,
                        received_at=received_at,
                        elapsed_ms=elapsed,
                        success=True,
                    )
                    return Result.ok(brs_resp)

                if resp.status_code in _REDIRECT_STATUSES:
                    # BrsApi anti-abuse: when the account's request count is
                    # above the plan threshold, EVERY live call is redirected
                    # to a massive file (e.g. a Windows ISO). Never follow a
                    # redirect (httpx default), never retry — just fail fast
                    # with a clear message so jobs don't hammer a still-
                    # exhausted account.
                    location = resp.headers.get("Location", "?")
                    logger.warning(
                        "BrsApi redirect — HTTP %d to %r (server-side usage "
                        "above plan threshold?)",
                        resp.status_code,
                        location,
                    )
                    # Arm the governor cooldown so subsequent calls reject fast
                    # instead of hammering the still-over-quota account.
                    try:
                        await self._governor.report_302(location)
                    except Exception:  # noqa: BLE001
                        logger.debug("budget governor report_302 failed", exc_info=True)
                    return Result.fail(
                        f"BrsApi quota exceeded (HTTP {resp.status_code} → "
                        f"{location}). Server-side usage is above the plan "
                        "threshold — keep DB-only mode (BRSAPI_ENABLED=false) "
                        "until the counter resets or the plan is upgraded.",
                        code="provider_blocked",
                    )

                if resp.status_code in _QUOTA_STATUSES:
                    # 402 Payment Required: the plan allowance is spent. A
                    # retry cannot pay for it and would only burn budget.
                    return Result.fail(
                        f"HTTP {resp.status_code}: payment required — the BrsApi "
                        "plan allowance for this period is exhausted",
                        code="quota_exhausted",
                    )

                if resp.status_code in _BLOCKED_STATUSES:
                    # 401/403/451: the key is rejected or the source is blocked
                    # for legal reasons. Retrying cannot fix either.
                    return Result.fail(
                        f"HTTP {resp.status_code}: {resp.text[:200]}",
                        code="provider_blocked",
                    )

                if resp.status_code in _RETRYABLE_STATUSES:
                    # Rate limit / gateway hiccup / service unavailable → retry.
                    # BrsApi's nginx intermittently returns 502 Bad Gateway for a
                    # few seconds; without this the whole backfill aborts.
                    retry_after = self._parse_retry_after(resp)
                    last_error = f"HTTP {resp.status_code} – retry after {retry_after}s"
                    if attempt < self._max_retries:
                        logger.warning(
                            "%s (attempt %d/%d) - retrying in %.1fs",
                            last_error,
                            attempt + 1,
                            self._max_retries + 1,
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    # Last attempt already spent - sleeping here would only stall
                    # the caller before the same failure is returned.
                    logger.warning(
                        "%s (attempt %d/%d) - no retries left",
                        last_error,
                        attempt + 1,
                        self._max_retries + 1,
                    )
                    break

                # Other HTTP error
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return Result.fail(last_error, code="http_error")

            except httpx.TimeoutException:
                last_error = "timeout"
                if attempt < self._max_retries:
                    delay = min(self._backoff_base ** (attempt + 1), self._backoff_max)
                    logger.warning(
                        "Timeout (attempt %d/%d) – retrying in %.1fs",
                        attempt + 1,
                        self._max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return Result.fail(
                    f"Request timeout after {self._max_retries} retries",
                    code="timeout",
                )

            except httpx.RequestError as exc:
                last_error = _redact_sensitive_text(str(exc))
                if attempt < self._max_retries:
                    delay = min(self._backoff_base ** (attempt + 1), self._backoff_max)
                    logger.warning(
                        "RequestError (attempt %d/%d): %s – retrying in %.1fs",
                        attempt + 1,
                        self._max_retries + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return Result.fail(
                    f"RequestError: {_redact_sensitive_text(str(exc))}",
                    code="network_error",
                )

        return Result.fail(
            f"All retries exhausted: {last_error}", code="retries_exhausted"
        )

    # ── Build URL parameters ─────────────────────

    def _build_params(
        self,
        endpoint: EndpointConfig,
        extra: dict[str, str] | None,
    ) -> dict[str, str]:
        params = {"key": self._api_key}
        # Defaults
        params.update(endpoint.default_params)
        # Override with explicit params
        if extra:
            params.update(extra)
        return params

    # ── Response parsing ─────────────────────────

    def _parse_response(self, content: bytes, content_type: str = "") -> Any:
        """Decode one HTTP body, rejecting non-JSON and provider error envelopes.

        A body we cannot read is an error, never data: returning ``[]`` or a
        ``{"_raw_text": ...}`` stub let a blocked or garbage response look like
        a healthy empty sync.
        """
        text = content.decode("utf-8", errors="replace")
        if _looks_like_html(content_type, text):
            raise BrsApiMalformedResponseError(
                "BrsApi returned an HTML page instead of JSON "
                "(suspend/block page)"
            )
        try:
            data = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrsApiMalformedResponseError(
                f"BrsApi returned invalid JSON: {exc}"
            ) from exc
        if isinstance(data, dict):
            _raise_for_provider_error(data)
        return data

    def _parse_retry_after(self, resp: httpx.Response) -> float:
        header = resp.headers.get("Retry-After", "5")
        try:
            return float(header)
        except ValueError:
            return 5.0

    # ── Circuit breaker ──────────────────────────

    def _circuit_breaker(self, path: str) -> CircuitBreaker:
        if path not in self._circuit_breakers:
            self._circuit_breakers[path] = CircuitBreaker(
                name=f"brsapi:{path}",
                failure_threshold=5,
                recovery_timeout=30.0,
            )
        return self._circuit_breakers[path]

    # ── Rate-limit configuration ─────────────────

    def _configure_rate_limits(self) -> None:
        """Seed the rate limiter with per-category defaults."""
        cfg = brsapi_settings
        limits: dict[str, int] = {
            EndpointCategory.TSETMC.value: cfg.rate_limit_tsetmc or 30,
            # Config default is 12 (matching CODAL_ANNOUNCEMENT's 2/10s).
            EndpointCategory.CODAL.value: cfg.rate_limit_codal or 12,
            EndpointCategory.IME.value: cfg.rate_limit_ime or 15,
            EndpointCategory.COMMODITY.value: cfg.rate_limit_commodity or 15,
            EndpointCategory.CRYPTOCURRENCY.value: cfg.rate_limit_crypto or 15,
        }
        for category, rpm in limits.items():
            if rpm > 0:
                self._rate_limiter.configure(category, rpm)

    # ── Readiness probe ──────────────────────────

    async def probe_ready(self) -> dict[str, Any]:
        """
        Single-request readiness probe for the BrsApi key.

        While the key is blocked the platform runs in DB-only mode
        (``BRSAPI_ENABLED=false``), but the whole point of this probe is to
        detect when the server-side usage counter has reset — so it
        deliberately BYPASSES the ``enabled`` gate. It still respects the
        global rate limiter (fail-fast, never sleeps) so it can never burn
        budget or pile up behind other jobs.

        Returns:
            ``{"ready": bool, "status_code": int, "detail": str}`` where
            ``ready`` is True only when the endpoint answers HTTP 200
            (i.e. the counter has reset). HTTP 302 to a heavy file means the
            account is still over quota — reported as ``ready=False``.
        """
        if self._client is None:
            await self.start()

        endpoint = BrsApiEndpoints.ALL_SYMBOLS
        url = f"{self._base_url}{endpoint.path}"
        params = self._build_params(endpoint, None)

        # Fail fast (never sleep) — this probe runs hourly and must never
        # block behind an exhausted daily budget.
        try:
            await self._governor.acquire(
                endpoint.category.value,
                endpoint=endpoint.path,
                fail_fast=True,
            )
        except BudgetBlockedError as exc:
            return {
                "ready": False,
                "status_code": 302,
                "detail": f"budget governor cooldown: {exc}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ready": False,
                "status_code": 0,
                "detail": f"rate-limited: {exc}",
            }

        try:
            resp = await self._client.get(url, params=params)
        except httpx.RequestError as exc:
            return {
                "ready": False,
                "status_code": 0,
                "detail": f"request error: {_redact_sensitive_text(str(exc))}",
            }

        if resp.status_code == 200:
            return {"ready": True, "status_code": 200, "detail": "AllSymbols OK"}
        if resp.status_code == 302:
            return {
                "ready": False,
                "status_code": 302,
                "detail": "still redirecting to a heavy file (HTTP 302) — "
                "server-side usage counter has not reset",
            }
        return {
            "ready": False,
            "status_code": resp.status_code,
            "detail": f"unexpected HTTP {resp.status_code}",
        }

    # ── Health check ─────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Check connectivity by hitting a lightweight endpoint."""
        status = self._rate_limiter.status()
        # Budget-governor snapshot: persisted daily usage + block cooldown.
        governor_stats = await self._governor.stats()
        if not brsapi_settings.enabled:
            return {
                "service": "brsapi",
                "ready": self.is_ready,
                "reachable": False,
                "error": "BrsApi disabled via BRSAPI_ENABLED=false — DB-only mode",
                "enabled": False,
                "circuit_breakers": {
                    path: cb.state for path, cb in self._circuit_breakers.items()
                },
                "rate_limit_buckets": status,
                "budget_governor": governor_stats,
            }
        test_endpoint = BrsApiEndpoints.ALL_SYMBOLS
        result = await self.fetch(test_endpoint)
        return {
            "service": "brsapi",
            "ready": self.is_ready,
            "reachable": result.success,
            "error": result.error if not result.success else None,
            "enabled": True,
            "circuit_breakers": {
                path: cb.state for path, cb in self._circuit_breakers.items()
            },
            "rate_limit_buckets": status,
            "budget_governor": governor_stats,
        }


# ──────────────────────────────────────────────
#  Singleton convenience
# ──────────────────────────────────────────────

_client: BrsApiClient | None = None


async def get_client() -> BrsApiClient:
    """Return (and lazily start) the global ``BrsApiClient`` singleton."""
    global _client
    if _client is None:
        _client = BrsApiClient()
        await _client.start()
    return _client


async def close_client() -> None:
    """Close the global client if open."""
    global _client
    if _client is not None:
        await _client.stop()
        _client = None
