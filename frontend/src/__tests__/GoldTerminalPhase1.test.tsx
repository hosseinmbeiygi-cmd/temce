// Phase 1 terminal surface — fail-closed rendering, what-if preview, no order UI.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import type { GoldTerminal, GoldWhatIf } from "@/types/phase1";

const mocks = vi.hoisted(() => ({
  getGoldTerminal: vi.fn(),
  postGoldWhatIf: vi.fn(),
}));

// Partial mock: everything else (isServiceUnavailable, etc.) stays real.
vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...mocks,
}));

import GoldTerminalPage from "@/app/gold/terminal/page";

const AS_OF = "2026-10-26T08:59:30Z";
const CAPABILITIES = { orders: false, wallet: false, delivery: false, preview_only: true };

const TERMINAL: GoldTerminal = {
  generated_at: "2026-10-26T09:00:00Z",
  unit: "rial",
  references: {
    xau_usd: 4000,
    usd_irt_rial: 1_000_000,
    as_of: AS_OF,
    source: "brsapi",
    quality: "DELAYED",
    unit: "rial",
    data_gaps: [],
  },
  ticker: [
    {
      key: "XAUUSD",
      label: "اونس جهانی طلا (XAU/USD)",
      price: 4000,
      unit: "ounce",
      change_pct: 0.5,
      change_amount: 20,
      as_of: AS_OF,
      source: "brsapi",
      source_detail: "brsapi_commodity_prices",
      quality: "DELAYED",
      status: "ok",
      note: null,
    },
    {
      key: "IR_GOLD_18K",
      label: "طلای ۱۸ عیار",
      price: 68_000_000,
      unit: "rial",
      change_pct: 1.5,
      change_amount: 1_000_000,
      as_of: AS_OF,
      source: "brsapi",
      source_detail: "brsapi_gold_coin_prices",
      quality: "DELAYED",
      status: "ok",
      note: null,
    },
    {
      key: "USD",
      label: "دلار آزاد",
      price: 1_000_000,
      unit: "rial",
      change_pct: null,
      change_amount: null,
      as_of: AS_OF,
      source: "brsapi",
      source_detail: "brsapi_currency_prices",
      quality: "DELAYED",
      status: "ok",
      note: null,
    },
    {
      key: "GOLD_FUND_INDEX",
      label: "شاخص صندوق‌های طلا",
      price: null,
      unit: "rial",
      change_pct: null,
      change_amount: null,
      as_of: null,
      source: "none",
      source_detail: "نامشخص",
      quality: "NO_DATA",
      status: "under_construction",
      note: "منبع شاخص صندوق‌های طلا هنوز متصل نیست.",
    },
  ],
  physical: [
    {
      symbol: "IR_GOLD_18K",
      label: "طلای ۱۸ عیار",
      kind: "gold",
      price_basis: "gram",
      price: 68_000_000,
      change_pct: 1.5,
      change_amount: 1_000_000,
      intrinsic: 69_000_000,
      bubble_pct: -1.45,
      bubble_amount: -1_000_000,
      implied_usd: 2819.77,
      as_of: AS_OF,
      source: "brsapi",
      source_detail: "brsapi_gold_coin_prices",
      quality: "DELAYED",
      intrinsic_quality: "DELAYED",
      data_gaps: [],
    },
    {
      symbol: "IR_COIN_1G",
      label: "سکه یک گرمی",
      kind: "coin",
      price_basis: "coin",
      price: null,
      change_pct: null,
      change_amount: null,
      intrinsic: null,
      bubble_pct: null,
      bubble_amount: null,
      implied_usd: null,
      as_of: null,
      source: "brsapi",
      source_detail: "brsapi_gold_coin_prices",
      quality: "NO_DATA",
      intrinsic_quality: "NO_DATA",
      data_gaps: ["قیمت بازار در منبع موجود نیست"],
    },
  ],
  funds: [
    {
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
    },
  ],
  certificates: [
    {
      contract_code: "GoldBar",
      commodity: "شمش طلا",
      description: "گواهی سپرده کالایی",
      price: 34_552_090,
      change_pct: 1.2,
      change_amount: 400_000,
      volume: 10,
      turnover: 345_520_900,
      contract_size: 1,
      contract_size_unit: "ضریب تبدیل نماد به گروه انبار",
      intrinsic: null,
      bubble_pct: null,
      bubble_amount: null,
      implied_usd: null,
      as_of: AS_OF,
      source_date: "2026-10-26",
      source: "brsapi",
      source_detail: "brsapi_ime_certificates",
      quality: "DELAYED",
      intrinsic_quality: "NO_DATA",
      data_gaps: ["وزن و عیار قرارداد گواهی در منبع موجود نیست"],
    },
  ],
  capabilities: CAPABILITIES,
};

