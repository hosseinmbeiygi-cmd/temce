"""Browser regression: reloading /gold must keep the session (STEP 8).

The defect this guards: ``hydrateSession()`` (auth provider, on mount) and the
401 path in ``apiRequest`` each refreshed independently. The backend rotates and
**revokes** the refresh token on every call, so two overlapping refreshes
invalidated each other; the loser returned no token, the request 401'd again and
``_handle401`` logged the user out. Every reload — and every second page opened
in the same tab — bounced to ``/auth/login``.

The pass criteria are the ones the live failure broke:

* three consecutive hard navigations to ``/gold`` all stay on ``/gold``;
* no API call fails with 401 while the session is alive;
* ``/auth/refresh`` is attempted at most once per document (no rotation race);
* no console errors and no uncaught page errors.

Requires the running stack (``next dev`` on :3000, the API on :8000). Skipped
when either is unreachable, so the default suite stays green.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import sync_playwright  # noqa: E402

FRONTEND = os.environ.get("GOLD_E2E_FRONTEND", "http://localhost:3000")
BACKEND = os.environ.get("GOLD_E2E_BACKEND", "http://127.0.0.1:8000")
# Credentials must not live in source: the previous literal was a real QA
# account password committed to git, so it also needs rotating.
PASSWORD = os.environ.get("GOLD_E2E_PASSWORD", "")
RELOADS = 3

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _reachable(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        # Any HTTP answer means the server is up.
        return True
    except Exception:
        return False


def _register(username: str, timeout: float = 20.0) -> None:
    payload = {
        "username": username,
        "email": f"{username}@qa.local",
        "password": PASSWORD,
        "full_name": "Gold Reload QA",
        "phone": "",
    }
    req = urllib.request.Request(
        f"{BACKEND}/api/v1/auth/register",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status not in (200, 201):
            raise AssertionError(f"register failed: http {resp.status}")


@pytest.fixture(scope="module")
def live_stack() -> None:
    if not _reachable(FRONTEND) or not _reachable(f"{BACKEND}/api/v1/gold/health"):
        pytest.skip("gold reload e2e needs the live frontend (:3000) and API (:8000)")
    if not PASSWORD:
        pytest.skip("set GOLD_E2E_PASSWORD to run the gold reload e2e")


def test_gold_survives_three_reloads(live_stack: None) -> None:
    username = f"goldreload{int(time.time())}"
    _register(username)

    console_errors: list[str] = []
    page_errors: list[str] = []
    refused: list[str] = []
    refresh_calls: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on(
            "response",
            lambda r: refused.append(f"{r.status} {r.url.split('?')[0]}")
            if r.status in (401, 403) and "/auth/refresh" not in r.url
            else None,
        )
        page.on(
            "request",
            lambda r: refresh_calls.append(r.url)
            if "/auth/refresh" in r.url and r.method == "POST"
            else None,
        )

        # ── sign in through the real form ───────────────────────────
        page.goto(f"{FRONTEND}/auth/login", wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3000)
        page.get_by_placeholder("نام کاربری خود را وارد کنید").fill(username)
        page.get_by_placeholder("رمز عبور خود را وارد کنید").fill(PASSWORD)
        page.locator("button[type=submit]").click()
        page.wait_for_url(lambda url: "/auth/login" not in url, timeout=90_000)

        # Refresh calls from the login page itself are not part of the window.
        refresh_calls.clear()

        # ── three reloads of the gold command center ────────────────
        for attempt in range(1, RELOADS + 1):
            console_errors.clear()
            page_errors.clear()
            refused.clear()
            refresh_calls.clear()

            page.goto(f"{FRONTEND}/gold", wait_until="domcontentloaded", timeout=90_000)
            # Wait for the gold shell to be interactive again after the reload.
            page.wait_for_selector('a[href="/gold/futures"]', timeout=90_000)
            page.wait_for_timeout(4000)

            assert "/auth/login" not in page.url, (
                f"reload {attempt}/{RELOADS} bounced to login: {page.url}\n"
                f"console errors: {console_errors[:5]}"
            )
            assert page.url.rstrip("/").endswith("/gold"), (
                f"reload {attempt}/{RELOADS} landed on {page.url}"
            )
            assert not refused, f"reload {attempt}/{RELOADS} hit failed API calls: {refused[:5]}"
            assert not page_errors, f"reload {attempt}/{RELOADS} raised page errors: {page_errors[:3]}"
            assert not console_errors, (
                f"reload {attempt}/{RELOADS} logged console errors: {console_errors[:3]}"
            )
            # One restore per document: a second refresh would rotate the token
            # again and can revoke the session under concurrent callers.
            assert len(refresh_calls) <= 1, (
                f"reload {attempt}/{RELOADS} refreshed {len(refresh_calls)} times in one document"
            )

        browser.close()
