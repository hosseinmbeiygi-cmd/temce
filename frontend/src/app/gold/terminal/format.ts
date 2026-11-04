import { formatAsOf } from "@/components/gold/DataTrustBadge";
import type { Phase1Quality } from "@/types/phase1";

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export const MISSING = "—";

export function faDigits(value: string): string {
  return value.replace(/\d/g, (digit) => FA_DIGITS[Number(digit)]);
}

/** عدد با جداکنندهٔ هزارگان فارسی «٬»، ممیز «٫» و ارقام فارسی؛ null ⇒ «—». */
export function faNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return MISSING;
  const grouped = value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return faDigits(grouped).replace(/,/g, "٬").replace(/\./g, "٫");
}

/** درصد علامت‌دار: +۱٫۲۵٪ / −۰٫۸۴٪ / — */
export function faPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return MISSING;
  if (value === 0) return `${faNumber(0, digits)}٪`;
  const sign = value > 0 ? "+" : "−";
  return `${sign}${faNumber(Math.abs(value), digits)}٪`;
}

/** مبلغ علامت‌دار (برای حباب/تغییر)؛ null ⇒ «—». */
export function faSignedAmount(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return MISSING;
  if (value === 0) return faNumber(0, digits);
  const sign = value > 0 ? "+" : "−";
  return `${sign}${faNumber(Math.abs(value), digits)}`;
}

/** زمان منبع؛ رشتهٔ نامعتبر ⇒ null تا UI «نامشخص» بگذارد. */
export function sourceTime(asOf: string | null | undefined): string | null {
  return formatAsOf(asOf);
}

export function gapTitle(gaps: string[] | null | undefined): string | undefined {
  const items = (gaps ?? []).filter(Boolean);
  return items.length > 0 ? items.join("؛ ") : undefined;
}

/** رنگ تغییر قیمت (بالا سبز، پایین قرمز). */
export function changeTone(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "text-zinc-400";
  return value > 0 ? "text-emerald-300" : "text-rose-300";
}

/** رنگ حباب (حباب مثبت هشدار، تخفیف سبز). */
export function bubbleTone(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "text-zinc-400";
  return value > 0 ? "text-rose-300" : "text-emerald-300";
}

export const QUALITY_LABEL: Record<Phase1Quality, string> = {
  LIVE: "زنده",
  DELAYED: "کهنه",
  SAMPLE: "نمونه",
  EDUCATIONAL: "آموزشی",
  NO_DATA: "ناموجود",
};

export function navDateLabel(date: string | null, time: string | null): string {
  if (!date) return MISSING;
  const stamp = time ? `${date} ${time.slice(0, 5)}` : date;
  return faDigits(stamp.replace(/-/g, "/"));
}