const WHAT_IF: GoldWhatIf = {
  generated_at: "2026-10-26T09:05:00Z",
  inputs: { xau_usd: 5000, usd_irt_rial: 1_500_000, usd_irt_toman: 150_000 },
  physical: [
    {
      symbol: "IR_GOLD_18K",
      label: "طلای ۱۸ عیار",
      market_price: 68_000_000,
      base_intrinsic: 69_000_000,
      preview_intrinsic: 90_000_000,
      base_bubble_pct: -1.45,
      preview_bubble_pct: -24.44,
      base_bubble_amount: -1_000_000,
      preview_bubble_amount: -22_000_000,
      base_implied_usd: 2819.77,
      preview_implied_usd: 3777.78,
      quality: "DELAYED",
      preview_quality: "SAMPLE",
      data_gaps: [],
    },
  ],
  funds: [
    {
      symbol: "عیار",
      name: "صندوق طلای عیار مفید",
      nav: 10_000,
      market_price: 11_000,
      nominal_bubble_pct_before: 10,
      nominal_bubble_pct_after: 10,
      real_bubble_pct_before: null,
      real_bubble_pct_after: null,
      implied_usd_before: null,
      implied_usd_after: null,
      data_gaps: ["ترکیب دارایی صندوق از منبعی دریافت نشده است"],
    },
  ],
  capabilities: CAPABILITIES,
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <GoldTerminalPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getGoldTerminal.mockResolvedValue(TERMINAL);
});

