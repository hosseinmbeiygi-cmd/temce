import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { Snapshot } from "@/types/gold";

const mocks = vi.hoisted(() => ({
  getSnapshot: vi.fn(),
  getFreshness: vi.fn(),
  getMacroCalendar: vi.fn(),
  getArbitrage: vi.fn(),
}));

// Partial mock: the four fetchers are faked, every other export (e.g.
// isServiceUnavailable) stays real so the components under test behave as
// they do in production.
vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...mocks,
}));

import GoldCommandCenterPage from "@/app/gold/page";

const asset = (overrides: Record<string, unknown>) => ({
  symbol: "IR_COIN_EMAMI",
  display_name: "سکه امامی",
  asset_type: "coin" as const,
  market_price: 50_000_000,
  fair_value: 46_000_000,
  bubble_abs: 4_000_000,
  bubble_pct: 8.5,
  implied_usd: null,
  quality_flag: "clean",
  ...overrides,
});

const snapshot: Snapshot = {
  snapshot_at: "2026-10-19T10:00:00Z",
  references: {
    xau_usd: 2345.67,
    usd_irt: 900_000,
    aed_irt: 245_000,
    aed_parity_usd: 3.6725,
    aed_gap_pct: 1.25,
    source: "brsapi",
    age_seconds: 12,
  },
  gold: {
    gold_18k: asset({
      symbol: "IR_GOLD_18K",
      display_name: "طلای ۱۸ عیار",
      asset_type: "gold",
      market_price: 5_000_000,
      fair_value: 4_900_000,
      bubble_pct: 2,
    }),
  },
  coins: { coin_emami: asset({}) },
  funds: [
    {
      symbol: "ZARFSHANG",
      fund_name: "زرافشان",
      nav_per_unit: 100_000,
      market_price: 105_000,
      bubble_pct: 5,
      bpr: 1.2,
      real_buy_value: 10,
      real_sell_value: 8,
      net_inflow: 2,
      nav_change_7d_pct: null,
    },
  ],
  score: {
    total: 62,
    decision: "YELLOW",
    components: {
      bubble: 0,
      bubble_reason: "",
      nav: 0,
      nav_reason: "",
      tsetmc: 0,
      tsetmc_reason: "",
      technical: 0,
      technical_reason: "",
      parity: 0,
      parity_reason: "",
      fund_flow: 0,
      fund_flow_reason: "",
    },
    hard_stop_active: false,
    hard_stop_reason: null,
  },
  quality_flag: "clean",
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return render(<GoldCommandCenterPage />, { wrapper: Wrapper });
}

describe("GoldCommandCenterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getSnapshot.mockResolvedValue(snapshot);
    mocks.getFreshness.mockResolvedValue({
      generated_at: "2026-10-19T10:00:00Z",
      overall: "stale",
      counts: { ok: 1, stale: 1, empty: 0, missing: 0 },
      sources: [
        {
          key: "gold_snapshots",
          label: "اسنپ‌شات GoldDesk",
          table: "gold_snapshots",
          column: "snapshot_at",
          max_age_minutes: 30,
          last_at: null,
          age_minutes: 90,
          rows: 5,
          status: "stale",
          detail: "۹۰ دقیقه",
        },
      ],
      scheduler_jobs: 4,
    });
    mocks.getMacroCalendar.mockResolvedValue([
      {
        event_id: "cpi-1",
        event_date: "2026-10-20",
        event_time: null,
        title: "CPI آمریکا",
        country: "US",
        category: "CPI",
        importance: 3,
        is_high_volatility: true,
        source: "fred",
      },
    ]);
    mocks.getArbitrage.mockResolvedValue({
      available: true,
      pair: "ETF ↔ طلای آب‌شده",
      gross_spread_pct: 3.4,
      net_spread_pct: 2.15,
      action: "BUY_PHYSICAL_SELL_ETF",
      strategy: "خرید فیزیکی و فروش ETF",
      estimated_profit_pct: 2.15,
    });
  });

  it("renders the snapshot, coins, funds and score from the live snapshot", async () => {
    renderPage();

    expect(await screen.findByText("خلاصه بازار طلا")).toBeInTheDocument();
    expect(screen.getByText(/امتیاز 62/)).toBeInTheDocument();
    expect(screen.getByText("سکه امامی")).toBeInTheDocument();
    expect(screen.getByText("زرافشان")).toBeInTheDocument();
    expect(screen.getByText("+8.50٪")).toBeInTheDocument();
  });

  it("renders the real freshness report and economic calendar", async () => {
    renderPage();

    expect(await screen.findByText(/وضعیت کلی/)).toBeInTheDocument();
    expect(await screen.findByText("CPI آمریکا")).toBeInTheDocument();
    expect(screen.getByText("پرنوسان")).toBeInTheDocument();
  });

  it("renders the arbitrage net spread", async () => {
    renderPage();

    expect(await screen.findByText("2.15٪")).toBeInTheDocument();
  });

  it("distinguishes a 503 outage from other snapshot failures (STEP 8)", async () => {
    mocks.getSnapshot.mockRejectedValue(
      new Error("Request failed with status code 503"),
    );
    renderPage();

    expect(await screen.findByText(/۵۰۳/)).toBeInTheDocument();
  });

  it("renders arbitrage as explicit no-data when available=false, without crashing (STEP 8)", async () => {
    mocks.getArbitrage.mockResolvedValue({
      available: false,
      reason: "no gold snapshot history with USD and AED prices",
      missing_symbols: ["gold_usd", "aed_irr"],
    });
    renderPage();

    expect(
      await screen.findByText(/no gold snapshot history/),
    ).toBeInTheDocument();
    expect(screen.getByText(/اسپرد آربیتراژ IME در دسترس نیست/)).toBeInTheDocument();
  });

  it("distinguishes a 503 outage for feed health (STEP 8)", async () => {
    mocks.getFreshness.mockRejectedValue(
      new Error("Request failed with status code 503"),
    );
    renderPage();

    expect(await screen.findByText(/۵۰۳/)).toBeInTheDocument();
  });

  it("distinguishes a 503 outage for the event calendar (STEP 8)", async () => {
    mocks.getMacroCalendar.mockRejectedValue(
      new Error("Request failed with status code 503"),
    );
    renderPage();

    expect(await screen.findByText(/۵۰۳/)).toBeInTheDocument();
  });

  it("renders missing bubble values as neutral no-data, never as zero colors (STEP 8)", async () => {
    mocks.getSnapshot.mockResolvedValue({
      ...snapshot,
      coins: { coin_emami: asset({ bubble_pct: null }) },
      funds: [{ ...snapshot.funds[0], bubble_pct: null }],
    });
    renderPage();

    const cells = (await screen.findAllByText("—"))
      .map((element) => element.closest("td"))
      .filter((cell): cell is HTMLTableCellElement => cell !== null);
    expect(cells.length).toBeGreaterThanOrEqual(2);
    for (const cell of cells) {
      expect(cell).not.toHaveClass("text-emerald-300");
      expect(cell).not.toHaveClass("text-rose-300");
    }
  });
});
