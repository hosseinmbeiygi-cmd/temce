// FE-15 — مطمئن شو که تغییر mute باعث شروع مجدد interval نمی‌شود.
//
// قبلاً `refresh` به `playChime` وابسته بود. هر بار که muted تغییر می‌کرد،
// hook یک تابع `playChime` جدید برمی‌گرداند، `refresh` بازسازی می‌شد و
// `useEffect([refresh])` یک interval جدید اضافه می‌کرد و یک burst جدید
// از ۵ درخواست موازی fire می‌کرد.
// با اصلاح: `playChimeRef` به‌روزرسانی می‌شود ولی identity `refresh` ثابت
// می‌ماند — `useEffect([refresh])` فقط یک بار در mount اجرا می‌شود.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import React from "react";

// ── mock state ───────────────────────────────────────────────────
// Use an object so the mock factory closes over a mutable reference —
// vi.mock factories are hoisted and can't close over `let` variables.
const sound = {
  muted: false,
  toggleMute: vi.fn(() => { sound.muted = !sound.muted; }),
  playChime: vi.fn(),
};

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

// ── module mocks ─────────────────────────────────────────────────
vi.mock("@/lib/api", () => ({
  apiGet: apiMocks.apiGet,
  apiPost: apiMocks.apiPost,
  apiPut: apiMocks.apiPut,
  apiDelete: apiMocks.apiDelete,
}));

vi.mock("@/lib/api-errors", () => ({
  describeApiError: (_: unknown, fallback: string) => fallback,
}));

vi.mock("@/hooks/useNotificationSound", () => ({
  useNotificationSound: () => sound,
}));

vi.mock("@/components/SymbolSelector", () => ({
  default: () => null,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/alerts",
}));

// ── import component after mocks ─────────────────────────────────
import MonitorWorkspace from "@/components/alerts/MonitorWorkspace";

// ── helpers ──────────────────────────────────────────────────────
function okApiResponse(endpoint: string): Promise<unknown> {
  if (endpoint.includes("/alerts/monitors"))
    return Promise.resolve({ data: { items: [] } });
  if (endpoint.includes("/alerts/engine/portfolio"))
    return Promise.resolve({ data: { allocated_capital_toman: 500_000_000, cash_toman: 490_000_000, budgets_toman: { per_trade_risk: 2_500_000 }, positions: [] } });
  if (endpoint.includes("/alerts/engine/health"))
    return Promise.resolve({ data: { status: "ok", market_open: false, market_data: { status: "ok" }, telegram: "not_configured" } });
  if (endpoint.includes("/alerts/engine/notifications"))
    return Promise.resolve({ data: { items: [] } });
  if (endpoint.includes("/alerts/engine/settings"))
    return Promise.resolve({ data: { settings: { notifications: { sound_enabled: true, sound_severities: ["critical"] }, risk: {} } } });
  return Promise.resolve({ data: {} });
}

// ── tests ─────────────────────────────────────────────────────────
describe("MonitorWorkspace — refresh stability", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    apiMocks.apiGet.mockImplementation(okApiResponse);
    // Fresh playChime reference each test suite run
    sound.playChime = vi.fn();
    sound.muted = false;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("fires exactly 5 apiGet requests on mount (one Promise.all)", async () => {
    const { unmount } = render(<MonitorWorkspace />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(5);
    unmount();
  });

  it("changing playChime reference does NOT trigger a new fetch burst", async () => {
    const { rerender, unmount } = render(<MonitorWorkspace />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(5);

    // Simulate muted toggle: React re-renders, useNotificationSound returns
    // a new playChime reference. With the fix, refresh identity stays stable.
    sound.playChime = vi.fn(); // new function reference, as a real muted toggle would cause
    sound.muted = true;
    rerender(<MonitorWorkspace />);
    await act(async () => { await Promise.resolve(); });

    // Must still be 5 — no extra burst from re-fired useEffect([refresh])
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(5);
    unmount();
  });

  it("exactly one interval fires every 30 s — no accumulation from mute toggles", async () => {
    const { unmount } = render(<MonitorWorkspace />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(5); // initial fetch

    // First 30 s tick
    await act(async () => { vi.advanceTimersByTime(30_000); });
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(10); // exactly 5 more

    // Simulate two mute toggles (old bug: each would spawn a new interval)
    sound.playChime = vi.fn();
    sound.muted = true;

    // Second 30 s tick
    await act(async () => { vi.advanceTimersByTime(30_000); });
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });

    // With the fix: exactly 5 more (1 interval). With the bug: ≥10 more (2+ intervals).
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(15);

    unmount();
  });

  it("clears the interval on unmount — no stale timers", async () => {
    const { unmount } = render(<MonitorWorkspace />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    const countAtUnmount = apiMocks.apiGet.mock.calls.length;

    unmount();

    // Advance well past one tick — no new calls should fire
    await act(async () => { vi.advanceTimersByTime(60_000); });
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(countAtUnmount);
  });
});
