// C7/backend-731de301 — حذف گروهی، ثبت فروش با id تازه، و null-safety.
//
// این تست‌ها قرارداد جدید بک‌اند را روی UI قفل می‌کنند:
//   * گروه چندردیفی فقط `holding_ids` دارد و `id` ندارد؛ دکمهٔ حذف باید بماند.
//   * هر id جداگانه و پشت‌سرهم حذف می‌شود؛ هیچ‌وقت `force` فرستاده نمی‌شود.
//   * 409 یعنی «قبلاً حذف شده» و 404/شبکه پیام روشن + refetch پورتفو.
//   * ثبت فروش فقط idی را می‌فرستد که در پاسخ تازهٔ /portfolio بوده است.
//   * pnl_pct/current_value/pnl_irt/priced_cost خالی «—» است، نه صفر.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const api = vi.hoisted(() => ({
  getPortfolioPerformance: vi.fn(),
  capturePortfolioSnapshot: vi.fn(),
}));
vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...api,
}));

const restApi = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/api")>()) as object),
  ...restApi,
}));

import GoldPortfolioPage from "@/app/gold/portfolio/page";

const holding = (overrides: Record<string, unknown> = {}) => ({
  id: 7 as number | undefined,
  holding_ids: [7],
  symbol: "IR_COIN_EMAMI",
  display_name: "سکه امامی",
  quantity: 2,
  avg_buy_price: 40_000_000,
  current_price: 50_000_000,
  cost_basis: 80_000_000,
  current_value: 100_000_000,
  pnl_irt: 20_000_000,
  pnl_pct: 25,
  n_purchases: 1,
  ...overrides,
});

const portfolio = (holdings: unknown[], overrides: Record<string, unknown> = {}) => ({
  success: true,
  data: {
    total_cost: 80_000_000,
    total_value: 100_000_000,
    total_pnl: 20_000_000,
    total_pnl_pct: 25,
    priced_cost: 80_000_000,
    unpriced_holdings: 0,
    holdings,
    snapshot_at: null,
    ...overrides,
  },
});

function installPortfolio(payload: unknown) {
  restApi.apiGet.mockImplementation(async (url: string) => {
    if (url.includes("/gold/portfolio/trades")) return { success: true, data: [] };
    if (url.includes("/gold/portfolio/dca")) return { success: true, data: [] };
    if (url.includes("/gold/portfolio")) return payload;
    throw new Error("unexpected GET " + url);
  });
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, refetchOnWindowFocus: true } },
  });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <GoldPortfolioPage />
      </QueryClientProvider>,
    ),
  };
}

function portfolioGetCount() {
  return restApi.apiGet.mock.calls.filter(([url]) => String(url).includes("/gold/portfolio") && !String(url).includes("/trades") && !String(url).includes("/dca")).length;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getPortfolioPerformance.mockResolvedValue({
    window_days: 90,
    start: null,
    end: null,
    points: 0,
    total_value_irt: 0,
    total_cost_irt: 0,
    unpriced_holdings: 0,
    twr_pct: null,
    simple_return_pct: null,
    annualized_volatility_pct: null,
    sharpe_ratio: null,
    sortino_ratio: null,
    max_drawdown_pct: null,
    var_95_pct: null,
    cvar_95_pct: null,
    concentration_pct: null,
    max_drift_pct: null,
    drift_by_class: {},
    benchmarks: {},
    unavailable: {},
  });
  restApi.apiDelete.mockResolvedValue({ success: true });
  restApi.apiPost.mockResolvedValue({ success: true, data: { id: 1, fee_irt: 0, pnl_irt: 0 } });
});

