// FE-11 — ویجت «بازار زنده» نباید در قطعی API دادهٔ نمونه نشان دهد.
//
// قبل از اصلاح، هر چهار query در `catch` (و در پاسخ خالی) به mock برمی‌گشتند:
// `return extracted.length > 0 ? extracted : mockCells` و `catch { return mockGold }`.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

type QueryState = {
  data: unknown;
  isFetching: boolean;
  isError: boolean;
  dataUpdatedAt: number;
};

const queryState = vi.hoisted(() => ({
  current: {
    data: undefined,
    isFetching: false,
    isError: true,
    dataUpdatedAt: 0,
  } as QueryState,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => queryState.current,
}));

vi.mock("@/hooks/useWebSocket", () => ({
  useMarketWebSocket: () => ({ prices: new Map(), connected: false }),
}));

import LiveMarketWidget from "@/components/widgets/LiveMarketWidget";

beforeEach(() => {
  queryState.current = { data: undefined, isFetching: false, isError: true, dataUpdatedAt: 0 };
});

describe("LiveMarketWidget — no fabricated data (FE-11)", () => {
  it("never renders sample rows when the feeds fail", () => {
    const { container } = render(<LiveMarketWidget />);

    expect(screen.queryByText("طلا ۱۸")).toBeNull();
    expect(screen.queryByText("USD")).toBeNull();
    expect(container.querySelectorAll(".live-symbol-row")).toHaveLength(0);
    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق|خطا/);
  });

  it("shows skeletons, not samples, on the first load", () => {
    queryState.current = { data: undefined, isFetching: true, isError: false, dataUpdatedAt: 0 };

    const { container } = render(<LiveMarketWidget />);

    expect(container.querySelectorAll(".live-symbol-row")).toHaveLength(0);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders real rows once the feed answers", () => {
    queryState.current = {
      data: [{ symbol: "فولاد", price: 1000, change: 1.2 }],
      isFetching: false,
      isError: false,
      dataUpdatedAt: Date.now(),
    };

    const { container } = render(<LiveMarketWidget />);

    expect(container.querySelectorAll(".live-symbol-row")).toHaveLength(1);
    expect(screen.getByText("فولاد")).toBeInTheDocument();
  });
});
