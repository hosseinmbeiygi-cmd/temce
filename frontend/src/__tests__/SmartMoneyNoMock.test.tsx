// FE-12 — تحلیل پول هوشمند نباید در قطعی API به دادهٔ ساختگی برنگردد.
//
// قبل از اصلاح، `catch` نتیجهٔ `generateMockResult` را رندر می‌کرد (با یک هشدار
// کوچک) و نمودار «روند SMC» همیشه از `generateMockHistory` ساخته می‌شد، حتی
// وقتی دادهٔ واقعی از سرور آمده بود.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

const apiGet = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({ apiGet }));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

import SmartMoneyPage from "@/app/smart-money/page";

const REAL_RESULT = {
  smart_money_score: 0.71,
  phase: "breakout_ready",
  scores: {
    accumulation: 0.6,
    absorption: 0.5,
    float_lock: 0.7,
    breakout_readiness: 0.8,
    buyer_power: 0.55,
    microstructure: 0.45,
  },
  penalties: { distribution_risk: 0.1, fake_breakout_risk: 0.05, dead_compression: 0.2 },
  features: {},
  breakout_features: {},
};

function analyze() {
  fireEvent.click(screen.getByRole("button", { name: /تحلیل/ }));
}

beforeEach(() => {
  apiGet.mockReset();
});

describe("smart-money page — no simulated analysis (FE-12)", () => {
  it("shows an error state instead of mock scores when the API fails", async () => {
    apiGet.mockRejectedValue(new Error("HTTP 503"));

    render(<SmartMoneyPage />);
    analyze();

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/ناموفق/));
    expect(screen.queryByText(/SMC Score/)).toBeNull();
    expect(screen.queryByText("آماده شکست")).toBeNull();
  });

  it("reports an explicit empty state when the endpoint returns no analysis", async () => {
    apiGet.mockResolvedValue({ success: true, data: null });

    render(<SmartMoneyPage />);
    analyze();

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/در دسترس نیست/));
  });

  it("renders the real analysis and never a fabricated SMC history chart", async () => {
    apiGet.mockResolvedValue({ success: true, data: REAL_RESULT });

    render(<SmartMoneyPage />);
    analyze();

    await waitFor(() => expect(screen.getByText(/SMC Score/)).toBeInTheDocument());
    expect(screen.getByText(/سری تاریخی امتیاز SMC/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
