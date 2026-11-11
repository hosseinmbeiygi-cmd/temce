// Phase 2 market coverage surface — Tehran board, platform pricing, returns
// matrix, fund heatmap. Read-only: no buy/cart/checkout/payment control.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { FundRow } from "@/types/phase1";
import type {
  FundMapResponse,
  PeriodKey,
  PeriodReturn,
  PlatformsResponse,
  ReturnsMatrixResponse,
  TehranBoardResponse,
  TehranRow,
} from "@/types/phase2";

const mocks = vi.hoisted(() => ({
  getGoldTehranBoard: vi.fn(),
  getGoldPlatforms: vi.fn(),
  getGoldReturnsMatrix: vi.fn(),
  getGoldFundMap: vi.fn(),
}));

vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...mocks,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import MarketCoveragePage from "@/app/gold/coverage/page";
import { GoldFundsTable } from "@/app/gold/terminal/GoldFundsTable";
import { heatColor, safeShare } from "@/app/gold/coverage/FundMarketMap";

const AS_OF = "2026-10-26T08:59:30Z";

const REFERENCES = {
  xau_usd: 4000,
  usd_irt_rial: 1_000_000,
  as_of: AS_OF,
  source: "brsapi",
  quality: "DELAYED" as const,
  unit: "rial" as const,
  data_gaps: [],
};

const CAPABILITIES = {
  orders: false,
  wallet: false,
  delivery: false,
  checkout: false,
  payment: false,
  preview_only: true,
};

function tehranRow(overrides: Partial<TehranRow> = {}): TehranRow {
  return {
    key: "tehran_gold_18",
    label: "طلا گرم ۱۸ تهران",
    kind: "gold",
    price_basis: "gram",
    purity: 18,
    tehran_price: 68_000_000,
    official_symbol: "IR_GOLD_18K",
    official_label: "طلای ۱۸ عیار",
    official_price: 68_000_000,
    spread_vs_official_pct: 0,
    spread_vs_official_amount: 0,
    change_pct: 1,
    change_amount: 700_000,
    intrinsic: 69_000_000,
    bubble_pct: -1.45,
    bubble_amount: -1_000_000,
    implied_usd: 2819.77,
    as_of: AS_OF,
    source: "brsapi",
    source_detail: "tehran_shop_feed",
    quality: "DELAYED",
    intrinsic_quality: "DELAYED",
    note: null,
    data_gaps: [],
    ...overrides,
  };
}

const TEHRAN: TehranBoardResponse = {
  generated_at: "2026-10-26T09:00:00Z",
  unit: "rial",
  references: REFERENCES,
  source_status: "partial",
  rows: [
    tehranRow({}),
    tehranRow({
      key: "tehran_used_18",
      label: "طلا ۱۸ دست‌دوم",
      kind: "used",
      tehran_price: 71_000_000,
      spread_vs_official_pct: 4.41,
      spread_vs_official_amount: 3_000_000,
      change_pct: 1,
      change_amount: 700_000,
      intrinsic: 69_000_000,
      bubble_pct: 2.9,
      bubble_amount: 2_000_000,
      implied_usd: 2940.3,
      note: "قیمت دست‌دوم شامل کارمزد و اختلاف خرید/فروش است.",
    }),
    tehranRow({
      key: "tehran_gold_20",
      label: "طلا گرم ۲۰ تهران",
      purity: 20,
      tehran_price: null,
      official_price: null,
      spread_vs_official_pct: null,
      spread_vs_official_amount: null,
      change_pct: null,
      change_amount: null,
      intrinsic: null,
      bubble_pct: null,
      bubble_amount: null,
      implied_usd: null,
      as_of: null,
      source: "not_connected",
      quality: "NO_DATA",
      intrinsic_quality: "NO_DATA",
      data_gaps: ["قیمت خرده‌فروشی/بنکداری تهران در منبع متصل نیست"],
    }),
  ],
  capabilities: CAPABILITIES,
};

const PLATFORMS_EMPTY: PlatformsResponse = {
  generated_at: "2026-10-26T09:00:00Z",
  unit: "rial",
  source_status: "not_connected",
  platform_count: 0,
  rows: [],
  notice:
    "هیچ منبع قیمت زنده‌ای برای بسترهای آنلاین طلا متصل نیست؛ این بخش فقط مقایسهٔ قیمت است و هیچ مسیر خرید، پرداخت یا سفارشی ندارد.",
  capabilities: CAPABILITIES,
};

