/**
 * Alert-condition builder for the threshold-alerts form (audit F4, 2026-11-28).
 *
 * Extracted from the Alerts page so the exact contract the backend evaluates is a
 * pure, tested function instead of inline JSX logic. Mirrors the server-side
 * `validate_condition` rules: known fields/operators, finite numeric thresholds,
 * and a server/UI-agreed anti-spam cooldown.
 *
 * Units (evaluated server-side against TSETMC raw data):
 * - price → ریال، آخرین معامله (unadjusted)
 * - volume → سهم، حجم تجمعی امروز
 * - rsi → ۰ تا ۱۰۰ (بازهٔ بسته؛ مقدار کاربر اختیاری، پیش‌فرض 30/70)
 * - sma cross → بدون آستانهٔ کاربر (سیگنال بولی eq 1)
 */

export type AlertCondition = Record<string, unknown>;

export type ConditionResult =
  | { ok: true; condition: AlertCondition }
  | { ok: false; error: "THRESHOLD_REQUIRED" | "RSI_RANGE" };

export interface ThresholdMeta {
  /** Field label shown above the input. */
  label: string;
  /** Unit/semantics hint shown under the input. */
  hint: string;
  /** Cross alerts carry no user threshold — the scheduler computes a boolean. */
  hide?: boolean;
  /** Input placeholder. */
  placeholder: string;
}

export const THRESHOLD_META: Record<string, ThresholdMeta> = {
  price_above: {
    label: "آستانهٔ قیمت",
    hint: "واحد: ریال — آخرین قیمت معاملهٔ TSETMC (خام/تعدیل‌نشده). مثال: ۵۰۰۰۰ ریال = ۵٬۰۰۰ تومان",
    placeholder: "مثلاً ۵۰۰۰۰ (ریال)",
  },
  price_below: {
    label: "آستانهٔ قیمت",
    hint: "واحد: ریال — آخرین قیمت معاملهٔ TSETMC (خام/تعدیل‌نشده). مثال: ۵۰۰۰۰ ریال = ۵٬۰۰۰ تومان",
    placeholder: "مثلاً ۵۰۰۰۰ (ریال)",
  },
  volume_above: {
    label: "آستانهٔ حجم",
    hint: "واحد: سهم — حجم تجمعی معاملات امروز",
    placeholder: "مثلاً ۱۰۰۰۰۰۰۰ (سهم)",
  },
  rsi_oversold: {
    label: "آستانهٔ RSI اشباع فروش",
    hint: "عددی بین ۰ تا ۱۰۰؛ خالی بگذارید تا پیش‌فرض ۳۰ استفاده شود",
    placeholder: "پیش‌فرض ۳۰ — مثلاً ۲۵",
  },
  rsi_overbought: {
    label: "آستانهٔ RSI اشباع خرید",
    hint: "عددی بین ۰ تا ۱۰۰؛ خالی بگذارید تا پیش‌فرض ۷۰ استفاده شود",
    placeholder: "پیش‌فرض ۷۰ — مثلاً ۷۵",
  },
  cross_above_sma: {
    label: "عبور از میانگین به بالا",
    hint: "بدون آستانهٔ عددی — عبور قیمت از میانگین ۲۰ روزه به بالا خودکار تشخیص داده می‌شود",
    hide: true,
    placeholder: "—",
  },
  cross_below_sma: {
    label: "عبور از میانگین به پایین",
    hint: "بدون آستانهٔ عددی — عبور قیمت از میانگین ۲۰ روزه به پایین خودکار تشخیص داده می‌شود",
    hide: true,
    placeholder: "—",
  },
};

export function thresholdMeta(alertType: string): ThresholdMeta {
  return THRESHOLD_META[alertType] ?? THRESHOLD_META.price_above;
}

/**
 * Build the condition document exactly as the backend evaluator expects it.
 * Branch order mirrors the original page logic (cross checks before the generic
 * "below" → lte mapping, since "cross_below_sma" also contains "below").
 */
export function buildAlertCondition(alertType: string, thresholdInput: string): ConditionResult {
  const parsed = Number.parseFloat(thresholdInput);
  const finite = Number.isFinite(parsed);

  const condition: AlertCondition = { threshold: parsed, operator: "gte", field: "price" };
  if (alertType.includes("rsi")) condition.field = "rsi";
  if (alertType.includes("volume")) condition.field = "volume";

  if (alertType.includes("oversold")) {
    condition.field = "rsi";
    condition.operator = "lte";
    // The user's threshold is honoured; the historical fixed 30 becomes the default.
    condition.threshold = finite ? parsed : 30;
    if (finite && (parsed <= 0 || parsed >= 100)) return { ok: false, error: "RSI_RANGE" };
  } else if (alertType.includes("overbought")) {
    condition.field = "rsi";
    condition.operator = "gte";
    condition.threshold = finite ? parsed : 70;
    if (finite && (parsed <= 0 || parsed >= 100)) return { ok: false, error: "RSI_RANGE" };
  } else if (alertType === "cross_above_sma") {
    condition.field = "sma_cross_above";
    condition.operator = "eq";
    condition.threshold = 1;
  } else if (alertType === "cross_below_sma") {
    condition.field = "sma_cross_below";
    condition.operator = "eq";
    condition.threshold = 1;
  } else if (alertType.includes("below") && !alertType.startsWith("cross_")) {
    condition.operator = "lte";
    if (!finite) return { ok: false, error: "THRESHOLD_REQUIRED" };
  } else if (!finite) {
    return { ok: false, error: "THRESHOLD_REQUIRED" };
  }

  // Anti-spam: don't re-trigger the same alert within 30 minutes (kept in sync with
  // the server default DEFAULT_COOLDOWN_MINUTES).
  condition.cooldown_minutes = 30;
  return { ok: true, condition };
}
