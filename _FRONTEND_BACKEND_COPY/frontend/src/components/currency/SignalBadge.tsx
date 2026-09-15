"use client";

import { cn } from "@/lib/cn";
import type { Confidence, SignalType } from "@/types/currency";

const TYPE_STYLES: Record<SignalType, string> = {
  BUY: "bg-emerald-600/15 text-emerald-700 ring-emerald-600/30 dark:text-emerald-400",
  SELL: "bg-rose-600/15 text-rose-700 ring-rose-600/30 dark:text-rose-400",
  HOLD: "bg-zinc-500/15 text-zinc-600 ring-zinc-500/30 dark:text-zinc-400",
};

const TYPE_LABEL: Record<SignalType, string> = { BUY: "خرید", SELL: "فروش", HOLD: "نگهداری" };
const CONF_LABEL: Record<Confidence, string> = { LOW: "کم", MEDIUM: "متوسط", HIGH: "زیاد" };

export function SignalBadge({ type, confidence }: { type: SignalType; confidence: Confidence }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ring-1",
        TYPE_STYLES[type]
      )}
    >
      {TYPE_LABEL[type]}
      <span className="font-normal opacity-75">· اطمینان {CONF_LABEL[confidence]}</span>
    </span>
  );
}
