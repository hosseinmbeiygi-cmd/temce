// SIL-05: ورودی نامعتبر مبدل نباید «۰ گرم» تفسیر شود و نباید عدد جعلی بسازد.
export const TROY_OUNCE_GRAMS = 31.1035;

/** گرم از ورودی کاربر: فقط عدد متناهی و بزرگ‌تر از صفر؛ در غیر این صورت null. */
export function parseGramsInput(raw: string | null | undefined): number | null {
  const parsed = Number.parseFloat((raw ?? "").replace(/,/g, "").trim());
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function gramsToUsd(grams: number | null, ounceUsd: number | null | undefined): number | null {
  if (grams === null || ounceUsd === null || ounceUsd === undefined || !Number.isFinite(ounceUsd)) {
    return null;
  }
  return (grams / TROY_OUNCE_GRAMS) * ounceUsd;
}

export function usdToIrr(usdValue: number | null, usdRate: number | null | undefined): number | null {
  if (usdValue === null || usdRate === null || usdRate === undefined || !Number.isFinite(usdRate)) {
    return null;
  }
  return usdValue * usdRate;
}
