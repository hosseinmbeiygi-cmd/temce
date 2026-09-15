from __future__ import annotations

from core.exceptions import ExternalServiceError


class ProviderError(ExternalServiceError):
    def __init__(
        self, provider: str = "unknown", message: str = "Provider error", status_code: int | None = None
    ) -> None:
        super().__init__(service=provider, message=message, status_code=status_code)


class ProviderConnectionError(ProviderError):
    def __init__(self, provider: str = "unknown", message: str = "Provider connection failed") -> None:
        super().__init__(provider=provider, message=message, status_code=None)


class ProviderTimeoutError(ProviderError):
    def __init__(self, provider: str = "unknown", timeout: float = 30.0) -> None:
        super().__init__(provider=provider, message=f"Provider timeout after {timeout}s", status_code=None)


class ProviderAuthError(ProviderError):
    def __init__(self, provider: str = "unknown", message: str = "Provider authentication failed") -> None:
        super().__init__(provider=provider, message=message, status_code=401)


class ProviderRateLimitError(ProviderError):
    def __init__(self, provider: str = "unknown", retry_after: int | None = None) -> None:
        msg = "Provider rate limit exceeded"
        super().__init__(provider=provider, message=msg, status_code=429)


class ProviderDataError(ProviderError):
    def __init__(self, provider: str = "unknown", message: str = "Provider returned invalid data") -> None:
        super().__init__(provider=provider, message=message, status_code=None)
