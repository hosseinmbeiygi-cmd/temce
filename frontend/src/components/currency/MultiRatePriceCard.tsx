"use client";

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Card } from "@/components/ui/Card";
import type { RateBlock } from "@/types/currency";

function fmt(n: number): string {
  return n.toLocaleString("fa-IR", { maximumFractionDigits: 0 });
}

interface Props {
  title: string;
  rate: RateBlock;
}

/** کارت نرخ یک بازار (آزاد / تتر / نیما) — buy=خرید ما، sell=فروش ما طبق پرامپت. */
export function MultiRatePriceCard({ title, rate }: Props) {
  const up = rate.daily_change > 0;
  const down = rate.daily_change < 0;

  return (
    <Card title={title} subtitle={rate.source}>
      <div className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-xs opacity-70">فروش (خرید شما):</span>
          <span className="text-xl font-extrabold tracking-tight">
            {fmt(rate.sell)} <span className="text-xs font-normal opacity-60">تومان</span>
          </span>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-xs opacity-70">خرید (فروش شما):</span>
          <span className="text-sm font-semibold opacity-80">
            {fmt(rate.buy)} <span className="text-xs font-normal">تومان</span>
          </span>
        </div>
        <div className="flex items-center justify-between border-t pt-2 text-xs">
          <div className="flex items-center gap-1">
            <span className="opacity-60">اسپرد:</span>
            <span className="font-mono font-medium">{rate.spread.toFixed(2)}%</span>
          </div>
          <div
            className={`flex items-center gap-0.5 font-medium ${
              up ? "text-rose-500" : down ? "text-emerald-500" : "opacity-60"
            }`}
          >
            {up && <ArrowUpRight className="h-4 w-4" />}
            {down && <ArrowDownRight className="h-4 w-4" />}
            {!up && !down && <Minus className="h-4 w-4" />}
            <span>{Math.abs(rate.daily_change).toFixed(1)}%</span>
          </div>
        </div>
      </div>
    </Card>
  );
}
