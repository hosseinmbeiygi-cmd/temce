"use client";

import { BarChart3 } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CASHFLOW_BY_SECTOR, OWNERSHIP_LAST_DAYS, VALUE_LAST_DAYS } from "@/lib/market-mock";
import { ChartTooltip, SectionHeader } from "./primitives";

const AXIS_TICK = { fill: "var(--ink-3)", fontSize: 10 };
const GRID = "var(--line)";

function compact(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return `${v}`;
}

function ChartShell({
  title,
  subtitle,
  legend,
  children,
}: {
  title: string;
  subtitle: string;
  legend?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-[13px] font-bold text-ink">{title}</h3>
          <p className="truncate text-[10.5px] text-ink-3">{subtitle}</p>
        </div>
        {legend}
      </div>
      <div className="mt-3 h-44 min-w-0 flex-1">{children}</div>
    </div>
  );
}

export default function TripleChartsGroup() {
  return (
    <section className="space-y-3">
      <SectionHeader
        icon={BarChart3}
        title="جریان پول و معاملات"
        subtitle="سه نمای هماهنگ از نقدینگی، ارزش معاملات و مالکیت — میلیارد تومان"
      />
      <div className="grid gap-4 lg:grid-cols-3">
        {/* 1 — Signed cash flow by sector */}
        <ChartShell title="جریان نقدینگی حقیقی" subtitle="بر اساس گروه صنعت — امروز">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-[10px] text-ink-3">
              <span className="size-2 rounded-full bg-up" /> ورود
            </span>
            <span className="flex items-center gap-1.5 text-[10px] text-ink-3">
              <span className="size-2 rounded-full bg-down" /> خروج
            </span>
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={CASHFLOW_BY_SECTOR} margin={{ top: 8, right: 0, left: 0, bottom: 0 }} barCategoryGap="26%">
              <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="3 6" />
              <XAxis dataKey="name" tick={AXIS_TICK} axisLine={false} tickLine={false} interval={0} angle={-18} height={38} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={34} tickFormatter={compact} />
              <Tooltip content={<ChartTooltip formatter={(v) => `${compact(v)} م.ت`} />} cursor={{ fill: "var(--line)" }} />
              <Bar dataKey="value" name="جریان" radius={[4, 4, 0, 0]}>
                {CASHFLOW_BY_SECTOR.map((s) => (
                  <Cell key={s.name} fill={s.value >= 0 ? "var(--up)" : "var(--down)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartShell>

        {/* 2 — Daily trade value */}
        <ChartShell title="ارزش معاملات روزانه" subtitle="پنج روز کاری اخیر">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={VALUE_LAST_DAYS} margin={{ top: 8, right: 0, left: 0, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="3 6" />
              <XAxis dataKey="day" tick={AXIS_TICK} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={38} tickFormatter={compact} />
              <Tooltip content={<ChartTooltip formatter={(v) => `${compact(v)} م.ت`} />} cursor={{ fill: "var(--line)" }} />
              <Bar dataKey="value" name="ارزش" fill="var(--primary-600)" radius={[5, 5, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartShell>

        {/* 3 — Real vs legal ownership flow */}
        <ChartShell title="ورود/خروج پول" subtitle="حقیقی در برابر حقوقی — روزانه">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-[10px] text-ink-3">
              <span className="size-2 rounded-full bg-up" /> حقیقی
            </span>
            <span className="flex items-center gap-1.5 text-[10px] text-ink-3">
              <span className="size-2 rounded-full bg-primary-600" /> حقوقی
            </span>
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={OWNERSHIP_LAST_DAYS} margin={{ top: 8, right: 0, left: 0, bottom: 0 }} barCategoryGap="24%" barGap={2}>
              <CartesianGrid vertical={false} stroke={GRID} strokeDasharray="3 6" />
              <XAxis dataKey="day" tick={AXIS_TICK} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={34} tickFormatter={compact} />
              <Tooltip content={<ChartTooltip formatter={(v) => `${compact(v)} م.ت`} />} cursor={{ fill: "var(--line)" }} />
              <Bar dataKey="real" name="حقیقی" fill="var(--up)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="legal" name="حقوقی" fill="var(--primary-600)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartShell>
      </div>
    </section>
  );
}