const PLATFORMS_WITH_ROW: PlatformsResponse = {
  ...PLATFORMS_EMPTY,
  source_status: "connected",
  platform_count: 1,
  notice: "قیمت‌ها فقط اطلاعاتی هستند و از منبع نام‌برده شده‌اند.",
  rows: [
    {
      platform: "بستر نمونه",
      platform_slug: "sample",
      buy_price: 70_000_000,
      sell_price: 69_500_000,
      low_price: 69_000_000,
      high_price: 71_000_000,
      intrinsic_18k: 69_000_000,
      bubble_pct: 1.45,
      implied_usd: 2898.4,
      as_of: AS_OF,
      source: "licensed_feed",
      source_detail: "platform_quote_feed",
      quality: "DELAYED",
      data_gaps: ["قیمت بستر ممکن است با کارمزد متفاوت باشد"],
    },
  ],
};

function period(
  overrides: Partial<Omit<PeriodReturn, "period">> & { period?: PeriodKey } = {},
): PeriodReturn {
  return {
    period: "1m",
    value: 5.2,
    status: "complete",
    start_date: "2026-09-26",
    end_date: "2026-10-26",
    start_price: 100,
    end_price: 105.2,
    observations: 31,
    reason: null,
    ...overrides,
  };
}

const RETURNS: ReturnsMatrixResponse = {
  generated_at: "2026-10-26T09:00:00Z",
  base_currency: "IRR",
  periods: ["1m", "3m", "6m", "9m", "1y"],
  correlation_against: "USD/IRR",
  method: "بازده ساده نقطه‌به‌نقطه؛ همبستگی پیرسون روی بازده روزانه.",
  rows: [
    {
      key: "coin_emami",
      label: "سکه امامی",
      asset_type: "gold",
      native_currency: "IRR",
      returns: {
        "1m": period({ value: 5.2, status: "complete" }),
        "3m": period({ period: "3m", value: 8.4, status: "complete" }),
        "6m": period({
          period: "6m",
          value: 10.1,
          status: "incomplete",
          reason: "داده برای این دوره کامل نیست",
        }),
        "9m": period({ period: "9m", value: null, status: "no_data", observations: 0, reason: null }),
        "1y": period({ period: "1y", value: null, status: "no_data", observations: 0 }),
      },
      correlation_90d: 0.42,
      correlation_observations: 90,
      correlation_status: "complete",
      correlation_reason: null,
      quality: "DELAYED",
      source: "brsapi_gold_history",
      data_gaps: [],
    },
    {
      key: "usd",
      label: "دلار آمریکا",
      asset_type: "currency",
      native_currency: "IRR",
      returns: {
        "1m": period({ value: 2.1 }),
        "3m": period({ period: "3m", value: 4.2 }),
        "6m": period({ period: "6m", value: 9.9 }),
        "9m": period({ period: "9m", value: 12.3 }),
        "1y": period({ period: "1y", value: 18.8 }),
      },
      correlation_90d: null,
      correlation_observations: 12,
      correlation_status: "no_data",
      correlation_reason: "برای همبستگی حداقل ۲۰ مشاهده لازم است",
      quality: "DELAYED",
      source: "brsapi_gold_currency_pro_daily_history",
      data_gaps: [],
    },
  ],
  capabilities: CAPABILITIES,
};

const FUND_MAP: FundMapResponse = {
  generated_at: "2026-10-26T09:00:00Z",
  size_metric: "trade_value",
  color_scale_pct: 4,
  cells: [
    {
      symbol: "کهربا",
      name: "صندوق طلای کهربا",
      size: 6_000_000_000,
      size_share_pct: 60,
      change_pct: 2.5,
      price: 12_000,
      quality: "DELAYED",
      as_of: AS_OF,
      href: `/gold/terminal#fund-${encodeURIComponent("کهربا")}`,
      data_gaps: [],
    },
    {
      symbol: "عیار",
      name: "صندوق طلای عیار",
      size: 4_000_000_000,
      size_share_pct: 40,
      change_pct: -1.2,
      price: 11_000,
      quality: "DELAYED",
      as_of: AS_OF,
      href: `/gold/terminal#fund-${encodeURIComponent("عیار")}`,
      data_gaps: [],
    },
  ],
  summary: {
    total_value: 10_000_000_000,
    currency: "rial",
    size_metric: "trade_value",
    items: [
      { label: "صندوق طلای کهربا", symbol: "کهربا", value: 6_000_000_000, share_pct: 60 },
      { label: "صندوق طلای عیار", symbol: "عیار", value: 4_000_000_000, share_pct: 40 },
    ],
    other_value: 0,
    other_share_pct: 0,
    cells_count: 2,
  },
  capabilities: CAPABILITIES,
};

