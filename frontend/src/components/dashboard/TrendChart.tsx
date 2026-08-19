"use client";

import { useState } from "react";
import { TrendingUp } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { INDEX_INTRADAY } from "@/lib/market-mock";
import { fmtInt } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import { ChartTooltip, SectionHeader } from "./primitives";

const RANGES = ["۱ روز", "۱ هفته", "۱ ماه", "۳ ماه", "سالانه"];

const AXIS_TICK = { fill: "var(--ink-3)", fontSize: 10 };

function compact(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (abs >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return `${v}`;
}

export default function TrendChart() {
  const [range, setRange] = useState(0);
  const first = INDEX_INTRADAY[0].value;
  const last = INDEX_INTRADAY[INDEX_INTRADAY.length - 1].value;
  const delta = ((last - first) / first) * 100;

  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={TrendingUp}
        title="روند شاخص کل — امروز"
        subtitle="حرکت شاخص کل بورس در ساعات معاملاتی"
        action={
          <div className="flex items-center gap-1 rounded-xl border border-line bg-soft p-1">
            {RANGES.map((r, i) => (
              <button
                key={r}
                type="button"
                onClick={() => setRange(i)}
                className={cn(
                  "cursor-pointer rounded-lg px-2 py-1 text-[10.5px] font-bold transition-colors duration-150",
                  range === i ? "bg-card text-ink shadow-[var(--shadow-card)]" : "text-ink-3 hover:text-ink-2",
                )}
              >
                {r}
              </button>
            ))}
          </div>
        }
      />

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_260px]">
        <div className="h-52 min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={INDEX_INTRADAY} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="idxArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--primary-600)" stopOpacity={0.32} />
                  <stop offset="100%" stopColor="var(--primary-600)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="3 6" />
              <XAxis dataKey="time" tick={AXIS_TICK} axisLine={false} tickLine={false} interval={1} />
              <YAxis
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
                width={44}
                domain={["dataMin - 4000", "dataMax + 2000"]}
                tickFormatter={compact}
              />
              <Tooltip content={<ChartTooltip formatter={(v) => fmtInt(v)} />} cursor={{ stroke: "var(--line-strong)" }} />
              <ReferenceLine y={first} stroke="var(--line-strong)" strokeDasharray="4 4" />
              <Area
                type="monotone"
                dataKey="value"
                name="شاخص کل"
                stroke="var(--primary-600)"
                strokeWidth={2}
                fill="url(#idxArea)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col justify-center gap-3 rounded-2xl border border-line bg-soft/50 p-4">
          <div>
            <p className="text-[10.5px] text-ink-3">ارزش فعلی شاخص</p>
            <p dir="ltr" className="mt-1 font-mono text-[26px] font-black tabular-nums text-ink">
              {fmtInt(last)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              dir="ltr"
              className={cn("font-mono text-[13px] font-bold tabular-nums", delta >= 0 ? "text-up" : "text-down")}
            >
              {delta >= 0 ? "+" : ""}
              {delta.toFixed(2)}٪
            </span>
            <span className="text-[10.5px] text-ink-3">از ابتدای امروز</span>
          </div>
          <div className="h-px bg-line" />
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl bg-card p-2.5">
              <p className="text-[9.5px] text-ink-3">بیشترین</p>
              <p dir="ltr" className="mt-0.5 font-mono text-[12px] font-bold tabular-nums text-ink">
                {fmtInt(Math.max(...INDEX_INTRADAY.map((p) => p.value)))}
              </p>
            </div>
            <div className="rounded-xl bg-card p-2.5">
              <p className="text-[9.5px] text-ink-3">کمترین</p>
              <p dir="ltr" className="mt-0.5 font-mono text-[12px] font-bold tabular-nums text-ink">
                {fmtInt(Math.min(...INDEX_INTRADAY.map((p) => p.value)))}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
