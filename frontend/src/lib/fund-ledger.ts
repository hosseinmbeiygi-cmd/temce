/**
 * 🧾 Fund Ledger — Types + Pure Helpers (صفحه صندوق).
 *
 * نمایش تراز آزمایشی و حرکت واحدها؛ هیچ محاسبه مالی در UI انجام نمی‌شود.
 */

import type { Tone } from "@/lib/fund-nav";

export interface LedgerAccountBalance {
  account_code: string;
  account_name: string;
  account_type: string;
  normal_side: string;
  debit: number;
  credit: number;
  balance: number;
}

export interface TrialBalance {
  accounts: LedgerAccountBalance[];
  total_debit: number;
  total_credit: number;
  balanced: boolean;
}

export interface JournalLine {
  account_code: string;
  instrument_symbol: string | null;
  debit_amount: number;
  credit_amount: number;
  quantity_delta: number;
}

export interface JournalEntry {
  entry_id: number;
  event_type: string;
  status: string;
  effective_at: string | null;
  source_system: string | null;
  source_ref_id: string | null;
  idempotency_key: string;
  memo: string | null;
  lines: JournalLine[];
}

export interface UnitMovement {
  movement_id: number;
  movement_date: string;
  movement_type: string;
  units: number;
  price_per_unit: number | null;
  amount: number | null;
  nav_type: string | null;
  reference: string | null;
}

export const MOVEMENT_TYPE_LABELS: Record<string, string> = {
  ISSUE: "صدور",
  REDEEM: "ابطال",
  DISTRIBUTION: "توزیع سود",
  TRANSFER: "انتقال",
  PLEDGE: "توثیق",
  RELEASE: "آزادسازی",
};

export const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  ASSET: "دارایی",
  LIABILITY: "بدهی",
  EQUITY: "حقوق واحدها",
  INCOME: "درآمد",
  EXPENSE: "هزینه",
};

export const ENTRY_STATUS_LABELS: Record<string, string> = {
  POSTED: "ثبت‌شده",
  REVERSED: "برگشت‌خورده",
};

export function accountTone(accountType: string | null | undefined): Tone {
  switch (accountType) {
    case "ASSET":
      return "pos";
    case "LIABILITY":
      return "warn";
    case "EQUITY":
      return "default";
    case "INCOME":
      return "pos";
    case "EXPENSE":
      return "neg";
    default:
      return "default";
  }
}

export function movementTone(movementType: string | null | undefined): Tone {
  switch (movementType) {
    case "ISSUE":
      return "pos";
    case "REDEEM":
      return "warn";
    case "DISTRIBUTION":
      return "default";
    default:
      return "default";
  }
}

export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

export function isBalanced(trial: TrialBalance | null | undefined): boolean {
  return Boolean(trial?.balanced);
}
