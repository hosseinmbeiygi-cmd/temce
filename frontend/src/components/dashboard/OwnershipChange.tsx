"use client";

import { Users } from "lucide-react";
import { useOwnershipFlows } from "@/hooks/useMarketData";
import { fmtBillion } from "@/lib/market-format";
import { cn } from "@/lib/cn";
import LiveDataBanner from "./LiveDataBanner";
import { SectionHeader } from "./primitives";

function FlowBar({ value, max, align }: { value: number; max: number; align: "real" | "legal" }) {
  const pos = value >= 0;
  const pct = Math.max((Math.abs(value) / max) * 100, 2);
  const color = pos ? "bg-up" : "bg-down";
  return (
    <div className="flex h-2 w-full items-center" dir="ltr">
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-soft">
        <div
          className={cn("absolute top-0 h-full rounded-full transition-all duration-500", color)}
          style={align === "real" ? { left: 0, width: `${pct}%` } : { right: 0, width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function OwnershipChange() {
  const { data: rows, isLive, isError, isLoading } = useOwnershipFlows();
  const max = Math.max(1e-9, ...rows.map((r) => Math.max(Math.abs(r.realNet), Math.abs(r.legalNet))));
  return (
    <section className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)] sm:p-5">
      <SectionHeader
        icon={Users}
        title="تغییر مالکیت حقوقی و حقیقی"
        subtitle="خالص جریان پول هر نماد — میلیارد تومان"
      />
      <LiveDataBanner state={{ isLive, isError, isLoading }} />
      <div className="mt-4 flex items-center gap-4 text-[10.5px] font-bold">
        <span className="flex items-center gap-1.5 text-up">
          <span className="size-2 rounded-full bg-up" /> حقیقی (خرید خالص)
        </span>
        <span className="mr-auto flex items-center gap-1.5 text-down">
          <span className="size-2 rounded-full bg-down" /> حقوقی (فروش خالص)
        </span>
      </div>
      <div className="mt-2 divide-y divide-line">
        {rows.map((r) => (
          <div key={r.symbol} className="flex items-center gap-3 py-2.5">
            <span className="w-14 shrink-0 text-[12px] font-bold text-ink">{r.symbol}</span>
            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex items-center gap-2">
                <span
                  dir="ltr"
                  className={cn(
                    "w-16 shrink-0 text-left font-mono text-[11px] font-bold tabular-nums",
                    r.realNet > 0 ? "text-up" : "text-down",
                  )}
                >
                  {r.realNet > 0 ? "+" : ""}
                  {fmtBillion(r.realNet)}
                </span>
                <FlowBar value={r.realNet} max={max} align="real" />
              </div>
              <div className="flex items-center gap-2">
                <span
                  dir="ltr"
                  className={cn(
                    "w-16 shrink-0 text-left font-mono text-[11px] font-bold tabular-nums",
                    r.legalNet > 0 ? "text-up" : "text-down",
                  )}
                >
                  {r.legalNet > 0 ? "+" : ""}
                  {fmtBillion(r.legalNet)}
                </span>
                <FlowBar value={r.legalNet} max={max} align="legal" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
