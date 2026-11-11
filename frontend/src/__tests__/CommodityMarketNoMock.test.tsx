// FE-12 — بازار کالایی نباید در قطعی API به محصولات/قراردادهای نمونه برگردد.
//
// قبل از اصلاح: query نقدی در `catch` آرایهٔ MOCK_COMMODITIES را برمی‌گرداند و
// تب مشتقه همیشه MOCK_DERIVATIVES را رندر می‌کرد (فقط با یک پانویس کوچک).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

type QueryState = { data: unknown; isLoading: boolean; isError: boolean };

const queries = vi.hoisted(() => ({
  spot: { data: undefined, isLoading: false, isError: true } as QueryState,
  derivatives: { data: undefined, isLoading: false, isError: true } as QueryState,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: { queryKey: string[] }) =>
    options.queryKey[0] === "commodity-market" ? queries.spot : queries.derivatives,
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

import CommodityMarketPage from "@/app/markets/commodity/page";

beforeEach(() => {
  queries.spot = { data: undefined, isLoading: false, isError: true };
  queries.derivatives = { data: undefined, isLoading: false, isError: true };
});

describe("commodity market — no sample products (FE-12)", () => {
  it("shows an error panel and no sample commodities when the spot feed fails", () => {
    render(<CommodityMarketPage />);

    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق/);
    expect(screen.queryByText("زعفران نگین")).toBeNull();
    expect(screen.queryByText("شمش فولاد")).toBeNull();
  });

  it("shows an error panel and no sample contracts in the derivatives tab", () => {
    render(<CommodityMarketPage />);
    fireEvent.click(screen.getByRole("button", { name: /مشتقه کالایی/ }));

    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق/);
    expect(screen.queryByText("آتی زعفران نگین - آذر ۱۴۰۵")).toBeNull();
    expect(screen.queryByText(/قرارداد آتی فعالی برای نمایش وجود ندارد/)).toBeNull();
  });

  it("renders real futures rows from the IME endpoint", () => {
    queries.spot = { data: [], isLoading: false, isError: false };
    queries.derivatives = {
      data: [
        {
          id: "SBF-1405-10",
          symbol: "SBF-1405-10",
          name: "آتی شمش فولاد - دی ۱۴۰۵",
          underlying: "آتی شمش فولاد - دی ۱۴۰۵",
          contractType: "futures",
          maturityDate: "۱۴۰۵/۱۰/۱۵",
          settlementPrice: 24800000,
          change: 380000,
          changePercent: 1.56,
          volume: 12100,
          openInterest: 41500,
          lastPrice: 24800000,
          status: "active",
        },
      ],
      isLoading: false,
      isError: false,
    };

    render(<CommodityMarketPage />);
    fireEvent.click(screen.getByRole("button", { name: /مشتقه کالایی/ }));

    expect(screen.getByText("SBF-1405-10")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
