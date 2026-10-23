"use client";

import { useQuery } from "@tanstack/react-query";
import { getAssistantRules } from "@/lib/goldApi";
import {
  AssistantRulesError,
  parseAssistantRules,
} from "@/lib/gold-silver-spec";
import type { AssistantRules } from "@/lib/gold-silver-spec";

export interface AssistantRulesState {
  /** `null` تا وقتی پاسخ معتبر نرسیده — هیچ عدد پیش‌فرضی ساخته نمی‌شود. */
  rules: AssistantRules | null;
  isLoading: boolean;
  /** پیام خطای قابل‌نمایش؛ صفحه باید صریحاً نشانش دهد، نه اینکه عدد جعل کند. */
  error: string | null;
}

/**
 * قواعد سروشدهٔ دستیار طلا و نقره را می‌خواند.
 *
 * صفحه‌های طلا و نقره هر دو از همین هوک استفاده می‌کنند تا آستانهٔ فیلتر (§۲۶)،
 * تعرفه (§۲۷.۱) و ساعت بازار (§۲۷.۳) یک منبع داشته باشند: `acceptance.yaml`
 * سمت سرور — همان منبعی که گیت `signal_decision_engine` از آن می‌خواند.
 *
 * پاسخ API باید сво函数아니 valid؛ اگر پیکربندی ناقص برگردد،
 * ``parseAssistantRules`` خطای صریح می‌دهد (§۱۳).
 */
export function useAssistantRules(): AssistantRulesState {
  const query = useQuery({
    queryKey: ["gold-assistant-rules"],
    queryFn: getAssistantRules,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  let rules: AssistantRules | null = null;
  let error: string | null = null;

  if (query.data != null) {
    try {
      rules = parseAssistantRules(query.data);
    } catch (e) {
      rules = null;
      error =
        e instanceof Error ? e.message : String(e);
    }
  } else if (query.error != null) {
    error =
      query.error instanceof Error
        ? query.error.message
        : String(query.error);
  }

  return { rules, isLoading: query.isLoading, error };
}
