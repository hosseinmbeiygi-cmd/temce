// FE-12 — مانیتور فاز نباید در قطعی API نمادهای ساختگی نشان دهد.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

const apiGet = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({ apiGet }));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

import PhaseMonitorPage from "@/app/smart-money/monitor/page";

beforeEach(() => {
  apiGet.mockReset();
});

describe("smart-money monitor — no sample phase table (FE-12)", () => {
  it("shows an outage banner and no symbol rows when the feed fails", async () => {
    apiGet.mockRejectedValue(new Error("HTTP 503"));

    render(<PhaseMonitorPage />);

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/ناموفق/));
    expect(screen.queryByText("فولاد")).toBeNull();
    expect(screen.queryByText("شپنا")).toBeNull();
    expect(screen.getByText(/وضعیت فازی برای هیچ نمادی/)).toBeInTheDocument();
  });

  it("renders real phase rows when the feed answers", async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: [
        {
          symbol: "فولاد",
          phase: "breakout_ready",
          smc: 0.72,
          scores: { accumulation: 0.6, absorption: 0.5, float_lock: 0.7, breakout_readiness: 0.8 },
          timestamp: Date.now(),
        },
      ],
    });

    render(<PhaseMonitorPage />);

    await waitFor(() => expect(screen.getByText("فولاد")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
