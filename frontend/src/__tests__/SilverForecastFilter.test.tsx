/**
 * تب پیش‌بینی نقره — فیلتر §۲۶ روی همان برنامه‌ای که صفحه نشان می‌دهد.
 *
 * از بیرون (رندر واقعی تب) می‌سنجد که:
 *  ۱. آستانه‌ها از پاسخ API می‌آیند (همان `GET /gold/assistant-rules`)؛
 *  ۲. برنامهٔ پیش‌بینی (ورود = قیمت پایه، هدف = میانه، حد ضرر = کف بازه) با همان
 *     `evaluateTrade` سنجیده می‌شود و حکم صفحه با حکم فیلتر یکی است؛
 *  ۳. پیش‌بینی‌ای که کف‌ها را رد می‌کند، «سیگنال» نامیده نمی‌شود؛
 *  ۴. هدف پیشنهادی صفحه خودش هر دو کف را رد می‌کند؛
 *  ۵. بی‌پاسخ‌ماندن API هیچ عدد آستانه‌ای نمی‌سازد (§۱۳).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  evaluateTrade,
  parseAssistantRules,
  roundTripFeePct,
  type AssistantRules,
} from "@/lib/gold-silver-spec";
import { ASSISTANT_RULES_PAYLOAD } from "./fixtures/assistant-rules";

const ANCHOR = 30;

/** نقطهٔ پیش‌بینی افق ۳۰ روزه که تست‌ها با آن برنامه می‌سازند. */
const POINT = {
  date: "2026-10-20",
  p50: 30.3,
  p_lower: 29.4,
  p_upper: 30.9,
  direction_probability_up: 0.6,
};

const apiGetMock = vi.fn(async (url: string) => {
  if (url.startsWith("/brsapi/commodities")) {
    return { success: true, data: [{ symbol: "XAGUSD", price: ANCHOR }] };
  }
  if (url.startsWith("/forecast")) {
    const horizon = Number(new URLSearchParams(url.split("?")[1]).get("horizon"));
    return {
      success: true,
      data: {
        symbol: "xag_usd",
        horizon_days: horizon,
        data_as_of: "2026-10-14",
        model: { name: "xgboost_ensemble", version: "3" },
        forecast: [{ ...POINT }],
        quality: { status: "good", is_stale: false },
        risk: { level: "متوسط", volatility: "0.8" },
        meta: null,
      },
    };
  }
  return { success: true, data: [] };
});

const getAssistantRulesMock = vi.fn();

vi.mock("@/lib/api", () => ({
  apiGet: (url: string) => apiGetMock(url),
  extractArray: (payload: unknown) => {
    if (Array.isArray(payload)) return payload;
    const data = (payload as { data?: unknown } | undefined)?.data;
    if (Array.isArray(data)) return data;
    return Array.isArray((data as { items?: unknown[] } | undefined)?.items)
      ? ((data as { items: unknown[] }).items ?? [])
      : [];
  },
  AUTH_STATE_CLEARED_EVENT: "auth:state-cleared",
  apiPost: vi.fn(async () => ({ success: true })),
  apiPut: vi.fn(async () => ({ success: true })),
  apiDelete: vi.fn(async () => ({ success: true })),
}));

vi.mock("@/lib/goldApi", () => ({
  getAssistantRules: (...args: unknown[]) => getAssistantRulesMock(...args),
}));

import ForecastTab from "@/app/markets/silver/components/ForecastTab";

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

const faDigits = (value: number, digits = 0) =>
  value.toLocaleString("fa-IR", { maximumFractionDigits: digits });

/** عدد نمایش‌داده‌شده (ارقام/جداکنندهٔ فارسی یا لاتین) را می‌خواند. */
const num = (testId: string): number => {
  const el = screen.getByTestId(testId);
  const ascii = (el.textContent ?? "").replace(/[۰-۹]/g, (d) => String(PERSIAN_DIGITS.indexOf(d)));
  const value = Number(ascii.replace(/[٬,\s]/g, ""));
  if (ascii === "" || !Number.isFinite(value)) {
    throw new Error(`${testId} عدد نداد: ${JSON.stringify(el.textContent)}`);
  }
  return value;
};

function renderTab() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ForecastTab />
    </QueryClientProvider>,
  );
}

/**
 * سطوح نمایش‌داده‌شده را از DOM می‌خواند و با فیلتر سروشده دوباره می‌سنجد.
 *
 * `probability` همان `p` پیش‌بینی است که کامپوننت برای صعود (یا آینه‌اش برای
 * نزول) به فیلتر می‌دهد.
 */
function judgeDisplayedPlan(rules: AssistantRules, probability: number) {
  const entry = num("silver-forecast-entry");
  const target = num("silver-forecast-target");
  const stop = num("silver-forecast-stop");
  const costPct = roundTripFeePct(rules, "commodity_fund") as number;
  const direction = stop > entry ? ("short" as const) : ("long" as const);
  const judge = (targetPrice: number) =>
    evaluateTrade({
      entry,
      target: targetPrice,
      stop,
      costPct,
      direction,
      probability: direction === "long" ? probability : 1 - probability,
      filter: rules.signal_filter,
    });
  return {
    entry,
    target,
    stop,
    costPct,
    direction,
    shown: judge(target),
    required: judge(num("silver-forecast-required-target")),
  };
}

