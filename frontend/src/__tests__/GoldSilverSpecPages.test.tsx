import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// ── مرز تست ─────────────────────────────────────────────────────────────────
// صفحه‌ها را کامل رندر می‌کنیم تا مطمئن شویم همان پوستهٔ خوانندهٔ قواعد API
// (AssistantRulesPanel) در تب پیش‌فرض سوار می‌شود؛ خود پوسته و کارت در
// AssistantRulesPanel.test.tsx و gold-silver-spec.test.ts آزموده می‌شوند.
vi.mock("@/components/gold/SpecRulesCard", () => ({
  __esModule: true,
  default: () => <div data-testid="spec-rules-card" />,
  AssistantRulesPanel: () => <div data-testid="assistant-rules-panel" />,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/markets/gold",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    section: ({ children }: { children?: React.ReactNode }) => <section>{children}</section>,
  },
}));

vi.mock("@/hooks/useWebSocket", () => ({
  useMarketWebSocket: () => ({ prices: new Map(), connected: false, error: null }),
}));

// هیچ داده‌ای از شبکه نمی‌آید؛ صفحه باید با پاسخ‌های خالی هم رندر شود.
vi.mock("@/lib/api", () => ({
  apiGet: vi.fn(async () => ({ success: true, data: { items: [], total: 0 } })),
  extractArray: (payload: unknown) => {
    const data = (payload as { data?: unknown } | undefined)?.data as
      | { items?: unknown[] }
      | undefined;
    return Array.isArray(data?.items) ? data.items : [];
  },
  AUTH_STATE_CLEARED_EVENT: "auth:state-cleared",
  apiPost: vi.fn(async () => ({ success: true })),
  apiPut: vi.fn(async () => ({ success: true })),
  apiDelete: vi.fn(async () => ({ success: true })),
}));

// زیرکامپوننت‌های سنگین نقره (نمودار و تب‌ها) در جای خودشان تست می‌شوند.
vi.mock("@/app/markets/silver/components/PriceChart", () => ({
  default: () => <div data-testid="silver-price-chart" />,
}));
vi.mock("@/app/markets/silver/components/ForecastTab", () => ({
  default: () => <div data-testid="silver-forecast-tab" />,
}));
vi.mock("@/app/markets/silver/components/BacktestTab", () => ({
  default: () => <div data-testid="silver-backtest-tab" />,
}));
vi.mock("@/app/markets/silver/components/MlTab", () => ({
  default: () => <div data-testid="silver-ml-tab" />,
}));

import GoldPage from "@/app/markets/gold/page";
import SilverPage from "@/app/markets/silver/page";

function renderPage(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("صفحه‌های طلا و نقره — مصرف قواعد از API", () => {
  it("صفحهٔ طلا در تب پیش‌فرض پوستهٔ قواعد را سوار می‌کند", async () => {
    renderPage(<GoldPage />);
    expect(await screen.findByTestId("assistant-rules-panel")).toBeTruthy();
  });

  it("صفحهٔ نقره در تب «نمای کلی» پوستهٔ قواعد را سوار می‌کند", async () => {
    renderPage(<SilverPage />);
    expect(await screen.findByTestId("assistant-rules-panel")).toBeTruthy();
  });
});
