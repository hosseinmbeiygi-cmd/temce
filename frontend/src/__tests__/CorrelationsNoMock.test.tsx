// FE-12 — صفحهٔ همبستگی‌ها نباید در قطعی API لیست نمونهٔ ثابت نشان دهد.

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

import CorrelationsPage from "@/app/correlations/page";

beforeEach(() => {
  queryState.current = { data: undefined, isLoading: false, isError: true };
});

describe("correlations page — no static demo pairs (FE-12)", () => {
  it("shows an error panel instead of the sample category list", () => {
    render(<CorrelationsPage />);

    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق/);
    expect(screen.queryByText("مس / فولاد")).toBeNull();
    expect(screen.queryByText("سکه / دلار")).toBeNull();
  });

  it("shows an empty state when the backend answers with no pairs", () => {
    queryState.current = { data: [], isLoading: false, isError: false };
    render(<CorrelationsPage />);

    expect(screen.getByText("داده‌ای برای نمایش وجود ندارد")).toBeInTheDocument();
  });

  it("renders only real pairs from the backend", () => {
    queryState.current = {
      data: [
        {
          name: "فلزات",
          pairs: [
            {
              pair: "فولاد / شپنا",
              symbolA: "فولاد",
              symbolB: "شپنا",
              correlation: 0.61,
              strength: "moderate",
              direction: "positive",
              trend: "stable",
              description: "واقعی",
            },
          ],
        },
      ],
      isLoading: false,
      isError: false,
    };

    render(<CorrelationsPage />);

    expect(screen.getByText("فولاد / شپنا")).toBeInTheDocument();
    expect(screen.queryByText("مس / فولاد")).toBeNull();
  });
});