describe("Phase 1 terminal", () => {
  it("renders reference strip, ticker and the under-construction index without a fake price", async () => {
    renderPage();

    await screen.findByTestId("phase1-ticker");
    const strip = screen.getByTestId("reference-strip");
    expect(strip).toHaveTextContent("XAU/USD");
    expect(strip).toHaveTextContent("۴٬۰۰۰٫۰۰");
    expect(strip).toHaveTextContent("۱٬۰۰۰٬۰۰۰");

    const index = screen.getByTestId("ticker-GOLD_FUND_INDEX");
    expect(within(index).getByTestId("under-construction")).toHaveTextContent("در دست ساخت");
    expect(within(index).queryByTestId("ticker-price-GOLD_FUND_INDEX")).not.toBeInTheDocument();

    const xau = screen.getByTestId("ticker-XAUUSD");
    expect(within(xau).getByTestId("ticker-price-XAUUSD")).toHaveTextContent("۴٬۰۰۰٫۰۰");
  });

  it("renders null market data as «—» with a NO_DATA badge, never zero", async () => {
    renderPage();

    const row = await screen.findByTestId("physical-row-IR_COIN_1G");
    const missing = within(row).getAllByTestId("missing-value");
    expect(missing.length).toBeGreaterThan(0);
    expect(missing[0]).toHaveAttribute("title", "قیمت بازار در منبع موجود نیست");
    expect(within(row).queryByText("۰")).not.toBeInTheDocument();

    const badges = within(row).getAllByTestId("quality-badge");
    expect(badges.some((badge) => badge.getAttribute("data-quality") === "NO_DATA")).toBe(true);
  });

  it("toggles the physical bubble column between percent and Rial", async () => {
    const user = userEvent.setup();
    renderPage();

    const row = await screen.findByTestId("physical-row-IR_GOLD_18K");
    expect(row).toHaveTextContent("−۱٫۴۵٪");
    expect(screen.getByRole("columnheader", { name: "حباب (٪)" })).toBeInTheDocument();

    await user.click(screen.getByTestId("bubble-percent-toggle"));

    expect(screen.getByRole("columnheader", { name: "حباب (ریال)" })).toBeInTheDocument();
    expect(within(row).getByText("−۱٬۰۰۰٬۰۰۰")).toBeInTheDocument();
  });

  it("computes the nominal fund bubble from NAV and marks composition as missing", async () => {
    renderPage();

    const row = await screen.findByTestId("fund-row-عیار");
    expect(row).toHaveTextContent("+۱۰٫۰۰٪");
    expect(row).toHaveTextContent("+۱٬۰۰۰ ریال");
    expect(row).toHaveTextContent("۱۴۰۵/۰۷/۱۲");
    expect(row).toHaveTextContent("نیاز به ترکیب دارایی صندوق");
    expect(screen.getByRole("columnheader", { name: "قیمت ذاتی پشتوانه" })).toBeInTheDocument();
    expect(
      within(row).getByTestId("composition-status-عیار"),
    ).toHaveTextContent("نیاز به ترکیب دارایی صندوق");
  });

  it("shows certificate analytics as «—» rather than inventing grams", async () => {
    renderPage();

    const row = await screen.findByTestId("certificate-row-GoldBar");
    expect(row).toHaveTextContent("گواهی شمش طلا");
    expect(within(row).getAllByTestId("missing-value").length).toBeGreaterThanOrEqual(3);
    expect(row).toHaveTextContent("ضریب تبدیل نماد به گروه انبار");
    expect(screen.getByText("چرا ارزش ذاتی گواهی‌ها خالی است؟")).toBeInTheDocument();
  });

  it("previews a what-if scenario as SAMPLE without touching live values", async () => {
    mocks.postGoldWhatIf.mockResolvedValue(WHAT_IF);
    const user = userEvent.setup();
    renderPage();

    const form = await screen.findByTestId("what-if-form");
    const xau = screen.getByTestId("what-if-xau");
    const usd = screen.getByTestId("what-if-usd");

    await user.clear(xau);
    await user.type(xau, "5000");
    await user.clear(usd);
    await user.type(usd, "1500000");
    await user.click(within(form).getByRole("button", { name: "محاسبه پیش‌نمایش" }));

    expect(mocks.postGoldWhatIf.mock.calls[0][0]).toEqual({
      xau_usd: 5000,
      usd_irt_rial: 1_500_000,
    });

    const preview = await screen.findByTestId("what-if-preview");
    expect(within(preview).getByText(/SAMPLE/)).toBeInTheDocument();
    expect(within(preview).getByTestId("what-if-physical-table")).toHaveTextContent(
      "۹۰٬۰۰۰٬۰۰۰",
    );
    // حباب اسمی صندوق NAV-محور است و با سناریو تغییر نمی‌کند.
    const fundRows = within(preview).getByTestId("what-if-funds-table");
    expect(fundRows).toHaveTextContent("+۱۰٫۰۰٪");
    expect(fundRows).toHaveTextContent("بدون تغییر");

    // دادهٔ زندهٔ جدول اصلی دست‌نخورده می‌ماند.
    const physical = screen.getByTestId("physical-row-IR_GOLD_18K");
    expect(physical).toHaveTextContent("۶۹٬۰۰۰٬۰۰۰");
  });

  it("offers no order, buy, sell or wallet control", async () => {
    renderPage();

    await screen.findByTestId("phase1-ticker");
    expect(screen.queryByRole("button", { name: /خرید|فروش|سفارش/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /خرید|فروش|سفارش|کیف پول/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("capability-note")).toHaveTextContent("سفارش: غیرفعال");
    expect(screen.getByTestId("capability-note")).toHaveTextContent("کیف پول: غیرفعال");
  });

  it("shows an explicit error when the terminal endpoint fails", async () => {
    mocks.getGoldTerminal.mockRejectedValueOnce(new Error("network down"));
    renderPage();

    const alert = await screen.findByTestId("terminal-error");
    expect(alert).toHaveTextContent("دریافت میز داده ناموفق بود.");
  });
});
