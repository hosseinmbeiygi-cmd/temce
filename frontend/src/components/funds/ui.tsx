"use client";

/**
 * Shared presentational primitives for the funds workspace.
 *
 * Every value here comes from a real endpoint payload — nothing is guessed.
 * `DataTable` derives its columns from the keys the API actually returned,
 * so a tab can never invent a field that the backend does not expose.
 */

import { useMemo } from "react";
import { Inbox, type LucideIcon } from "lucide-react";
import Skeleton from "@/components/Skeleton";

// ── Formatting ──────────────────────────────────────────────────────────────

export function fmt(v: unknown, digits = 0): string {
  const n = typeof v === "number" ? v : Number(v);
  if (v === null || v === undefined || v === "" || !Number.isFinite(n)) return "—";
  return n.toLocaleString("fa-IR", { maximumFractionDigits: digits });
}

/** Compact money: میلیارد/میلیون in Persian digits. */
export function fmtBig(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n) || n === 0) return "—";
  const a = Math.abs(n);
  if (a >= 1e12) return `${(n / 1e12).toLocaleString("fa-IR", { maximumFractionDigits: 2 })} هزار میلیارد`;
  if (a >= 1e9) return `${(n / 1e9).toLocaleString("fa-IR", { maximumFractionDigits: 2 })} میلیارد`;
  if (a >= 1e6) return `${(n / 1e6).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} میلیون`;
  if (a >= 1e3) return `${(n / 1e3).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} هزار`;
  return fmt(n);
}

export function fmtPct(v: unknown, digits = 2): string {
  const n = typeof v === "number" ? v : Number(v);
  if (v === null || v === undefined || !Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : "−"}${Math.abs(n).toLocaleString("fa-IR", { maximumFractionDigits: digits })}٪`;
}

export function fmtDate(v: unknown): string {
  if (!v) return "—";
  const s = String(v).slice(0, 10);
  return s.replace(/-/g, "/");
}

export function fmtDateTime(v: unknown): string {
  if (!v) return "—";
  const s = String(v).replace("T", " ").slice(0, 16);
  return s;
}

/** Latin digits + Latin labels read better in RTL tables, so numbers get their own dir. */
export const numDir = "ltr" as const;

export const toneText = (tone: Tone = "default") =>
  tone === "pos"
    ? "text-accent-emerald"
    : tone === "neg"
      ? "text-accent-rose"
      : tone === "warn"
        ? "text-accent-amber"
        : tone === "accent"
          ? "text-primary-300"
          : "text-surface-100";

export type Tone = "default" | "pos" | "neg" | "warn" | "accent" | "muted";

// ── Chips / badges ──────────────────────────────────────────────────────────

const CHIP_TONES: Record<Tone, string> = {
  default: "bg-surface-700/60 text-surface-200",
  pos: "bg-accent-emerald/15 text-accent-emerald",
  neg: "bg-accent-rose/15 text-accent-rose",
  warn: "bg-accent-amber/15 text-accent-amber",
  accent: "bg-primary-600/20 text-primary-300",
  muted: "bg-surface-800 text-surface-400",
};

export function Chip({ label, tone = "default", icon: Icon, dot }: { label: string; tone?: Tone; icon?: LucideIcon; dot?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-bold ${CHIP_TONES[tone]}`}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />}
      {Icon && <Icon className="w-3 h-3" />}
      {label}
    </span>
  );
}

const FRESHNESS: Record<string, { label: string; tone: Tone }> = {
  live: { label: "زنده", tone: "pos" },
  estimated: { label: "تخمینی", tone: "warn" },
  stale: { label: "کهنه", tone: "neg" },
  ok: { label: "سالم", tone: "pos" },
  partial: { label: " ناقص", tone: "warn" },
  missing: { label: "غایب", tone: "neg" },
};

export function FreshnessChip({ value }: { value?: string | null }) {
  if (!value) return null;
  const meta = FRESHNESS[value] ?? { label: value, tone: "muted" as Tone };
  return <Chip label={meta.label} tone={meta.tone} dot={value === "live"} />;
}

