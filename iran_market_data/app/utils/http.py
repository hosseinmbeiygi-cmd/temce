from __future__ import annotations

import requests
from tenacity import retry, stop_after_attempt, wait_fixed


class HttpClient:
    """Standard HTTP client with retry logic for API calls."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json,text/html,*/*",
                "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
            }
        )

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def get(
        self, url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 30
    ) -> requests.Response:
        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def post(
        self,
        url: str,
        data: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
        timeout: int = 30,
    ) -> requests.Response:
        response = self.session.post(
            url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response
