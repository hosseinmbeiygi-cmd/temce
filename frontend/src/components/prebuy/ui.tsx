"use client";

/**
 * Presentational atoms for the pre-buy feature.
 *
 * Deliberately local rather than imported from `components/funds`: the decision sheet
 * is a form, not a table screen, and coupling two features' markup for four small
 * helpers would make either one harder to change.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type Tone = "default" | "pos" | "neg" | "warn" | "accent" | "muted";

export const toneText = (tone: Tone = "default") =>
  tone === "pos"
    ? "text-accent-emerald"
    : tone === "neg"
      ? "text-accent-rose"
      : tone === "warn"
        ? "text-accent-amber"
        : tone === "accent"
          ? "text-primary-300"
          : tone === "muted"
            ? "text-surface-400"
            : "text-surface-100";

const CHIP_TONES: Record<Tone, string> = {
  default: "bg-surface-700/60 text-surface-200",
  pos: "bg-accent-emerald/15 text-accent-emerald",
  neg: "bg-accent-rose/15 text-accent-rose",
  warn: "bg-accent-amber/15 text-accent-amber",
  accent: "bg-primary-600/20 text-primary-300",
  muted: "bg-surface-800 text-surface-400",
};

export function Chip({ label, tone = "default", title }: { label: string; tone?: Tone; title?: string }) {
  return (
    <span
      title={title}
      className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold", CHIP_TONES[tone])}
    >
      {label}
    </span>
  );
}

export function Panel({
  title,
  desc,
  actions,
  children,
  className = "",
}: {
  title: string;
  desc?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("glass-card p-4", className)}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-surface-100">{title}</h3>
          {desc && <p className="mt-0.5 text-[11px] leading-relaxed text-surface-500">{desc}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

/** Persian-grouped number; `—` for anything that is not a real figure. */
export function fmt(v: unknown, digits = 0): string {
  const n = typeof v === "number" ? v : Number(v);
  if (v === null || v === undefined || v === "" || !Number.isFinite(n)) return "—";
  return n.toLocaleString("fa-IR", { maximumFractionDigits: digits });
}

export function fmtPct(v: unknown, digits = 2): string {
  const n = typeof v === "number" ? v : Number(v);
  if (v === null || v === undefined || !Number.isFinite(n)) return "—";
  return `${n.toLocaleString("fa-IR", { maximumFractionDigits: digits })}٪`;
}

export function fmtDate(v: unknown): string {
  if (!v) return "—";
  const d = new Date(String(v));
  if (Number.isNaN(d.getTime())) return String(v);
  return d.toLocaleDateString("fa-IR");
}

export function fmtDateTime(v: unknown): string {
  if (!v) return "—";
  const d = new Date(String(v));
  if (Number.isNaN(d.getTime())) return String(v);
  return d.toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" });
}
