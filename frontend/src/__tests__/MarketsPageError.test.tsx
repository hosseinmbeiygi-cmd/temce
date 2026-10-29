// FE-03 — an outage must render an error, not an empty market or a zero quote.
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: undefined, isLoading: false, isError: true }),
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

import MarketsPage from "@/app/markets/page";

describe("markets page error state (FE-03)", () => {
  it("shows an error panel when the overview/heatmap sources fail", () => {
    render(<MarketsPage />);

    expect(screen.getByRole("alert").textContent).toMatch(/ناموفق بود/);
  });
});
