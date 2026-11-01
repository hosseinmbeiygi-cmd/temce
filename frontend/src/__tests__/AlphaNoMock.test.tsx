// FE-12 — استراتژی‌های آلفا نباید در قطعی API کارنامهٔ ساختگی نشان دهند.
//
// قبل از اصلاح، هم شاخهٔ `catch` و هم پاسخ خالی، FALLBACK_ALPHAS را با اعداد
// عملکرد ساختگی (Sharpe 2.14، بازده 34.5%…) برمی‌گرداندند.

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
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

import AlphaPage from "@/app/alpha/page";

beforeEach(() => {
  queryState.current = { data: undefined, isLoading: false, isError: true };
});

describe("alpha page — no fabricated strategy performance (FE-12)", () => {
  it("shows an error panel and no fallback strategies when the API fails", () => {
    render(<AlphaPage />);

    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق/);
    expect(screen.queryByText("Momentum")).toBeNull();
    expect(screen.queryByText("ML Alpha")).toBeNull();
  });

  it("shows an empty state when the backend has no strategies", () => {
    queryState.current = { data: [], isLoading: false, isError: false };
    render(<AlphaPage />);

    expect(screen.getByText("هیچ استراتژی یافت نشد")).toBeInTheDocument();
    expect(screen.queryByText("Momentum")).toBeNull();
  });

  it("renders real strategies from the backend", () => {
    queryState.current = {
      data: [
        {
          id: "real-1",
          name: "استراتژی واقعی",
          version: "v1",
          sharpe: 1.2,
          returns: 9.5,
          volatility: 11.1,
          maxDrawdown: -6.4,
          winRate: 54,
          trades: 120,
          status: "active",
          description: "از سرور",
        },
      ],
      isLoading: false,
      isError: false,
    };

    render(<AlphaPage />);

    expect(screen.getByText(/استراتژی واقعی/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
