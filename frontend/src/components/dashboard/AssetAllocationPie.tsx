"use client";

import { PieChart as PieIcon, ChartNoAxesColumn } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useAssetAllocation } from "@/hooks/useMarketData";
import LiveDataBanner from "./LiveDataBanner";
import { ChartTooltip, SectionHeader } from "./primitives";

const COLORS = ["#33486b", "#718db0", "#d97706", "#a3b7d2", "#64748b"];

export default function AssetAllocationPie() {
  const { data: slices, isLive, isError, isLoading } = useAssetAllocation();
  const total = slices.reduce((s, a) => s + a.valueB, 0);

  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={PieIcon}
        title="انواع دارایی"
        subtitle="سهم هر کلاس از ارزش بازار — طبقه‌بندی تقریبی"
      />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      {!isLive ? (
        <div className="mt-2 flex h-44 items-center justify-center gap-2 text-[11px] text-ink-3">
          <ChartNoAxesColumn className="size-4" aria-hidden />
          داده زنده‌ای برای ترکیب دارایی در دسترس نیست.
        </div>
      ) : (
        <>
          <div className="mt-2 flex h-44 items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="valueB"
                  nameKey="label"
                  innerRadius="62%"
                  outerRadius="88%"
                  paddingAngle={2.5}
                  strokeWidth={0}
                  cornerRadius={4}
                >
                  {slices.map((s, i) => (
                    <Cell key={s.label} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "transparent" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 space-y-1.5">
            {slices.map((s, i) => (
              <div key={s.label} className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-soft">
                <span className="size-2.5 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />
                <span className="text-[12px] text-ink-2">{s.label}</span>
                <span dir="ltr" className="mr-auto font-mono text-[12px] font-bold tabular-nums text-ink">
                  {s.valueB.toLocaleString("en-US")}
                </span>
                <span dir="ltr" className="w-11 text-left font-mono text-[11px] tabular-nums text-ink-3">
                  {s.pct != null ? `${Math.round(s.pct)}%` : `${Math.round((s.valueB / total) * 100)}%`}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
