import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AssistantRulesPanel } from "@/components/gold/SpecRulesCard";
import { parseAssistantRules } from "@/lib/gold-silver-spec";
import {
  ASSISTANT_RULES_PAYLOAD,
  assistantRulesDraft,
  type AssistantRulesDraft,
} from "./fixtures/assistant-rules";

// پاسخ API را می‌دزدیم تا مرز واقعی را بسنجیم: آیا صفحه اعداد را از سرویس
// می‌گیرد یا از نسخهٔ بستهٔ خودش؟
const getAssistantRules = vi.fn();
vi.mock("@/lib/goldApi", () => ({
  getAssistantRules: (...args: unknown[]) => getAssistantRules(...args),
}));

// قالب‌بندی ارقام هم مثل کامپوننت محاسبه می‌شود تا تست به وجود ICU وابسته نباشد
// و در عوض، *مقدار* عددی سروشده را بسنجد.
const fa0 = (n: number) => n.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
const fa = (n: number) => n.toLocaleString("fa-IR", { maximumFractionDigits: 2 });

const RETRY_TIMEOUT = { timeout: 5000 };

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const payloadWith = (patch: (draft: AssistantRulesDraft) => void) => {
  const draft = assistantRulesDraft();
  patch(draft);
  return draft;
};

describe("AssistantRulesPanel — قواعد از API", () => {
  beforeEach(() => {
    getAssistantRules.mockReset();
  });

  it("آستانهٔ §۲۶ را از پاسخ سروشده نشان می‌دهد (۲٪ سود خالص و RR ≥ ۲)", async () => {
    getAssistantRules.mockResolvedValue(parseAssistantRules(ASSISTANT_RULES_PAYLOAD));
    wrap(<AssistantRulesPanel />);

    const badge = await screen.findByTestId("spec-filter-thresholds");
    expect(badge.textContent).toContain(`سود خالص ≥ ${fa0(2)}٪`);
    expect(badge.textContent).toContain(`RR ≥ ${fa0(2)}`);
  });

  it("ساعت بازار، دامنه، تسویه و تعرفهٔ §۲۷.۱ را نشان می‌دهد", async () => {
    getAssistantRules.mockResolvedValue(parseAssistantRules(ASSISTANT_RULES_PAYLOAD));
    wrap(<AssistantRulesPanel />);

    await screen.findByTestId("spec-filter-thresholds");

    // §۲۷.۳ — ساعت‌ها، دامنه و تسویه
    expect(screen.getByText("11:45 → 12:00 → 18:00")).toBeTruthy();
    expect(screen.getByText("11:45 → 12:00 → 15:00")).toBeTruthy();
    expect(screen.getByText("T+1")).toBeTruthy();
    expect(screen.getByText(`±${fa0(10)}٪`)).toBeTruthy();

    // §۲۷.۱ — تعرفهٔ صندوق کالایی و §۲۰ — حرکت ناخالص لازم
    expect(screen.getByText(new RegExp(`رفت‌وبرگشت ${fa(0.24)}٪`))).toBeTruthy();
    expect(screen.getByText(`${fa(2.24)}٪`)).toBeTruthy();
  });

  it("کارت پیش‌فرض با آستانهٔ سروشده «پایش» می‌دهد (W=۳٫۷۶٪ ≥ ۲٪ و RR≈۳ ≥ ۲)", async () => {
    getAssistantRules.mockResolvedValue(parseAssistantRules(ASSISTANT_RULES_PAYLOAD));
    wrap(<AssistantRulesPanel />);

    const verdict = await screen.findByTestId("spec-trade-verdict");
    expect(verdict.textContent).toContain("پایش");
    expect(screen.getByText(fa(3.76))).toBeTruthy(); // کاشی «سود خالص W»
  });

  it("همان ورودی با کف ۴٪ از سرور رد می‌شود ⇒ عدد از API می‌آید، نه از بستهٔ فرانت‌اند", async () => {
    const draft = payloadWith((d) => {
      d.signal_filter.min_net_profit_pct = 4;
    });
    getAssistantRules.mockResolvedValue(parseAssistantRules(draft));
    wrap(<AssistantRulesPanel />);

    const badge = await screen.findByTestId("spec-filter-thresholds");
    expect(badge.textContent).toContain(`سود خالص ≥ ${fa0(4)}٪`);

    const verdict = screen.getByTestId("spec-trade-verdict");
    expect(verdict.textContent).toContain("سیگنال صادر نشد");
    // دلیل، عدد خام سروشده را نام می‌برد و W همان ۳٫۷۶٪ می‌ماند.
    expect(screen.getByText(/سود خالص 3\.76٪ کمتر از حداقل 4٪ است/)).toBeTruthy();
  });

  it("تا رسیدن پاسخ، هیچ عددی نشان نمی‌دهد", () => {
    getAssistantRules.mockReturnValue(new Promise(() => {}));
    wrap(<AssistantRulesPanel />);

    expect(screen.getByTestId("spec-rules-loading")).toBeTruthy();
    expect(screen.queryByTestId("spec-filter-thresholds")).toBeNull();
  });

  it("خطای سرویس ⇒ پیام صریح و بدون آستانهٔ ساختگی (§۱۳)", async () => {
    getAssistantRules.mockRejectedValue(new Error("HTTP 500: boom"));
    wrap(<AssistantRulesPanel />);

    const box = await screen.findByTestId("spec-rules-unavailable", undefined, RETRY_TIMEOUT);
    expect(box.textContent).toContain("HTTP 500: boom");
    expect(screen.queryByTestId("spec-filter-thresholds")).toBeNull();
    expect(screen.queryByText(new RegExp(`≥ ${fa0(2)}٪`))).toBeNull();
  });

  it("پاسخ نامعتبر هم به «در دسترس نیست» تبدیل می‌شود، نه عدد جعلی", async () => {
    getAssistantRules.mockRejectedValue(
      new Error("signal_filter.min_net_profit_pct نامعتبر است: عدد متناهی"),
    );
    wrap(<AssistantRulesPanel />);

    const box = await screen.findByTestId("spec-rules-unavailable", undefined, RETRY_TIMEOUT);
    expect(box.textContent).toContain("min_net_profit_pct");
    expect(screen.queryByText(new RegExp(`≥ ${fa0(2)}٪`))).toBeNull();
  });
});
