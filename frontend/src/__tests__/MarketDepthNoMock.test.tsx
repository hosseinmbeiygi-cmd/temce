// FE-11 — صفحهٔ عمق بازار نباید دفتر سفارش ساختگی یا جدول هاردکدشده نشان دهد.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

type QueryState = { data: unknown; isLoading: boolean; isError: boolean };

const queryState = vi.hoisted(() => ({
  current: { data: undefined, isLoading: false, isError: true } as QueryState,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => queryState.current,
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

import MarketDepthPage from "@/app/market-depth/page";

beforeEach(() => {
  queryState.current = { data: undefined, isLoading: false, isError: true };
});

describe("market-depth page — no fabricated order book (FE-11)", () => {
  it("shows an error panel instead of a sample order book", () => {
    const { container } = render(<MarketDepthPage />);

    expect(container.querySelectorAll(".order-row")).toHaveLength(0);
    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق|خطا/);
  });

  it("does not render the hard-coded top-volume table", () => {
    render(<MarketDepthPage />);

    expect(screen.queryByText("نمادهای پرحجم")).toBeNull();
    expect(screen.queryByText("۱۲,۴۵۰")).toBeNull();
  });

  it("shows a skeleton while the order book loads", () => {
    queryState.current = { data: undefined, isLoading: true, isError: false };

    const { container } = render(<MarketDepthPage />);

    expect(container.querySelectorAll(".order-row")).toHaveLength(0);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders real levels when the order book answers", () => {
    queryState.current = {
      data: {
        bids: [{ price: 12000, volume: 100 }],
        asks: [{ price: 12100, volume: 50 }],
        lastPrice: 12050,
      },
      isLoading: false,
      isError: false,
    };

    const { container } = render(<MarketDepthPage />);

    expect(container.querySelectorAll(".order-row")).toHaveLength(2);
    expect(screen.getByText("12,000")).toBeInTheDocument();
    expect(screen.getByText("12,100")).toBeInTheDocument();
  });
});