// ── Stat blocks ─────────────────────────────────────────────────────────────

export function Stat({
  label,
  value,
  sub,
  tone = "default",
  numeric = true,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: Tone;
  numeric?: boolean;
  icon?: LucideIcon;
}) {
  return (
    <div className="glass-card p-3 relative overflow-hidden group">
      <div className="flex items-center gap-1.5 mb-1.5">
        {Icon && <Icon className="w-3.5 h-3.5 text-surface-500" />}
        <p className="text-[10px] text-surface-500 leading-tight">{label}</p>
      </div>
      <p
        className={`font-mono text-sm font-bold truncate ${toneText(tone)}`}
        {...(numeric ? { dir: numDir } : {})}
        title={typeof value === "string" || typeof value === "number" ? String(value) : undefined}
      >
        {value ?? "—"}
      </p>
      {sub && <p className="text-[10px] mt-1 text-surface-600 leading-tight">{sub}</p>}
    </div>
  );
}

export function StatGrid({ children, cols = 4 }: { children: React.ReactNode; cols?: 2 | 3 | 4 | 5 | 6 }) {
  const map = { 2: "grid-cols-2", 3: "grid-cols-2 md:grid-cols-3", 4: "grid-cols-2 md:grid-cols-4", 5: "grid-cols-2 md:grid-cols-5", 6: "grid-cols-2 md:grid-cols-3 xl:grid-cols-6" };
  return <div className={`grid gap-3 ${map[cols]}`}>{children}</div>;
}

export function MiniMetric({ label, value, sub, tone = "default" }: { label: string; value?: React.ReactNode; sub?: React.ReactNode; tone?: Tone }) {
  return (
    <div className="bg-surface-800/40 rounded-lg px-3 py-2">
      <p className="text-[9px] text-surface-500 mb-0.5">{label}</p>
      <p className={`font-mono text-xs font-bold ${toneText(tone)}`} dir={numDir}>
        {value ?? "—"}
      </p>
      {sub && <p className="text-[9px] mt-0.5 text-surface-600">{sub}</p>}
    </div>
  );
}

export function MeterBar({ label, value, max = 100, hint }: { label: string; value: number; max?: number; hint?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = pct >= 70 ? "#10b981" : pct >= 45 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="bg-surface-800/40 rounded-lg p-2.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-surface-400">{label}</span>
        <span className="text-[11px] font-mono font-bold" style={{ color }} dir={numDir}>
          {hint ?? value.toFixed(0)}
        </span>
      </div>
      <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

// ── Layout / state helpers ──────────────────────────────────────────────────

export function SectionTitle({ title, desc, actions }: { title: string; desc?: string; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
      <div>
        <h3 className="text-sm font-bold text-surface-100">{title}</h3>
        {desc && <p className="text-[11px] text-surface-500 mt-0.5 leading-relaxed">{desc}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, desc, actions, children, className = "" }: { title: string; desc?: string; actions?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={`glass-card p-4 ${className}`}>
      <SectionTitle title={title} desc={desc} actions={actions} />
      {children}
    </div>
  );
}

export function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full rounded-lg" />
      ))}
    </div>
  );
}

export function Empty({ text = "داده‌ای موجود نیست", hint, icon: Icon = Inbox }: { text?: string; hint?: string; icon?: LucideIcon }) {
  return (
    <div className="py-10 text-center">
      <Icon className="w-8 h-8 text-surface-700 mx-auto" />
      <p className="text-xs font-bold text-surface-400 mt-2">{text}</p>
      {hint && <p className="text-[11px] text-surface-600 mt-1 max-w-md mx-auto leading-relaxed">{hint}</p>}
    </div>
  );
}

export function Failed({ error, onRetry }: { error?: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : typeof error === "string" ? error : "دریافت داده ممکن نشد";
  return (
    <div className="py-8 text-center">
      <span className="material-icons text-2xl text-accent-rose/70">cloud_off</span>
      <p className="text-xs text-accent-rose mt-2">{msg}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 text-[11px] px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 transition-colors">
          تلاش دوباره
        </button>
      )}
    </div>
  );
}

