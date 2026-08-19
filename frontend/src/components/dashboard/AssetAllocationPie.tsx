"use client";

import { PieChart as PieIcon } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ASSET_ALLOCATION } from "@/lib/market-mock";
import { ChartTooltip, SectionHeader } from "./primitives";

export default function AssetAllocationPie() {
  const total = ASSET_ALLOCATION.reduce((s, a) => s + a.value, 0);
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader icon={PieIcon} title="انواع دارایی" subtitle="سهم هر کلاس از ارزش بازار" />
      <div className="mt-2 flex h-44 items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={ASSET_ALLOCATION}
              dataKey="value"
              nameKey="label"
              innerRadius="62%"
              outerRadius="88%"
              paddingAngle={2.5}
              strokeWidth={0}
              cornerRadius={4}
            >
              {ASSET_ALLOCATION.map((s) => (
                <Cell key={s.label} fill={s.color} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "transparent" }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 space-y-1.5">
        {ASSET_ALLOCATION.map((s) => (
          <div key={s.label} className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-soft">
            <span className="size-2.5 rounded-sm" style={{ background: s.color }} />
            <span className="text-[12px] text-ink-2">{s.label}</span>
            <span dir="ltr" className="mr-auto font-mono text-[12px] font-bold tabular-nums text-ink">
              {s.value}
            </span>
            <span dir="ltr" className="w-11 text-left font-mono text-[11px] tabular-nums text-ink-3">
              {Math.round((s.value / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
