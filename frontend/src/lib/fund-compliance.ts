/**
 * 🛡 Fund Compliance — Types + Pure Helpers (صفحه صندوق).
 */

import type { Tone } from "@/lib/fund-nav";

export interface AmlAlert {
  alert_id: number;
  alert_type: string;
  risk_level: string;
  subject_ref: string | null;
  amount: number | null;
  status: string;
  created_at: string | null;
}

export interface StrReport {
  str_id: number;
  subject_ref: string | null;
  reason: string;
  amount: number | null;
  due_at: string | null;
  submitted_at: string | null;
  status: string;
}

export interface TaxItem {
  tax_id: number;
  period_label: string;
  tax_type: string;
  base_amount: number | null;
  rate: number | null;
  tax_amount: number | null;
  exempt: boolean;
  exemption_ref: string | null;
}

export interface Committee {
  committee_id: number;
  committee_type: string;
  members: unknown[];
  charter_ref: string | null;
  is_active: boolean;
}

export interface FofSummary {
  total_value: number;
  circular_value: number;
  valued_positions: number;
  missing_positions: number;
  coverage_pct: number;
}

export interface FofPosition {
  sub_fund_id: string;
  sub_nav_per_unit: number | null;
  units: number | null;
  value: number | null;
  circular_flag: boolean;
}

export interface FofLatest {
  fund_id: string;
  valuation_date: string;
  positions: FofPosition[];
  summary: FofSummary;
}

export interface CsdiBreak {
  break_id: number;
  as_of_date: string;
  internal_units: number | null;
  csdi_units: number | null;
  units_diff: number | null;
  status: string;
}

export const RISK_TONE: Record<string, Tone> = {
  LOW: "pos",
  MEDIUM: "warn",
  HIGH: "neg",
};

export const TAX_TYPE_LABELS: Record<string, string> = {
  TRANSFER_05: "مقطوع ۰.۵٪ نقل‌وانتقال",
  CGT: "مالیات بر عایدی سرمایه",
  DEPOSIT_INTEREST: "سود سپرده",
  VAT: "ارزش افزوده",
  FUND_INCOME: "درآمد صندوق",
};

export const COMMITTEE_LABELS: Record<string, string> = {
  AUDIT: "کمیته حسابرسی",
  RISK: "کمیته ریسک",
  NOMINATION: "کمیته انتصابات",
  VALUATION: "کمیته ارزش‌گذاری",
  OTHER: "سایر",
};

export function riskTone(level: string | null | undefined): Tone {
  if (!level) return "default";
  return RISK_TONE[level] ?? "default";
}

export function circularTone(flag: boolean | null | undefined): Tone {
  return flag ? "neg" : "pos";
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export function hasCircularExposure(latest: FofLatest | null | undefined): boolean {
  if (!latest) return false;
  return (latest.positions ?? []).some((p) => p.circular_flag);
}
