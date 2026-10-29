// FE-01 — نقشهٔ بازار هرگز نباید دادهٔ نمونه را به‌جای دادهٔ واقعی نشان دهد.
//
// قبل از اصلاح، صفحه در `isLoading && !hasData` آرایهٔ `generateMockHeatmap()`
// را رندر می‌کرد و `LiveDataBanner` هم در حالت loading چیزی نشان نمی‌داد؛ یعنی
// نمادها و درصدهای ساختگی بدون هیچ برچسبی به‌عنوان دادهٔ زنده دیده می‌شدند.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

type HeatmapState = {
  data: Array<{ symbol: string; change: number }>;
  hasData: boolean;
  isFresh: boolean;
  isStale: boolean;
  isError: boolean;
  isLoading: boolean;
  dataAsOf: string | null;
};

const heatmapState = vi.hoisted(() => ({
  current: {
    data: [] as Array<{ symbol: string; change: number }>,
    hasData: false,
    isFresh: false,
    isStale: false,
    isError: false,
    isLoading: true,
    dataAsOf: null,
  } as HeatmapState,
}));

vi.mock("@/hooks/useMarketData", () => ({
  useEnrichedHeatmap: () => heatmapState.current,
}));

// The page's inline treemap query is irrelevant here; keep it pending.
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: undefined, isLoading: true, isError: false }),
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("recharts", () => ({
  Treemap: () => null,
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Tooltip: () => null,
}));

vi.mock("@/lib/types", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/types")>();
  return { ...actual, generateMockHeatmap: vi.fn(actual.generateMockHeatmap) };
});

import HeatmapPage from "@/app/heatmap/page";
import { generateMockHeatmap } from "@/lib/types";

function openSymbolsView() {
  const utils = render(<HeatmapPage />);
  fireEvent.click(screen.getByText("نمادها"));
  return utils;
}

beforeEach(() => {
  heatmapState.current = {
    data: [],
    hasData: false,
    isFresh: false,
    isStale: false,
    isError: false,
    isLoading: true,
    dataAsOf: null,
  };
  vi.mocked(generateMockHeatmap).mockClear();
});

describe("heatmap page — no fabricated data (FE-01)", () => {
  it("never generates sample cells, even before the first response", () => {
    const { container } = openSymbolsView();

    expect(generateMockHeatmap).not.toHaveBeenCalled();
    expect(container.querySelectorAll(".heatmap-cell")).toHaveLength(0);
  });

  it("shows a skeleton while the first load is running", () => {
    const { container } = openSymbolsView();

    expect(container.querySelector(".animate-pulse")).not.toBeNull();
  });

  it("shows an error panel instead of an empty grid when the feed fails", () => {
    heatmapState.current = { ...heatmapState.current, isLoading: false, isError: true };

    openSymbolsView();

    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق/);
  });

  it("renders real cells once data arrives", () => {
    heatmapState.current = {
      ...heatmapState.current,
      isLoading: false,
      hasData: true,
      isFresh: true,
      data: [{ symbol: "فولاد", change: 1.5 }],
    };

    const { container } = openSymbolsView();

    expect(container.querySelectorAll(".heatmap-cell")).toHaveLength(1);
    expect(screen.getByText("فولاد")).toBeInTheDocument();
  });
});
