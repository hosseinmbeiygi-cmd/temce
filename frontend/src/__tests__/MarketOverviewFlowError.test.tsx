// FE-02 — a failed flow request must not render as a measured zero.
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const flowState = vi.hoisted(() => ({
  current: { summary: null as null | { realNetB: number; legalNetB: number; queueBuy: number; queueSell: number }, isError: true },
}));

vi.mock("@/hooks/useMarketData", () => ({
  useMarketOverview: () => ({
    data: {
      breadth: { up: 2, down: 1, flat: 0 },
      tradeValueB: 12.5,
      volumeM: 3.1,
      avgChangePct: 0.4,
    },
    hasData: true,
    isLive: true,
    isFresh: true,
    isStale: false,
    isError: false,
    isLoading: false,
  }),
  useQuoteCards: () => ({ data: [] }),
  useFlowSummary: () => flowState.current,
}));

import MarketOverview from "@/components/dashboard/MarketOverview";

describe("MarketOverview flow text (FE-02)", () => {
  it("never claims zero inflow when the flow request failed", () => {
    flowState.current = { summary: null, isError: true };

    const { container } = render(<MarketOverview />);

    expect(container.textContent).not.toMatch(/وارد بازار کردند/);
    expect(container.textContent).toMatch(/جریان پول حقیقی در دسترس نیست/);
    // The flow banner is a real error, not an empty state.
    expect(screen.getByRole("status").textContent).toMatch(/ارتباط با سرور برقرار نشد/);
  });

  it("renders the real net flow when it exists", () => {
    flowState.current = {
      summary: { realNetB: 1.2, legalNetB: -0.3, queueBuy: 10, queueSell: 20 },
      isError: false,
    };

    const { container } = render(<MarketOverview />);

    expect(container.textContent).toMatch(/وارد بازار کردند/);
    expect(container.textContent).toMatch(/\+1\.2/);
  });
});
