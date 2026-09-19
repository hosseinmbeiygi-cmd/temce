/**
 * 🧮 Fund NAV Engine — Types + Pure Helpers (صفحه صندوق).
 *
 * لایه نمایش برای خروجی `/funds/v2/nav/*`:
 *   - سه بُعد وضعیت تطبیق جدا نگه داشته می‌شود (مقایسه‌پذیری/اعتبار مرجع/اختلاف).
 *   - هیچ محاسبه مالی در UI انجام نمی‌شود؛ فقط قالب‌بندی و برچسب.
 */

export type NavQuality = "COMPLETE" | "ESTIMATED" | "PARTIAL" | "BLOCKED";
export type ComparabilityStatus = "COMPARABLE" | "NOT_COMPARABLE" | "INCOMPLETE";
export type ReferenceStatus = "VALID" | "STALE" | "INVALID";
export type DiffStatus = "MATCHED" | "WARNING" | "BREACH";
export type BreakLifecycle =
  | "OPEN"
  | "TRIAGED"
  | "INVESTIGATING"
  | "RESOLVED"
  | "ACCEPTED"
  | "ESCALATED";

export interface FundNavPosition {
  instrument_symbol: string | null;
  instrument_name: string | null;
  holding_type: string;
  quantity: number | null;
  price: number | null;
  price_source: string | null;
  price_at: string | null;
  value: number | null;
  weight_pct: number | null;
  quality: string | null;
  reported_market_value: number | null;
  note: string | null;
}

export interface FundNavRun {
  run_id: number;
  fund_id: string;
  valuation_date: string;
  nav_type: string;
  mode?: string;
  quality_status: NavQuality | string;
  coverage_pct: number | null;
  units_outstanding: number | null;
  total_assets?: number | null;
  total_liabilities?: number | null;
  net_assets: number | null;
  nav_per_unit: number | null;
  positions_count?: number | null;
  holdings_period?: string | null;
  input_hash?: string | null;
  engine_version?: string | null;
  policy_version?: string | null;
  created_at?: string | null;
  positions?: FundNavPosition[];
}

export interface FundNavReconciliation {
  recon_run_id: number;
  nav_type: string;
  valuation_date: string;
  comparability_status: ComparabilityStatus | string;
  reference_status: ReferenceStatus | string;
  diff_status: DiffStatus | string | null;
  internal_nav: number | null;
  reference_nav: number | null;
  abs_diff: number | null;
  bps_diff: number | null;
  threshold_version?: string | null;
  created_at?: string | null;
}

export interface FundNavBreak {
  break_id: number;
  fund_id: string;
  recon_run_id: number;
  lifecycle: BreakLifecycle | string;
  severity: string;
  owner: string | null;
  opened_at: string | null;
  resolved_at: string | null;
  sla_due_at: string | null;
  notes: string | null;
}

export interface FundNavDashboard {
  fund_id: string;
  latest_run: FundNavRun | null;
  recent_runs: FundNavRun[];
  latest_reconciliation: FundNavReconciliation | null;
  reconciliation_history: FundNavReconciliation[];
  open_breaks: FundNavBreak[];
  engine_version: string;
}

// ── Labels ──────────────────────────────────────────────────────────────────

export const QUALITY_LABELS: Record<string, string> = {
  COMPLETE: "کامل",
  ESTIMATED: "تخمینی",
  PARTIAL: "ناقص",
  BLOCKED: "مسدود",
};

export const COMPARABILITY_LABELS: Record<string, string> = {
  COMPARABLE: "قابل مقایسه",
  NOT_COMPARABLE: "غیرقابل مقایسه",
  INCOMPLETE: "ورودی ناقص",
};

export const REFERENCE_LABELS: Record<string, string> = {
  VALID: "معتبر",
  STALE: "کهنه",
  INVALID: "نامعتبر",
};

export const DIFF_LABELS: Record<string, string> = {
  MATCHED: "منطبق",
  WARNING: "هشدار",
  BREACH: "مغایرت",
};

export const BREAK_LIFECYCLE_LABELS: Record<string, string> = {
  OPEN: "باز",
  TRIAGED: "دسته‌بندی‌شده",
  INVESTIGATING: "در بررسی",
  RESOLVED: "رفع‌شده",
  ACCEPTED: "پذیرفته‌شده",
  ESCALATED: "ارجاع‌شده",
};

// ── Pure helpers ────────────────────────────────────────────────────────────

export type Tone = "pos" | "warn" | "neg" | "default";

export function qualityTone(quality: string | null | undefined): Tone {
  switch (quality) {
    case "COMPLETE":
      return "pos";
    case "ESTIMATED":
      return "warn";
    case "PARTIAL":
      return "warn";
    case "BLOCKED":
      return "neg";
    default:
      return "default";
  }
}

export function diffTone(status: string | null | undefined): Tone {
  switch (status) {
    case "MATCHED":
      return "pos";
    case "WARNING":
      return "warn";
    case "BREACH":
      return "neg";
    default:
      return "default";
  }
}

export function referenceTone(status: string | null | undefined): Tone {
  switch (status) {
    case "VALID":
      return "pos";
    case "STALE":
      return "warn";
    case "INVALID":
      return "neg";
    default:
      return "default";
  }
}

export function formatBps(bps: number | null | undefined): string {
  if (bps === null || bps === undefined) return "—";
  const sign = bps > 0 ? "+" : "";
  return `${sign}${bps.toFixed(2)} bps`;
}

export function formatNav(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

export function labelOf(
  map: Record<string, string>,
  key: string | null | undefined
): string {
  if (!key) return "—";
  return map[key] ?? key;
}

export function hasOpenBreach(dashboard: FundNavDashboard | undefined | null): boolean {
  if (!dashboard) return false;
  return (dashboard.open_breaks ?? []).some(
    (b) => b.lifecycle !== "RESOLVED" && b.lifecycle !== "ACCEPTED"
  );
}