/** A short source-of-truth note under a tab, so the user knows what feeds it. */
export function SourceNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-3 text-[10px] text-surface-600 leading-relaxed border-r-2 border-surface-700/70 pr-2">
      {children}
    </p>
  );
}

// ── Generic table ───────────────────────────────────────────────────────────

const HIDDEN_KEYS = /^(id|fund_id|created_at|updated_at|row_num)$/;

function guessKind(key: string, sample: unknown): "num" | "date" | "time" | "pct" | "text" {
  if (/(_pct|percent|_rate)$/.test(key)) return "pct";
  if (/(date|_day|period)$/.test(key) && typeof sample === "string") return "date";
  if (/(time|_at|timestamp)/.test(key)) return "time";
  if (typeof sample === "number") return "num";
  return "text";
}

const FA_LABELS: Record<string, string> = {
  symbol: "نماد",
  name: "نام",
  fund_symbol: "صندوق",
  isin: "ISIN",
  source: "منبع",
  status: "وضعیت",
  coverage_status: "پوشش",
  reject_reason: "دلیل رد",
  reject_rule: "قاعده",
  reviewed: "بازبینی",
  price: "قیمت",
  volume: "حجم",
  count: "تعداد",
  trade_value: "ارزش معاملاتی",
  weight_pct: "وزن ٪",
  weight_change_pct: "تغییر وزن ٪",
  flow_direction: "جهت جریان",
  instrument_symbol: "ابزار",
  instrument_name: "ابزار",
  holding_type: "نوع دارایی",
  market_value: "ارزش بازار",
  quantity: "تعداد",
  total_score: "امتیاز",
  sharpe: "شارپ",
  max_drawdown: "حداکثر افت",
  rank: "رتبه",
  score_date: "تاریخ امتیاز",
  nav: "NAV",
  nav_issue: "NAV صدور",
  nav_redemption: "NAV ابطال",
  nav_statistical: "NAV آماری",
  date: "تاریخ",
  tier: "سطح",
  direction: "جهت",
  units: "واحدها",
  amount: "مبلغ",
  debit: "بستانکار",
  credit: "بدهکار",
  account: "حساب",
  description: "شرح",
  rule_type: "نوع قاعده",
  rate: "نرخ",
  period: "دوره",
  lifecycle: "چرخه",
  severity: "شدت",
  break_type: "نوع مغایرت",
  deviation_pct: "انحراف ٪",
  engine_version: "نسخه موتور",
  path_used: "مسیر فرمول",
  confidence: "اطمینان",
  valuation_date: "تاریخ ارزش‌گذاری",
  allocation_type: "نوع تخصیص",
  class_code: "کد طبقه",
  nav_per_unit: "NAV هر واحد",
  weight: "وزن",
  underlying: "زیرصندوق",
  loop: "حلقه",
  hops: "سطوح",
  reason: "دلیل",
  total: "جمع",
  average: "میانگین",
  min: "کمینه",
  max: "بیشینه",
};

export function headerLabel(key: string) {
  return FA_LABELS[key] ?? FA_LABELS[key.replace(/^(is_|has_)/, "")] ?? key;
}

