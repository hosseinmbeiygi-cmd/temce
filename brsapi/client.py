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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from logging import getLogger
from typing import Any, TypeVar

import httpx
from httpx import AsyncHTTPTransport, Limits

# Fix stale Windows registry proxy BEFORE any HTTP connections
from core.fix_network import fix_network as _fix_network

_fix_network()

from brsapi.config import BrsApiEndpoints, EndpointCategory, EndpointConfig
from brsapi.config import settings as brsapi_settings
from brsapi.rate_limiter import RateLimiter, get_rate_limiter
from core.circuit_breaker import CircuitBreaker
from core.result import Result

T = TypeVar("T")
logger = getLogger(__name__)


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
        if self._client is None:
            return Result.fail("BrsApiClient not started – call .start() first")

        url = f"{self._base_url}{endpoint.path}"
        request_params = self._build_params(endpoint, params)
        category = category_override or endpoint.category.value

        # Circuit breaker for this endpoint path
        cb = self._circuit_breaker(endpoint.path)

        try:
            return await cb.call(
                self._do_fetch,
                url,
                request_params,
                category,
                endpoint,
            )
        except Exception as exc:
            logger.warning("BrsApi fetch failed [%s]: %s", endpoint.path, exc)
            return Result.fail(str(exc))

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

        # Rate limit (passes endpoint path for per-endpoint tracking)
        await self._rate_limiter.acquire(category, endpoint=endpoint.path)

        # HTTP request with retry
        last_error: str | None = None
        raw_bytes: bytes | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.get(url, params=params)
                elapsed = (asyncio.get_event_loop().time() - start) * 1000

                raw_bytes = resp.content

                if resp.status_code == 200:
                    data = self._parse_response(resp.content)
                    brs_resp = BrsApiResponse(
                        endpoint=endpoint.path,
                        status_code=200,
                        data=data,
                        raw_bytes=raw_bytes if self._raw_sink_enabled else None,
                        elapsed_ms=elapsed,
                        success=True,
                    )
                    return Result.ok(brs_resp)

                if resp.status_code in (429, 503):
                    # Rate limit / service unavailable → retry after delay
                    retry_after = self._parse_retry_after(resp)
                    last_error = f"HTTP {resp.status_code} – retry after {retry_after}s"
                    logger.warning("%s (attempt %d/%d)", last_error, attempt + 1, self._max_retries)
                    await asyncio.sleep(retry_after)
                    continue

                # Other HTTP error
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return Result.fail(last_error)

            except httpx.TimeoutException:
                last_error = "timeout"
                if attempt < self._max_retries:
                    delay = min(self._backoff_base ** (attempt + 1), self._backoff_max)
                    logger.warning("Timeout (attempt %d/%d) – retrying in %.1fs", attempt + 1, self._max_retries, delay)
                    await asyncio.sleep(delay)
                    continue
                return Result.fail(f"Request timeout after {self._max_retries} retries")

            except httpx.RequestError as exc:
                last_error = str(exc)
                if attempt < self._max_retries:
                    delay = min(self._backoff_base ** (attempt + 1), self._backoff_max)
                    logger.warning("RequestError (attempt %d/%d): %s – retrying in %.1fs", attempt + 1, self._max_retries, exc, delay)
                    await asyncio.sleep(delay)
                    continue
                return Result.fail(f"RequestError: {exc}")

        return Result.fail(f"All retries exhausted: {last_error}")

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

    def _parse_response(self, content: bytes) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Sometimes BrsApi returns plain text on error
            return {"_raw_text": content.decode("utf-8", errors="replace")}

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

    # ── Health check ─────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Check connectivity by hitting a lightweight endpoint."""
        test_endpoint = BrsApiEndpoints.ALL_SYMBOLS
        result = await self.fetch(test_endpoint)
        return {
            "service": "brsapi",
            "ready": self.is_ready,
            "reachable": result.success,
            "error": result.error if not result.success else None,
            "circuit_breakers": {
                path: cb.state for path, cb in self._circuit_breakers.items()
            },
            "rate_limit_buckets": self._rate_limiter.all_bucket_status(),
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
