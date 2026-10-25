// تب مستقل صندوق‌های طلا: همهٔ ردیف‌های snapshot (که از gold_fund_nav ساخته
// می‌شوند) باید دیده شوند؛ null نباید ۰٪ رندر شود.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mocks = vi.hoisted(() => ({ getSnapshot: vi.fn() }));
vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...mocks,
}));

import GoldFundsPage from "@/app/gold/funds/page";

const NAMES = ["عیار", "طلا", "کهربا", "زر", "زرفام", "گوهر", "تابش", "نفیس", "آلتون", "ناب"];

const funds = NAMES.map((name, index) => ({
  symbol: `FUND_${index}`,
  fund_name: name,
  nav_per_unit: 1_000 + index,
  market_price: 1_100 + index,
  bubble_pct: index === 0 ? null : 4.2,
  bpr: 1.2,
  real_buy_value: 0,
  real_sell_value: 0,
  net_inflow: 1_000_000_000,
  nav_change_7d_pct: null,
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <GoldFundsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("gold funds tab", () => {
  it("lists every fund from the snapshot, not a top-N subset", async () => {
    mocks.getSnapshot.mockResolvedValue({ funds });

    renderPage();

    expect(await screen.findByRole("heading", { name: "صندوق‌های طلا" })).toBeInTheDocument();
    await screen.findByText(NAMES[0]);
    for (const name of NAMES) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
    expect(screen.getByText(/۱۰ صندوق/)).toBeInTheDocument();
  });

  it("renders a null P/NAV bubble as an em-dash", async () => {
    mocks.getSnapshot.mockResolvedValue({ funds });
    renderPage();

    await screen.findByText(NAMES[0]);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.queryByText("0.00٪")).not.toBeInTheDocument();
  });

  it("shows a 503-aware error instead of an empty silent page", async () => {
    mocks.getSnapshot.mockRejectedValue(new Error("HTTP 503: unavailable"));
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("۵۰۳");
  });
});