const FUND_ROW: FundRow = {
  symbol: "عیار",
  name: "صندوق طلای عیار مفید",
  price: 11_000,
  change_pct: 2,
  change_amount: 200,
  last_trade_date: null,
  last_trade_time: "12:30:00",
  volume: 1_000,
  turnover: 11_000_000,
  market_cap: 5_000_000_000,
  nav: 10_000,
  nav_issue: 10_000,
  nav_redemption: 10_000,
  nav_date: "1405-07-12",
  nav_time: "17:00:00",
  nav_as_of: "2026-10-04T13:30:00Z",
  nav_source: "brsapi_nav_records",
  intrinsic_price: null,
  bubble_nominal_pct: 10,
  bubble_nominal_amount: 1_000,
  bubble_intrinsic_pct: null,
  bubble_intrinsic_amount: null,
  bubble_real_pct: null,
  composition: null,
  composition_status: "needs_composition",
  implied_usd: null,
  as_of: AS_OF,
  source: "brsapi",
  source_detail: "brsapi_ime_funds",
  quality: "DELAYED",
  nav_quality: "DELAYED",
  data_gaps: ["ترکیب دارایی صندوق از منبعی دریافت نشده است"],
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MarketCoveragePage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getGoldTehranBoard.mockResolvedValue(TEHRAN);
  mocks.getGoldPlatforms.mockResolvedValue(PLATFORMS_EMPTY);
  mocks.getGoldReturnsMatrix.mockImplementation(async (base: "IRR" | "USD") => ({
    ...RETURNS,
    base_currency: base,
  }));
  mocks.getGoldFundMap.mockImplementation(async (metric: "trade_value" | "market_value") => ({
    ...FUND_MAP,
    size_metric: metric,
  }));
});

afterEach(() => {
  window.location.hash = "";
});

describe("Phase 2 Tehran board", () => {
  it("keeps every row and renders a used-gold bubble distinct from the official 18k row", async () => {
    renderPage();

    const used = await screen.findByTestId("tehran-row-tehran_used_18");
    expect(used).toHaveAttribute("data-kind", "used");
    expect(within(used).getByTestId("tehran-bubble-tehran_used_18")).toHaveTextContent("+۲٫۹۰٪");
    expect(within(used).getByTestId("tehran-spread-tehran_used_18")).toHaveTextContent("+۴٫۴۱٪");
    expect(used).toHaveTextContent("قیمت دست‌دوم شامل کارمزد");

    const official = screen.getByTestId("tehran-row-tehran_gold_18");
    const officialBubble = within(official).getByTestId("tehran-bubble-tehran_gold_18");
    expect(officialBubble).toHaveTextContent("−۱٫۴۵٪");
    expect(officialBubble.textContent).not.toBe(
      within(used).getByTestId("tehran-bubble-tehran_used_18").textContent,
    );

    // ردیف بی‌منبع حذف نشده و «—» با دلیل است، نه صفر.
    const missing = screen.getByTestId("tehran-row-tehran_gold_20");
    expect(within(missing).getAllByTestId("missing-value").length).toBeGreaterThan(0);
    expect(within(missing).queryByText("۰")).not.toBeInTheDocument();
    expect(screen.getByTestId("tehran-source-status")).toHaveTextContent("بخشی از اقلام");
  });
});

