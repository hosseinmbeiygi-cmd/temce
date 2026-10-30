// F10 — سطح UI: تب‌های layout، کلاینت مشترک صفحهٔ tokens، و حذف دارایی.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("next/navigation", () => ({ usePathname: () => "/gold" }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// ── layout ────────────────────────────────────────────────────────────
vi.mock("@/components/gold/LiveSignalBanner", () => ({
  LiveSignalBanner: () => <div data-testid="signal-banner" />,
}));
vi.mock("@/components/gold/PWAProvider", () => ({
  PWAProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock("@/components/gold/NativeBridge", () => ({ NativeBridge: () => null }));
vi.mock("@/hooks/useGoldWS", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/hooks/useGoldWS")>()) as object),
  useGoldWS: () => ({
    state: "open",
    connected: true,
    lastMessageAt: Date.now(),
    ageSeconds: 3,
    stale: false,
    lastHot: null,
  }),
}));

import GoldLayout from "@/app/gold/layout";

// ── goldApi (کلاینت مشترک) ────────────────────────────────────────────
const api = vi.hoisted(() => ({
  getApiTokens: vi.fn(),
  revokeApiToken: vi.fn(),
  createApiToken: vi.fn(),
  getPortfolioPerformance: vi.fn(),
  capturePortfolioSnapshot: vi.fn(),
}));
vi.mock("@/lib/goldApi", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/goldApi")>()) as object),
  ...api,
}));

const restApi = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiDelete: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...((await importOriginal<typeof import("@/lib/api")>()) as object),
  ...restApi,
}));

import GoldTokensPage from "@/app/gold/tokens/page";
import GoldPortfolioPage from "@/app/gold/portfolio/page";

