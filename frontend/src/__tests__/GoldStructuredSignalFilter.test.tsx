/**
 * صفحهٔ طلا — هم‌ترازی فیلتر §۲۶ با موتور سمت سرور.
 *
 * این تست از بیرون (رندر واقعی صفحه) می‌سنجد که:
 *  ۱. سطوحی که کارت سیگنال نشان می‌دهد از **همان** کف‌های سروشدهٔ §۲۶ عبور می‌کنند
 *     (RR ≥ ۲ و سود خالص ≥ ۲٪) — عدد نمایش‌داده‌شده از DOM خوانده و با همان تابع
 *     `evaluateTrade`ی که صفحه استفاده می‌کند دوباره سنجیده می‌شود؛
 *  ۲. برنامهٔ خام قانون (۲×ATR) که این کف‌ها را رد می‌کند، «سیگنال» نامیده نمی‌شود
 *     و حکمش با نتیجهٔ فیلتر یکی است؛
 *  ۳. آستانه‌ها از پاسخ API می‌آیند، نه از یک ثابت در بستهٔ فرانت‌اند؛
 *  ۴. بی‌پاسخ‌ماندن API هیچ عدد آستانه‌ای نمی‌سازد (§۱۳).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  evaluateTrade,
  parseAssistantRules,
  roundTripFeePct,
  type AssistantRules,
  type TradeDirection,
} from "@/lib/gold-silver-spec";
import { ASSISTANT_RULES_PAYLOAD, assistantRulesDraft } from "./fixtures/assistant-rules";

/* ────────────────────────── دادهٔ تست ────────────────────────── */

// ۸۰ روز واقعی‌نما: نوسان ۴٪ روزانه تا ATR و در نتیجه حد ضرر ۲×ATR عدد داشته باشد.
const historyRows = Array.from({ length: 80 }, (_, i) => {
  const close = 5_000_000 + i * 20_000;
  return {
    date: `1405-07-${String(80 - i).padStart(2, "0")}`,
    price_close: close,
    price_high: Math.round(close * 1.02),
    price_low: Math.round(close * 0.98),
  };
});

const apiGetMock = vi.fn(async (url: string) => {
  if (url.startsWith("/brsapi/history/IR_GOLD_18K")) {
    return { data: { items: historyRows } };
  }
  return { success: true, data: { items: [], total: 0 } };
});

const getAssistantRulesMock = vi.fn();

vi.mock("@/lib/api", () => ({
  apiGet: (url: string) => apiGetMock(url),
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

vi.mock("@/lib/goldApi", () => ({
  getAssistantRules: (...args: unknown[]) => getAssistantRulesMock(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/markets/gold",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    section: ({ children }: { children?: ReactNode }) => <section>{children}</section>,
  },
}));

vi.mock("@/hooks/useWebSocket", () => ({
  useMarketWebSocket: () => ({ prices: new Map(), connected: false, error: null }),
}));

import GoldPage from "@/app/markets/gold/page";

/* ────────────────────────── ابزارهای تست ────────────────────────── */

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** «۵٬۰۰۰٬۰۰۰» → 5000000 (ارقام و جداکنندهٔ فارسی). */
function toNumber(text: string | null): number {
  const ascii = (text ?? "")
    .replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)))
    .replace(/[٬,\s]/g, "");
  const value = Number(ascii);
  if (!Number.isFinite(value) || ascii === "") {
    throw new Error(`عدد قابل‌خواندن نبود: ${JSON.stringify(text)}`);
  }
  return value;
}

const faDigits = (value: number, digits = 0) =>
  value.toLocaleString("fa-IR", { maximumFractionDigits: digits });

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{<GoldPage />}</QueryClientProvider>);
}

/** سطوح نمایش‌داده‌شده را از DOM می‌خواند و با فیلتر سروشده دوباره می‌سنجد. */
function readDisplayedTrade(rules: AssistantRules) {
  const entry = toNumber(screen.getByTestId("gold-signal-entry").textContent) * 10;
  const stop = toNumber(screen.getByTestId("gold-signal-stop").textContent) * 10;
  const requiredTarget = toNumber(screen.getByTestId("gold-signal-required-target").textContent) * 10;
  const ruleTarget = toNumber(screen.getByTestId("gold-signal-rule-target").textContent) * 10;
  const costPct = roundTripFeePct(rules, "commodity_fund") as number;
  const direction: TradeDirection = stop > entry ? "short" : "long";
  const judge = (target: number) =>
    evaluateTrade({ entry, target, stop, costPct, direction, filter: rules.signal_filter });
  return { entry, stop, requiredTarget, costPct, direction, required: judge(requiredTarget), rule: judge(ruleTarget) };
}