describe("grouped holding soft-delete", () => {
  it("keeps the delete action for a holding that only has holding_ids and deletes every id sequentially", async () => {
    installPortfolio(portfolio([holding({ id: undefined, holding_ids: [7, 8] })]));
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));
    fireEvent.click(await screen.findByRole("button", { name: /حذف دارایی سکه امامی/ }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("۲ ردیف");
    expect(dialog.textContent).toMatch(/همه حذف نرم می‌شوند و معاملات حفظ می‌شوند/);

    fireEvent.click(screen.getByRole("button", { name: "حذف نرم" }));

    await waitFor(() => expect(restApi.apiDelete).toHaveBeenCalledTimes(2));
    expect(restApi.apiDelete.mock.calls.map(([url]) => url)).toEqual([
      "/gold/portfolio/holdings/7",
      "/gold/portfolio/holdings/8",
    ]);
    // force هرگز از UI نمی‌آید
    for (const [url] of restApi.apiDelete.mock.calls) {
      expect(String(url)).not.toMatch(/force/);
    }
  });

  it("translates 409 to 'already deleted', keeps going, and refetches the portfolio", async () => {
    installPortfolio(portfolio([holding({ id: undefined, holding_ids: [7, 8] })]));
    restApi.apiDelete
      .mockRejectedValueOnce(new Error("HTTP 409: holding 7 is soft-deleted"))
      .mockResolvedValueOnce({ success: true });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));
    const before = portfolioGetCount();
    fireEvent.click(await screen.findByRole("button", { name: /حذف دارایی سکه امامی/ }));
    fireEvent.click(screen.getByRole("button", { name: "حذف نرم" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/قبلاً حذف شده/);
    await waitFor(() => expect(restApi.apiDelete).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(portfolioGetCount()).toBeGreaterThan(before));
  });

  it("shows a clear message for 404 and refetches the portfolio", async () => {
    installPortfolio(portfolio([holding()]));
    restApi.apiDelete.mockRejectedValue(new Error("HTTP 404: holding not found"));

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));
    const before = portfolioGetCount();
    fireEvent.click(await screen.findByRole("button", { name: /حذف دارایی سکه امامی/ }));
    fireEvent.click(screen.getByRole("button", { name: "حذف نرم" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/دارایی پیدا نشد/);
    await waitFor(() => expect(portfolioGetCount()).toBeGreaterThan(before));
  });

  it("shows a clear network message instead of leaking the raw error", async () => {
    installPortfolio(portfolio([holding()]));
    restApi.apiDelete.mockRejectedValue(new TypeError("Failed to fetch"));

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));
    fireEvent.click(await screen.findByRole("button", { name: /حذف دارایی سکه امامی/ }));
    fireEvent.click(screen.getByRole("button", { name: "حذف نرم" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/ارتباط با سرور برقرار نشد/);
    expect(alert.textContent).not.toMatch(/Failed to fetch/);
  });
});