function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const holding = (overrides: Record<string, unknown> = {}) => ({
  id: 7,
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

beforeEach(() => {
  vi.clearAllMocks();
  restApi.apiGet.mockImplementation(async (url: string) => {
    if (url.includes("/gold/telegram/status")) {
      return { success: true, data: { is_operational: false, bot_configured: false, default_chat_id_set: false, enabled: false } };
    }
    if (url.includes("/gold/portfolio/trades")) return { success: true, data: [] };
    if (url.includes("/gold/portfolio/dca")) return { success: true, data: [] };
    if (url.includes("/gold/portfolio/performance")) throw new Error("not under test");
    return { success: true, data: { total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, holdings: [], snapshot_at: null } };
  });
  api.getPortfolioPerformance.mockResolvedValue({
    window_days: 90, start: null, end: null, points: 0, total_value_irt: 0, total_cost_irt: 0,
    unpriced_holdings: 0, twr_pct: null, simple_return_pct: null, annualized_volatility_pct: null,
    sharpe_ratio: null, sortino_ratio: null, max_drawdown_pct: null, var_95_pct: null,
    cvar_95_pct: null, concentration_pct: null, max_drift_pct: null, drift_by_class: {},
    benchmarks: {}, unavailable: {},
  });
  api.getApiTokens.mockResolvedValue([]);
});

describe("gold layout tabs (F8 review)", () => {
  it("shows all destinations on desktop but only the primary five in the mobile bottom bar", async () => {
    renderWithQuery(
      <GoldLayout>
        <p>content</p>
      </GoldLayout>,
    );
    // دسکتاپ: ۱۸ تب (۱۵ تب قبلی + «میز داده» + «پوشش بازار»)
    const desktop = await screen.findAllByRole("link", { name: /آتی IME|Antigravity|دستیار/ });
    expect(desktop.length).toBeGreaterThan(0);
    const desktopNav = document.querySelector("nav.hidden.md\\:flex");
    expect(desktopNav?.querySelectorAll("a")).toHaveLength(18);

    // موبایل: فقط ۵ مقصد اصلی — قبلاً ۱۵ تا در ۳ سطر ≈۱۳۰px جا می‌شد
    const bottomNav = document.querySelector("nav.fixed.bottom-0");
    expect(bottomNav?.querySelectorAll("a")).toHaveLength(5);
  });

  it("reports the live socket state from the hook, not from a fixed timer", async () => {
    renderWithQuery(
      <GoldLayout>
        <p>content</p>
      </GoldLayout>,
    );
    expect(await screen.findByText(/Live/)).toBeInTheDocument();
    expect(screen.queryByText("Polling")).not.toBeInTheDocument();
  });
});

describe("tokens page uses the shared client (F8)", () => {
  it("lists tokens through goldApi and never through a raw fetch", async () => {
    api.getApiTokens.mockResolvedValue([
      { token_id: "abc1", name: "Telegram Bot", scopes: ["read"], enabled: true, created_at: null, last_used_at: null },
    ]);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    renderWithQuery(<GoldTokensPage />);

    expect(await screen.findByText("Telegram Bot")).toBeInTheDocument();
    expect(api.getApiTokens).toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("asks for confirmation before revoking, and says what breaks", async () => {
    api.getApiTokens.mockResolvedValue([
      { token_id: "abc1", name: "Sheets", scopes: ["read"], enabled: true, created_at: null, last_used_at: null },
    ]);
    api.revokeApiToken.mockResolvedValue(true);
    renderWithQuery(<GoldTokensPage />);

    fireEvent.click(await screen.findByRole("button", { name: /لغو token Sheets/ }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toMatch(/ربات تلگرام|Google Sheets|ابزار خارجی/);
    expect(api.revokeApiToken).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "لغو token" }));
    await waitFor(() => expect(api.revokeApiToken).toHaveBeenCalledWith("abc1"));
  });
});

describe("portfolio asset deletion (F5 / C7)", () => {
  const withHoldings = (holdings: unknown[]) => ({
    success: true,
    data: {
      total_cost: 80_000_000,
      total_value: 100_000_000,
      total_pnl: 20_000_000,
      total_pnl_pct: 25,
      holdings,
      snapshot_at: null,
    },
  });

  it("renders a null pnl_pct as an em-dash instead of crashing on toFixed", async () => {
    restApi.apiGet.mockImplementation(async (url: string) => {
      if (url.includes("/gold/portfolio/trades")) return { success: true, data: [] };
      if (url.includes("/gold/portfolio/dca")) return { success: true, data: [] };
      if (url.includes("/gold/portfolio")) return withHoldings([holding({ current_price: null, current_value: null, pnl_irt: null, pnl_pct: null })]);
      throw new Error("unexpected " + url);
    });

    renderWithQuery(<GoldPortfolioPage />);
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));

    const nameCell = await screen.findByText("سکه امامی");
    const cells = Array.from(nameCell.closest("tr")!.children) as HTMLElement[];
    // ترتیب ستون‌ها: نماد | تعداد | میانگین خرید | قیمت فعلی | ارزش | P&L | حذف
    expect(cells[3].textContent).toBe("—");
    expect(cells[4].textContent).toBe("—");
    expect(cells[5].textContent).toBe("— (—)");
    // هیچ «۰» جعلی نباید ساخته شود
    expect(cells[5].textContent).not.toMatch(/0[.,]0|۰/);
  });

  it("confirms with an explicit warning about the asset's trades before deleting", async () => {
    restApi.apiGet.mockImplementation(async (url: string) => {
      if (url.includes("/gold/portfolio/trades")) return { success: true, data: [] };
      if (url.includes("/gold/portfolio/dca")) return { success: true, data: [] };
      if (url.includes("/gold/portfolio")) return withHoldings([holding()]);
      throw new Error("unexpected " + url);
    });
    restApi.apiDelete.mockResolvedValue({ success: true });

    renderWithQuery(<GoldPortfolioPage />);
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));

    fireEvent.click(await screen.findByRole("button", { name: /حذف دارایی سکه امامی/ }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toMatch(/معامله\u200cهای این دارایی هم تحت\u200cتأثیرند/);
    expect(restApi.apiDelete).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "حذف نرم" }));
    await waitFor(() => expect(restApi.apiDelete).toHaveBeenCalledWith("/gold/portfolio/holdings/7"));
    // حذف سخت فقط با force — پیش‌فرض نباید force بفرستد
    expect(restApi.apiDelete.mock.calls[0][0]).not.toMatch(/force/);
  });

  it("hides the delete action when the server payload carries no holding id", async () => {
    restApi.apiGet.mockImplementation(async (url: string) => {
      if (url.includes("/gold/portfolio/trades")) return { success: true, data: [] };
      if (url.includes("/gold/portfolio/dca")) return { success: true, data: [] };
      const payload = withHoldings([holding()]);
      (payload.data.holdings as Record<string, unknown>[])[0].id = undefined;
      return payload;
    });

    renderWithQuery(<GoldPortfolioPage />);
    fireEvent.click(await screen.findByRole("button", { name: "نمای کلی" }));

    expect(await screen.findByText("سکه امامی")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /حذف دارایی/ })).not.toBeInTheDocument();
  });
});