describe("Phase 2 online platforms", () => {
  it("shows an empty state without rows, links or payment controls", async () => {
    renderPage();

    const empty = await screen.findByTestId("platforms-empty");
    expect(empty).toHaveTextContent("هیچ ردیف قیمتی");
    const section = screen.getByTestId("platforms-section");
    expect(section.querySelectorAll("a, button")).toHaveLength(0);
    expect(screen.getByTestId("platforms-notice")).toHaveTextContent("هیچ منبع قیمت زنده‌ای");
  });

  it("prices a connected platform row without adding any buy or payment route", async () => {
    mocks.getGoldPlatforms.mockResolvedValue(PLATFORMS_WITH_ROW);
    renderPage();

    const row = await screen.findByTestId("platform-row-sample");
    expect(row).toHaveTextContent("۷۰٬۰۰۰٬۰۰۰");
    expect(row).toHaveTextContent("+۱٫۴۵٪");

    const section = screen.getByTestId("platforms-section");
    // هیچ لینک بیرونی/خرید و هیچ دکمه‌ای در بخش بسترها نیست.
    expect(section.querySelectorAll("a")).toHaveLength(0);
    expect(section.querySelectorAll("button")).toHaveLength(0);
    expect(screen.queryByRole("link", { name: /خرید|فروش|پرداخت|سفارش|سبد/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("coverage-capability-note")).toHaveTextContent("سفارش: غیرفعال");
    expect(screen.getByTestId("coverage-capability-note")).toHaveTextContent("پرداخت: غیرفعال");
  });
});

describe("Phase 2 returns matrix", () => {
  it("renders complete periods and labels incomplete/no-data periods honestly", async () => {
    renderPage();

    await screen.findByTestId("returns-matrix");

    const complete = screen.getByTestId("return-cell-coin_emami-1m");
    expect(complete).toHaveAttribute("data-status", "complete");
    expect(complete).toHaveTextContent("+۵٫۲۰٪");
    expect(complete).not.toHaveTextContent("ناقص");

    const incomplete = screen.getByTestId("return-cell-coin_emami-6m");
    expect(incomplete).toHaveAttribute("data-status", "incomplete");
    expect(within(incomplete).getByTestId("period-incomplete-coin_emami-6m")).toHaveTextContent(
      "ناقص",
    );
    expect(incomplete).toHaveAttribute("title", "داده برای این دوره کامل نیست");

    const noData = screen.getByTestId("return-cell-coin_emami-9m");
    expect(noData).toHaveAttribute("data-status", "no_data");
    expect(noData).toHaveTextContent("—");

    // همبستگی بدون ۲۰ مشاهده «—» با دلیل است، نه صفر.
    expect(screen.getByTestId("correlation-usd")).toHaveTextContent("—");
    expect(screen.getByTestId("correlation-usd")).toHaveAttribute(
      "title",
      "برای همبستگی حداقل ۲۰ مشاهده لازم است",
    );
  });

  it("re-queries in USD and shows the same-window conversion note", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByTestId("returns-matrix");
    await user.click(screen.getByTestId("base-currency-USD"));

    await waitFor(() =>
      expect(mocks.getGoldReturnsMatrix).toHaveBeenLastCalledWith("USD"),
    );
    expect(await screen.findByTestId("returns-usd-note")).toHaveTextContent(
      "بازده دلار/ریالِ همان پنجره",
    );
    expect(screen.getByTestId("base-currency-USD")).toHaveAttribute("aria-pressed", "true");
  });
});

describe("Phase 2 fund map", () => {
  it("links each tile to the Phase 1 fund row and never emits Infinity/NaN", async () => {
    renderPage();

    const tile = await screen.findByTestId("fund-map-cell-کهربا");
    expect(tile).toHaveAttribute("href", `/gold/terminal#fund-${encodeURIComponent("کهربا")}`);
    expect(tile).toHaveTextContent("+۲٫۵۰٪");

    const container = screen.getByTestId("fund-map");
    expect(container.innerHTML).not.toMatch(/Infinity|NaN/);
    expect(screen.getByTestId("fund-map-total")).toHaveTextContent("۱۰٬۰۰۰٬۰۰۰٬۰۰۰");
  });

  it("guards non-finite sizes and returns at the helper boundary", () => {
    expect(heatColor(Number.POSITIVE_INFINITY, 4)).toBe("rgba(63, 63, 70, 0.55)");
    expect(heatColor(2, 0)).toBe("rgba(63, 63, 70, 0.55)");
    expect(heatColor(2, 4)).toMatch(/^rgba\(16, 185, 129, /);
    expect(heatColor(-2, 4)).toMatch(/^rgba\(244, 63, 94, /);
    expect(safeShare(Number.POSITIVE_INFINITY)).toBe(1);
    expect(safeShare(Number.NaN)).toBe(1);
    expect(safeShare(-5)).toBe(1);
    expect(safeShare(60)).toBe(60);
  });

  it("switches the size metric to market value", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByTestId("fund-map");
    await user.click(screen.getByTestId("size-metric-market_value"));

    await waitFor(() => expect(mocks.getGoldFundMap).toHaveBeenLastCalledWith("market_value"));
    expect(screen.getByTestId("size-metric-market_value")).toHaveAttribute("aria-pressed", "true");
  });
});

describe("Phase 2 hand-off to Phase 1", () => {
  it("gives each fund row the id the market map links to and flashes it after navigation", async () => {
    window.location.hash = `#fund-${encodeURIComponent("عیار")}`;
    const { container } = render(<GoldFundsTable funds={[FUND_ROW]} />);

    const row = await screen.findByTestId("fund-row-عیار");
    expect(row).toHaveAttribute("id", "fund-عیار");
    expect(container.querySelector("#fund-عیار")).toBe(row);
    expect(row).toHaveClass("gd-fund-flash");
  });
});
