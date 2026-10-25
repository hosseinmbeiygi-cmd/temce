// F6 / C10 — polling فقط وقتی سوکت قطع است؛ وقتی وصل است داده از WS می‌آید.
//
// امروز هیچ refetchInterval در درخت gold با وضعیت WS گیت نشده (۲۰+ مورد)،
// یعنی سرویس هم‌زمان هم push می‌گیرد هم poll.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const mocks = vi.hoisted(() => ({
  getSnapshot: vi.fn(),
  getFreshness: vi.fn(),
  getMacroCalendar: vi.fn(),
  getArbitrage: vi.fn(),
}));

vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...mocks,
  subscribeGoldWS: vi.fn(() => () => {}),
}));

// وضعیت WS را کنترل می‌کنیم تا ببینیم polling واقعاً گیت می‌شود یا نه.
const wsMock = vi.hoisted(() => ({ connected: true, stale: false }));
vi.mock("@/hooks/useGoldWS", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/hooks/useGoldWS")>()) as object),
  useGoldWS: () => ({
    state: wsMock.connected ? "open" : "closed",
    connected: wsMock.connected,
    lastMessageAt: null,
    ageSeconds: null,
    stale: wsMock.stale,
    lastHot: null,
  }),
}));

import GoldCommandCenterPage from "@/app/gold/page";

const snapshot = {
  snapshot_at: "2026-10-24T10:00:00Z",
  references: {
    xau_usd: 2345.67,
    usd_irt: 900000,
    aed_irt: 245000,
    aed_parity_usd: 3.6725,
    aed_gap_pct: 1.25,
    source: "brsapi",
    age_seconds: 12,
  },
  gold: {},
  coins: {},
  funds: [],
  score: {
    total: 62,
    decision: "YELLOW",
    components: {},
    hard_stop_active: false,
    hard_stop_reason: null,
  },
  quality_flag: "clean",
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return render(<GoldCommandCenterPage />, { wrapper: Wrapper });
}

describe("snapshot polling gate (F6)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    wsMock.connected = true;
    wsMock.stale = false;
    mocks.getSnapshot.mockResolvedValue(snapshot);
    mocks.getFreshness.mockResolvedValue({
      generated_at: "2026-10-24T10:00:00Z",
      overall: "ok",
      counts: { ok: 1, stale: 0, empty: 0, missing: 0 },
      sources: [],
    });
    mocks.getMacroCalendar.mockResolvedValue([]);
    mocks.getArbitrage.mockResolvedValue({ available: false, reason: "no data" });
  });

  async function settle() {
    // ۹۰ ثانیه: کافی است که کد قبلی (refetchInterval ثابت ۶۰۰۰۰) حداقل دو بار
    // دیگر هم refetch می‌کرد، پس اگر گیت واقعاً کار کند این تست قرمزِ معنادار دارد.
    for (let i = 0; i < 90; i++) {
      await vi.advanceTimersByTimeAsync(1000);
    }
  }

  it("does not poll the snapshot while the socket is connected", async () => {
    renderPage();
    await settle();
    expect(mocks.getSnapshot).toHaveBeenCalledTimes(1);
  });

  it("falls back to a 10s poll once the socket is down", async () => {
    wsMock.connected = false;
    renderPage();
    await settle();
    // ۹۰ ثانیه / ۱۰ ثانیه ≈ ۹ بار
    expect(mocks.getSnapshot.mock.calls.length).toBeGreaterThanOrEqual(8);
  });

  it("warns when the socket is connected but silent, instead of pretending it is live", async () => {
    wsMock.connected = true;
    wsMock.stale = true;
    renderPage();
    await vi.advanceTimersByTimeAsync(1500);
    expect(screen.getByText(/اتصال برقرار است ولی پیام تازه‌ای نمی‌رسد/)).toBeInTheDocument();
  });
});