describe("trade recording with a fresh holding id", () => {
  async function openSellDialog() {
    const rendered = renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));
    fireEvent.click(await screen.findByRole("button", { name: /ثبت فروش برای سکه امامی/ }));
    return { dialog: await screen.findByRole("dialog"), client: rendered.client };
  }

  it("posts the id that came from the current /portfolio payload and never sends force", async () => {
    installPortfolio(portfolio([holding()]));
    await openSellDialog();

    fireEvent.change(screen.getByLabelText("تعداد فروش"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("قیمت فروش (تومان)"), { target: { value: "60000000" } });
    fireEvent.click(screen.getByRole("button", { name: "ثبت فروش" }));

    await waitFor(() => expect(restApi.apiPost).toHaveBeenCalledTimes(1));
    const [url, body] = restApi.apiPost.mock.calls[0];
    expect(url).toBe("/gold/portfolio/trades");
    expect(body).toMatchObject({
      symbol: "IR_COIN_EMAMI",
      action: "sell",
      quantity: 1,
      price: 60_000_000,
      amount_irt: 60_000_000,
      holding_id: 7,
    });
    expect(JSON.stringify(body)).not.toMatch(/force/);
  });

  it("refuses to post a holding_id that is no longer in the fresh portfolio", async () => {
    installPortfolio(portfolio([holding()]));
    const { client } = await openSellDialog();

    // refetch با ردیف تازه: همان نماد، ولی id جدید
    installPortfolio(portfolio([holding({ id: 99, holding_ids: [99] })]));
    await act(async () => {
      await client.invalidateQueries({ queryKey: ["gold", "portfolio"] });
    });
    await waitFor(() => expect(portfolioGetCount()).toBeGreaterThan(1));

    fireEvent.change(screen.getByLabelText("تعداد فروش"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("قیمت فروش (تومان)"), { target: { value: "60000000" } });
    fireEvent.click(screen.getByRole("button", { name: "ثبت فروش" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/لیست پورتفو تغییر کرده/);
    expect(restApi.apiPost).not.toHaveBeenCalled();
  });

  it("maps 409 to a readable message and refetches the portfolio", async () => {
    installPortfolio(portfolio([holding()]));
    restApi.apiPost.mockRejectedValue(new Error("HTTP 409: holding is soft-deleted"));

    await openSellDialog();
    const before = portfolioGetCount();
    fireEvent.change(screen.getByLabelText("تعداد فروش"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("قیمت فروش (تومان)"), { target: { value: "60000000" } });
    fireEvent.click(screen.getByRole("button", { name: "ثبت فروش" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/قبلاً حذف شده/);
    await waitFor(() => expect(portfolioGetCount()).toBeGreaterThan(before));
  });

  it("maps 404 to a readable message and refetches the portfolio", async () => {
    installPortfolio(portfolio([holding()]));
    restApi.apiPost.mockRejectedValue(new Error("HTTP 404: holding not found"));

    await openSellDialog();
    const before = portfolioGetCount();
    fireEvent.change(screen.getByLabelText("تعداد فروش"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("قیمت فروش (تومان)"), { target: { value: "60000000" } });
    fireEvent.click(screen.getByRole("button", { name: "ثبت فروش" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/دارایی پیدا نشد/);
    await waitFor(() => expect(portfolioGetCount()).toBeGreaterThan(before));
  });
});

describe("null-safe portfolio numbers", () => {
  it("renders unknown values as an em-dash and never as zero", async () => {
    installPortfolio(
      portfolio(
        [holding({ current_price: null, current_value: null, pnl_irt: null, pnl_pct: null })],
        { priced_cost: null, unpriced_holdings: 1 },
      ),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));

    const nameCell = await screen.findByText("سکه امامی");
    const cells = Array.from(nameCell.closest("tr")!.children) as HTMLElement[];
    expect(cells[3].textContent).toBe("—");
    expect(cells[4].textContent).toBe("—");
    expect(cells[5].textContent).toBe("— (—)");

    // هزینهٔ قیمت‌دار نامعلوم است ⇒ «—»، نه ۰
    const pnlCard = screen.getAllByText("P&L")[0].closest("div")!.parentElement!;
    expect(pnlCard.textContent).toContain("سرمایهٔ قیمت‌دار: —");
    expect(pnlCard.textContent).not.toContain("NaN");
  });

  it("shows the server total (not a client-side sum) when one holding is unpriced", async () => {
    installPortfolio(
      portfolio(
        [
          holding(),
          holding({
            id: 8,
            holding_ids: [8],
            symbol: "IR_GOLD_18K",
            display_name: "طلای ۱۸ عیار",
            current_price: null,
            current_value: null,
            pnl_irt: null,
            pnl_pct: null,
          }),
        ],
        { priced_cost: 80_000_000, unpriced_holdings: 1 },
      ),
    );
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));

    await screen.findByText("طلای ۱۸ عیار");
    // total_pnl از سرور ۲۰٬۰۰۰٬۰۰۰ است؛ جمع دوباره با null نباید صفر شود.
    const card = screen.getAllByText("P&L")[0].closest("div")!.parentElement!;
    expect(card.textContent).toContain("۲۰٬۰۰۰٬۰۰۰");
    expect(card.textContent).not.toContain("NaN");
  });
});