const FIND = { timeout: 5000 };

describe("تب پیش‌بینی نقره — گیت §۲۶", () => {
  beforeEach(() => {
    apiGetMock.mockClear();
    getAssistantRulesMock.mockReset();
  });

  it("پیش‌بینی‌ای که کف سود خالص و RR را رد می‌کند، «سیگنال» نامیده نمی‌شود", async () => {
    const rules = parseAssistantRules(ASSISTANT_RULES_PAYLOAD);
    getAssistantRulesMock.mockResolvedValue(rules);
    renderTab();

    await screen.findByTestId("silver-forecast-filter", undefined, FIND);

    const thresholds = screen.getByTestId("silver-forecast-filter-thresholds").textContent ?? "";
    expect(thresholds).toContain(`سود خالص ≥ ${faDigits(rules.signal_filter.min_net_profit_pct)}٪`);
    expect(thresholds).toContain(`RR ≥ ${faDigits(rules.signal_filter.min_risk_reward)}`);

    const plan = judgeDisplayedPlan(rules, POINT.direction_probability_up);
    // حکم نمایش‌داده‌شده با فیلتر سروشده می‌خواند...
    expect(plan.shown.verdict).toBe("reject");
    expect(screen.getByTestId("silver-forecast-filter-verdict").textContent).toContain(
      "سیگنال صادر نشد",
    );
    // ...و خوانش مدل هم بدون برچسب §۲۶ به‌عنوان سیگنال عرضه نمی‌شود.
    expect(screen.getByTestId("silver-forecast-advice").textContent).toContain("سیگنال صادر نشد (§۲۶)");
    const reasons = screen.getByTestId("silver-forecast-filter-reasons").textContent ?? "";
    expect(reasons).toContain("سود خالص");
    expect(reasons).toContain("ریسک/ریوارد");

    // هدف پیشنهادی صفحه (حداقل هدف §۲۶) خودش از فیلتر می‌گذرد.
    expect(plan.required.netProfitPct).toBeGreaterThanOrEqual(
      rules.signal_filter.min_net_profit_pct - 1e-6,
    );
    expect(plan.required.riskReward).toBeGreaterThanOrEqual(
      rules.signal_filter.min_risk_reward - 1e-6,
    );
    expect(plan.required.verdict).not.toBe("reject");
  });

  it("پیش‌بینی‌ای که هر دو کف را رد می‌کند، سیگنال عرضه می‌شود و خوانش مدل هم می‌ماند", async () => {
    const rules = parseAssistantRules(ASSISTANT_RULES_PAYLOAD);
    getAssistantRulesMock.mockResolvedValue(rules);

    // همان ورودی، ولی این بار میانهٔ پیش‌بینی برنامه را از فیلتر می‌گذراند.
    apiGetMock.mockImplementation(async (url: string) => {
      if (url.startsWith("/brsapi/commodities")) {
        return { success: true, data: [{ symbol: "XAGUSD", price: ANCHOR }] };
      }
      const horizon = Number(new URLSearchParams(url.split("?")[1]).get("horizon"));
      return {
        success: true,
        data: {
          symbol: "xag_usd",
          horizon_days: horizon,
          data_as_of: "2026-10-14",
          model: { name: "xgboost_ensemble", version: "3" },
          forecast: [
            { ...POINT, p50: 30.9, p_lower: 29.7, p_upper: 31.5, direction_probability_up: 0.7 },
          ],
          quality: { status: "good", is_stale: false },
          risk: { level: "متوسط", volatility: "0.8" },
          meta: null,
        },
      };
    });

    renderTab();
    await screen.findByTestId("silver-forecast-filter", undefined, FIND);

    const plan = judgeDisplayedPlan(rules, 0.7);
    expect(plan.shown.verdict).toBe("opportunity");
    expect(screen.getByTestId("silver-forecast-filter-verdict").textContent).toContain(
      "بررسی فرصت",
    );
    expect(screen.getByTestId("silver-forecast-advice").textContent).not.toContain("§۲۶");
    expect(screen.queryByTestId("silver-forecast-filter-reasons")).toBeNull();
  });

  it("اگر آستانه‌ها نیاید، هیچ عدد یا حکمی ساخته نمی‌شود (§۱۳)", async () => {
    getAssistantRulesMock.mockRejectedValue(new Error("HTTP 500: boom"));
    renderTab();

    await waitFor(
      () =>
        expect(
          screen.getByTestId("silver-forecast-filter-unavailable").textContent,
        ).toContain("HTTP 500: boom"),
      { timeout: 5000 },
    );
    expect(screen.queryByTestId("silver-forecast-filter-thresholds")).toBeNull();
    expect(screen.queryByTestId("silver-forecast-filter-verdict")).toBeNull();
    expect(screen.getByTestId("silver-forecast-advice").textContent).not.toContain("§۲۶");
  });
});