export interface Column<T> {
  key: keyof T | string;
  label: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  rows,
  columns,
  emptyText,
  maxHeight,
  highlight,
  dense,
}: {
  rows: T[] | undefined | null;
  columns?: Column<T>[];
  emptyText?: string;
  maxHeight?: number;
  highlight?: (row: T) => boolean;
  dense?: boolean;
}) {
  const cols = useMemo<Column<T>[]>(() => {
    if (columns?.length) return columns;
    const sample = rows?.[0];
    if (!sample) return [];
    return Object.keys(sample)
      .filter((k) => !HIDDEN_KEYS.test(k) && sample[k] !== undefined)
      .slice(0, 9)
      .map((k) => ({ key: k, label: headerLabel(k) }));
  }, [rows, columns]);

  if (!rows?.length || !cols.length) return <Empty text={emptyText ?? "رکوردی برای نمایش نیست"} />;

  const cell = (row: T, col: Column<T>) => {
    if (col.render) return col.render(row);
    const v = row[col.key as string];
    const kind = guessKind(String(col.key), v);
    if (kind === "pct" && typeof v === "number") return <span dir={numDir} className={v >= 0 ? "text-accent-emerald" : "text-accent-rose"}>{fmtPct(v)}</span>;
    if (kind === "date") return <span dir={numDir}>{fmtDate(v)}</span>;
    if (kind === "time") return <span dir={numDir}>{fmtDateTime(v)}</span>;
    if (kind === "num") return <span dir={numDir}>{Math.abs(v as number) > 999 ? fmtBig(v) : fmt(v, 2)}</span>;
    if (typeof v === "boolean") return <Chip label={v ? "بله" : "خیر"} tone={v ? "pos" : "muted"} />;
    if (v === null || v === undefined || v === "") return <span className="text-surface-600">—</span>;
    return String(v);
  };

  return (
    <div className="overflow-auto rounded-xl border border-surface-700/60" style={maxHeight ? { maxHeight } : undefined}>
      <table className="w-full text-[11px] border-collapse">
        <thead className="sticky top-0 z-10 bg-surface-900/95 backdrop-blur">
          <tr>
            {cols.map((c) => (
              <th key={String(c.key)} className={`text-right font-bold text-surface-400 border-b border-surface-700 ${dense ? "px-2 py-1.5" : "px-3 py-2"}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-surface-800/60 last:border-0 transition-colors ${
                highlight?.(row) ? "bg-primary-600/10" : "hover:bg-white/[0.03]"
              }`}
            >
              {cols.map((c) => (
                <td key={String(c.key)} className={`${dense ? "px-2 py-1" : "px-3 py-2"} text-surface-300 ${c.className ?? ""}`}>
                  {cell(row, c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Vertical key/value list — used for single-object payloads (runs, evidence, configs). */
export function KeyValue({ data, keys, filter }: { data: Record<string, unknown> | null | undefined; keys?: string[]; filter?: (k: string) => boolean }) {
  if (!data) return <Empty text="رکوردی بازنگشت" />;
  const entries = Object.entries(data).filter(
    ([k, v]) => (keys ? keys.includes(k) : true) && (filter ? filter(k) : true) && v !== undefined && typeof v !== "object"
  );
  if (!entries.length) return <Empty text="فیلد ساده‌ای در این پاسخ نیست" />;
  return (
    <div className="divide-y divide-surface-800/70 rounded-xl border border-surface-700/60 overflow-hidden">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-3 px-3 py-2 bg-surface-900/20">
          <span className="text-[11px] text-surface-500">{headerLabel(k)}</span>
          <span className="text-[11px] font-mono font-bold text-surface-200" dir={typeof v === "number" ? numDir : undefined}>
            {typeof v === "number" ? (Math.abs(v) > 999 ? fmtBig(v) : fmt(v, 4)) : typeof v === "boolean" ? (v ? "بله" : "خیر") : String(v)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Pull the first array out of a heterogeneous endpoint response. */
export function rowsOf(payload: unknown, ...hints: string[]): Record<string, unknown>[] {
  if (Array.isArray(payload)) return payload as Record<string, unknown>[];
  if (!payload || typeof payload !== "object") return [];
  const obj = payload as Record<string, unknown>;
  for (const h of [...hints, "items", "data", "rows", "records", "results"]) {
    const v = obj[h];
    if (Array.isArray(v)) return v as Record<string, unknown>[];
  }
  const firstArray = Object.values(obj).find(Array.isArray);
  return (firstArray as Record<string, unknown>[] | undefined) ?? [];
}

export function firstOf(obj: Record<string, unknown> | null | undefined, keys: string[]): unknown {
  if (!obj) return null;
  for (const k of keys) if (obj[k] !== undefined && obj[k] !== null) return obj[k];
  return null;
}
