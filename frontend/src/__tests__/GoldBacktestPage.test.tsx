// S5/F7 — صفحهٔ بک‌تست: هشدار دائمی، خطای query، و متریک out-of-sample.
//
// واقعیت کد که این تست ثبت می‌کند: `BacktestMetrics` در
// `src/gold_desk/backtest_runner.py:77-81` از قبل `oos_*` را دارد، ولی route
// `/backtest/strategy` (`api.py:534-562`) آن‌ها را در پاسخ **نمی‌گذارد**. پس UI
// باید feature-detect باشد: با فیلد → ستون OOS کنار عدد کل دوره؛ بدون فیلد →
// همان متن «نیست» و هیچ ادعایی ساخته نشود.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const mocks = vi.hoisted(() => ({
  getStrategyBacktest: vi.fn(),
  getBacktest: vi.fn(),
}));

vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...mocks,
}));

import GoldBacktestPage from "@/app/gold/backtest/page";

const fullPeriod = {
  total_return_pct: 18.4,
  buy_hold_return_pct: 11.2,
  alpha_pct: 7.2,
  hit_rate_pct: 66.7,
  max_drawdown_pct: 9.1,
  sharpe_ratio: 1.32,
  n_successful: 4,
  n_trades: 6,
  final_value: 118_400_000,
  warning: null as string | null,
  trades: [] as unknown[],
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <GoldBacktestPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getBacktest.mockResolvedValue({
    signal_days: 12, forward_30d_avg_pct: 3.1, hit_rate_pct: 58,
  });
});

describe("backtest page (F7)", () => {
  it("shows an explicit error when the backtest query fails, instead of rendering nothing", async () => {
    mocks.getStrategyBacktest.mockRejectedValue(new Error("HTTP 500: boom"));
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("محاسبهٔ استراتژی بک‌تست انجام نشد");
  });

  it("keeps the response warning visible and prominent, and never auto-dismisses it", async () => {
    mocks.getStrategyBacktest.mockResolvedValue({
      ...fullPeriod,
      warning: "نمونه کم است: ۲۴ روز معاملاتی برای ۹۰ روز درخواستی",
    });
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("نمونه کم است");
    // «دائمی» یعنی بعد از گذشت زمان هم بماند
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.getByRole("alert").textContent).toContain("نمونه کم است");
  });

  it("renders out-of-sample numbers beside the full-period ones when the API provides them", async () => {
    mocks.getStrategyBacktest.mockResolvedValue({
      ...fullPeriod,
      oos_start: "2026-04-01",
      oos_total_return_pct: 6.1,
      oos_buy_hold_return_pct: 4.0,
      oos_alpha_pct: 2.1,
      oos_max_drawdown_pct: 12.5,
    });
    renderPage();

    // جدول دو ستونه: کل دوره کنار OOS
    expect(await screen.findByRole("table", { name: /بازهٔ آزمایش بیرون‌نمونه/ })).toBeInTheDocument();
    expect(screen.getByText("کل دوره")).toBeInTheDocument();
    expect(screen.getByText("OOS")).toBeInTheDocument();
    // کنارِ عدد کل دوره (۱۸٫۴) باید مقدار OOS (۶٫۱) هم دیده شود
    expect(screen.getByText(/۶\.۱|6\.1/)).toBeInTheDocument();
    expect(screen.getAllByText(/۲۰۲۶-۰۴-۰۱|2026-04-01/).length).toBeGreaterThan(0);
  });

  it("renders null out-of-sample fields as 'نامشخص', never as zero", async () => {
    mocks.getStrategyBacktest.mockResolvedValue({
      ...fullPeriod,
      oos_start: null,
      oos_total_return_pct: null,
      oos_buy_hold_return_pct: null,
      oos_alpha_pct: null,
      oos_max_drawdown_pct: null,
    });
    renderPage();

    const table = await screen.findByRole("table", { name: /بازهٔ آزمایش بیرون‌نمونه/ });
    const unknown = Array.from(table.querySelectorAll("td")).filter((td) => td.textContent === "نامشخص");
    expect(unknown.length).toBeGreaterThanOrEqual(4);
    // هیچ صفر جعلی برای OOS ساخته نشود
    expect(table.textContent).not.toMatch(/\b0(\.0+)?٪/);
  });

  it("states plainly that OOS is absent when the API omits it (feature-detect, no invented numbers)", async () => {
    mocks.getStrategyBacktest.mockResolvedValue(fullPeriod);
    renderPage();

    await screen.findByText(/Buy & Hold/);
    // ادعای صادقانه باید باشد…
    expect(screen.getByText(/متریک جداگانهٔ out-of-sample/)).toBeInTheDocument();
    // …و هیچ عدد OOS جعلی ساخته نشود: تنها کارت‌های عددی، همان هشت عدد کل دوره‌اند
    expect(screen.queryByText(/OOS|بیرون‌نمونه/)).not.toBeInTheDocument();
  });
});
