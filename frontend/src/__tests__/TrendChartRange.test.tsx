// FE-07 — range buttons must change the requested window, not just the cache key.
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const calls: string[] = [];

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiGet: vi.fn(async (url: string) => {
      calls.push(url);
      return {
        success: true,
        data: [
          { index_value: 100, fetched_at: "2026-10-29T09:00:00" },
          { index_value: 101, fetched_at: "2026-10-29T09:02:00" },
        ],
        data_as_of: "2026-10-29T09:02:00",
      };
    }),
  };
});

vi.mock("recharts", () => ({
  Area: () => null,
  AreaChart: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  ReferenceLine: () => null,
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

import TrendChart from "@/components/dashboard/TrendChart";

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("TrendChart ranges (FE-07)", () => {
  it("requests a wider point budget for the full-day range", async () => {
    renderWithQuery(<TrendChart />);

    await waitFor(() => expect(calls.some((u) => u.includes("limit=30"))).toBe(true));

    fireEvent.click(screen.getByText("کل روز"));

    await waitFor(() => expect(calls.some((u) => u.includes("limit=300"))).toBe(true));
  });
});