const RETRY_TIMEOUT = { timeout: 5000 };

describe("صفحهٔ طلا — کارت سیگنال با فیلتر §۲۶ موتور سمت سرور", () => {
  beforeEach(() => {
    apiGetMock.mockClear();
    getAssistantRulesMock.mockReset();
  });

  it("هدف نمایش‌داده‌شده هر دو کف سروشده را رد می‌کند و برنامهٔ خام قانون را «سیگنال» نمی‌نامد", async () => {
    const rules = parseAssistantRules(ASSISTANT_RULES_PAYLOAD);
    getAssistantRulesMock.mockResolvedValue(rules);
    renderPage();

    await screen.findByTestId("gold-signal-filter", undefined, RETRY_TIMEOUT);

    // آستانه‌ها با همان متن و همان عدد پاسخ API نمایش داده می‌شوند.
    const thresholds = screen.getByTestId("gold-signal-filter-thresholds").textContent ?? "";
    expect(thresholds).toContain(`سود خالص ≥ ${faDigits(rules.signal_filter.min_net_profit_pct)}٪`);
    expect(thresholds).toContain(`RR ≥ ${faDigits(rules.signal_filter.min_risk_reward)}`);

    const shown = readDisplayedTrade(rules);

    // ۱) هدف پیشنهادی صفحه از فیلتر عبور می‌کند: RR ≥ ۲ و سود خالص ≥ ۲٪.
    //    (تحمل خطای گِرد‌کردن نمایش در تومان.)
    expect(shown.required.netProfitPct).toBeGreaterThanOrEqual(
      rules.signal_filter.min_net_profit_pct - 1e-3,
    );
    expect(shown.required.riskReward).toBeGreaterThanOrEqual(rules.signal_filter.min_risk_reward - 1e-3);
    expect(shown.required.verdict).not.toBe("reject");

    // ۲) هدف خام قانون (۲×ATR) از فیلتر رد می‌شود و صفحه هم همان حکم را می‌دهد.
    expect(shown.rule.verdict).toBe("reject");
    const verdict = screen.getByTestId("gold-signal-filter-verdict").textContent ?? "";
    expect(verdict).toContain("سیگنال صادر نشد");
    expect(screen.getByTestId("gold-signal-rule-target-verdict").textContent).toContain("ریسک/ریوارد");
  });

  it("با سخت‌ترشدن آستانهٔ سروشده، هدف نمایش‌داده‌شده هم سخت‌تر می‌شود (عدد از API، نه از بستهٔ فرانت‌اند)", async () => {
    const draft = assistantRulesDraft();
    draft.signal_filter.min_net_profit_pct = 6;
    draft.signal_filter.min_risk_reward = 4;
    const strict = parseAssistantRules(draft);
    getAssistantRulesMock.mockResolvedValue(strict);
    renderPage();

    await screen.findByTestId("gold-signal-filter", undefined, RETRY_TIMEOUT);

    const thresholds = screen.getByTestId("gold-signal-filter-thresholds").textContent ?? "";
    expect(thresholds).toContain(`سود خالص ≥ ${faDigits(6)}٪`);
    expect(thresholds).toContain(`RR ≥ ${faDigits(4)}`);

    const shown = readDisplayedTrade(strict);
    expect(shown.required.netProfitPct).toBeGreaterThanOrEqual(6 - 1e-3);
    expect(shown.required.riskReward).toBeGreaterThanOrEqual(4 - 1e-3);
  });

  it("اگر آستانه‌ها نیاید، هیچ عدد آستانه‌ای نشان داده نمی‌شود (§۱۳)", async () => {
    getAssistantRulesMock.mockRejectedValue(new Error("HTTP 500: boom"));
    renderPage();

    // تا خطای واقعی سرویس برسد (react-query یک بار retry می‌کند).
    await waitFor(
      () =>
        expect(screen.getByTestId("gold-signal-filter-unavailable").textContent).toContain(
          "HTTP 500: boom",
        ),
      { timeout: RETRY_TIMEOUT.timeout },
    );
    expect(screen.queryByTestId("gold-signal-filter-thresholds")).toBeNull();
    expect(screen.queryByTestId("gold-signal-required-target")).toBeNull();
    // سطوح قانون ATR می‌مانند، ولی هیچ حکم یا آستانه‌ای به آن‌ها نمی‌چسبد.
    expect(screen.getByTestId("gold-signal-rule-target")).toBeTruthy();
  });
});
