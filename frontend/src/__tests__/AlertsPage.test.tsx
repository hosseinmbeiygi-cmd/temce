import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

// ── Mocks ───────────────────────────────────────────────────────────────────
// The page talks to the backend only through @/lib/api, so mock that module and
// drive every branch deterministically. AppLayout / next/navigation are stubbed
// so the page can mount without a real router or layout chrome.

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
  routerPush: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  apiGet: mocks.apiGet,
  apiPost: mocks.apiPost,
  apiPut: mocks.apiPut,
  apiDelete: mocks.apiDelete,
  getStoredAuth: () => ({ access_token: "tok", user: {} }),
  extractItems: (response: unknown) =>
    (response as { data?: { items?: unknown[] } })?.data?.items ?? [],
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.routerPush, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/alerts",
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

import AlertsHubPage from "@/app/alerts/page";

function alertItem(overrides: Record<string, unknown> = {}) {
  return {
    id: "a1",
    instrument_id: "",
    symbol: "فولاد",
    alert_type: "price_above",
    condition: {},
    channels: ["console"],
    enabled: true,
    triggered_count: 3,
    last_triggered: null,
    description: "",
    created_at: null,
    updated_at: null,
    signal_id: "",
    market: "",
    timeframe: "",
    ...overrides,
  };
}

describe("AlertsHubPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.apiGet.mockResolvedValue({ success: true, data: { items: [alertItem()], total: 1 } });
  });

  it("renders an alert using the API's `enabled` field (not is_active)", async () => {
    render(<AlertsHubPage />);

    expect(await screen.findByText("فولاد")).toBeInTheDocument();
    // enabled=true must surface as "فعال" and the toggle must offer to disable.
    expect(screen.getByText("غیرفعال کردن")).toBeInTheDocument();
    expect(screen.getByText(/3 بار فعال‌شده/)).toBeInTheDocument();
  });

  it("shows a disabled alert and lets the user re-enable it", async () => {
    mocks.apiGet.mockResolvedValue({
      success: true,
      data: { items: [alertItem({ enabled: false })], total: 1 },
    });
    render(<AlertsHubPage />);

    const enableBtn = await screen.findByText("فعال کردن");
    expect(enableBtn).toBeInTheDocument();

    fireEvent.click(enableBtn);

    await waitFor(() =>
      expect(mocks.apiPut).toHaveBeenCalledWith("/alerts/a1", { enabled: true }),
    );
  });

  it("renders the empty state when there are no alerts", async () => {
    mocks.apiGet.mockResolvedValue({ success: true, data: { items: [], total: 0 } });
    render(<AlertsHubPage />);

    expect(await screen.findByText("هیچ هشداری تعریف نشده")).toBeInTheDocument();
  });
});
