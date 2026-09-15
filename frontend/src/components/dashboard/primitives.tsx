"use client";

import { useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, Minus, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { fmtPct } from "@/lib/market-format";

/* ── Live flash — brief tint when a streamed number changes ── */

/**
 * Wraps a price readout; whenever `value` moves the wrapper remounts (key
 * bump) so the flash-up/flash-down CSS animation replays. State-based diff
 * (no ref reads in render — the react-hooks/refs rule forbids the render-phase
 * ref pattern). One extra render per change only, and none when idle.
 */
export function Flash({
  value,
  className,
  children,
}: {
  value: number;
  className?: string;
  children: ReactNode;
}) {
  // [previous value, flash direction, mount key]
  const [[prev, dir, tick], setDiff] = useState<[number, "up" | "down" | null, number]>([
    value,
    null,
    0,
  ]);
  if (value !== prev) {
    setDiff([value, value > prev ? "up" : "down", tick + 1]);
  }
  return (
    <span
      key={tick}
      className={cn(
        "inline-block rounded-md px-0.5",
        dir === "up" && "flash-up",
        dir === "down" && "flash-down",
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ── Section header ─────────────────────────────────────────── */

export function SectionHeader({
  icon: Icon,
  title,
  subtitle,
  action,
  tone,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  subtitle?: string;
  action?: ReactNode;
  /** Tints the icon chip (e.g. "up", "down", "warn", "primary"). */
  tone?: "up" | "down" | "warn" | "primary";
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3", className)}>
      <div className="flex items-center gap-2.5 min-w-0">
        {Icon && (
          <span
            className={cn(
              "grid size-8 shrink-0 place-items-center rounded-xl border",
              (!tone || tone === "primary") && "border-primary-600/20 bg-primary-600/10 text-primary-700 dark:border-brand-300/20 dark:bg-brand-300/10 dark:text-brand-200",
              tone === "up" && "border-up/20 bg-up/10 text-up",
              tone === "down" && "border-down/20 bg-down/10 text-down",
              tone === "warn" && "border-warn/25 bg-warn/10 text-warn",
            )}
          >
            <Icon className="size-4" aria-hidden />
          </span>
        )}
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-ink truncate">{title}</h2>
          {subtitle && <p className="mt-0.5 text-[11px] text-ink-3 truncate">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

/* ── Trend arrow + Delta badge ──────────────────────────────── */

export function TrendArrow({ value, className }: { value: number; className?: string }) {
  if (value > 0) return <ArrowUp className={cn("size-3.5", className)} aria-hidden />;
  if (value < 0) return <ArrowDown className={cn("size-3.5", className)} aria-hidden />;
  return <Minus className={cn("size-3.5", className)} aria-hidden />;
}

export function DeltaBadge({
  value,
  suffix = "%",
  showArrow = true,
  className,
}: {
  value: number;
  suffix?: string;
  showArrow?: boolean;
  className?: string;
}) {
  const tone = value > 0 ? "up" : value < 0 ? "down" : "flat";
  return (
    <span
      dir="ltr"
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[11px] font-bold tabular-nums",
        tone === "up" && "bg-up/12 text-up",
        tone === "down" && "bg-down/12 text-down",
        tone === "flat" && "bg-soft text-ink-3",
        className,
      )}
    >
      {showArrow && <TrendArrow value={value} />}
      {fmtPct(value)}
      {suffix && suffix !== "%" ? suffix : ""}
    </span>
  );
}

/* ── Sparkline (inline SVG) ─────────────────────────────────── */

export function Sparkline({
  data,
  width = 84,
  height = 28,
  stroke,
  className,
}: {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  className?: string;
}) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1 || 1);
  const pts = data.map((v, i) => {
    const x = i * step;
    const y = height - 3 - ((v - min) / range) * (height - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const last = data[data.length - 1];
  const first = data[0];
  const color =
    stroke || (last > first ? "var(--up)" : last < first ? "var(--down)" : "var(--ink-3)");
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("shrink-0 overflow-visible", className)}
      aria-hidden
    >
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={width - 2} cy={Number(pts[pts.length - 1].split(",")[1])} r={2} fill={color} />
    </svg>
  );
}

/* ── Recharts shared tooltip ────────────────────────────────── */

export interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
  payload?: Record<string, unknown>;
}

export function ChartTooltip({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  formatter?: (value: number, name: string, entry: TooltipEntry) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div dir="rtl" className="rounded-xl border border-line-strong bg-card/95 px-3 py-2.5 shadow-[var(--shadow-card)] backdrop-blur">
      {label != null && <p className="mb-1.5 text-[11px] font-bold text-ink-3">{label}</p>}
      <div className="space-y-1">
        {payload.map((entry, i) => {
          const num =
            typeof entry.value === "number"
              ? entry.value
              : Number(String(entry.value).replace(/[^\d.-]/g, "")) || 0;
          return (
            <div key={i} className="flex items-center gap-2 text-[11px]">
              <span
                className="size-2 rounded-full"
                style={{ background: entry.color || "var(--ink-3)" }}
              />
              <span className="text-ink-2">{entry.name ?? entry.dataKey}</span>
              <span className="mr-auto font-mono font-bold text-ink tabular-nums" dir="ltr">
                {formatter ? formatter(num, String(entry.name ?? ""), entry) : num.toLocaleString("en-US")}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Skeleton block ─────────────────────────────────────────── */

export function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-xl bg-soft", className)}
      style={{ backgroundImage: "linear-gradient(100deg, transparent 30%, rgba(255,255,255,0.06) 50%, transparent 70%)" }}
      aria-hidden
    />
  );
}

/* ── Empty / error state ────────────────────────────────────── */

export function EmptyState({
  icon: Icon,
  title,
  hint,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line-strong bg-soft/40 px-6 py-10 text-center", className)}>
      {Icon && (
        <span className="grid size-10 place-items-center rounded-2xl bg-soft text-ink-3">
          <Icon className="size-5" aria-hidden />
        </span>
      )}
      <p className="text-[13px] font-bold text-ink-2">{title}</p>
      {hint && <p className="max-w-xs text-[11px] leading-relaxed text-ink-3">{hint}</p>}
    </div>
  );
}

/* ── KPI mini metric ────────────────────────────────────────── */

export function MiniMetric({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "flat";
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-card p-3">
      <p className="text-[10px] font-medium text-ink-3">{label}</p>
      <p
        dir="ltr"
        className={cn(
          "mt-1 font-mono text-base font-bold tabular-nums leading-none",
          tone === "up" && "text-up",
          tone === "down" && "text-down",
          (!tone || tone === "flat") && "text-ink",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-1 text-[10px] text-ink-3">{hint}</p>}
    </div>
  );
}
