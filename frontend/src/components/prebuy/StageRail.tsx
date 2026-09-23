"use client";

/**
 * The stage rail: eleven stages, gated.
 *
 * A stage opens only when every earlier one is complete — the framework's rule is
 * behavioural («اگر پاسخ نمی‌دانم است، به مرحله بعد نروید»), so a locked stage is not
 * merely greyed, it is the UI refusing to show questions the process has not reached.
 */

import { Lock } from "lucide-react";
import { STAGE_STATUS_META, type BankStage, type StagePreview } from "@/lib/pre-buy";
import { cn } from "@/lib/cn";

export function StageRail({
  stages,
  previews,
  stopperCounts,
  active,
  onSelect,
}: {
  stages: BankStage[];
  previews: StagePreview[];
  stopperCounts: Record<number, number>;
  active: number;
  onSelect: (id: number) => void;
}) {
  return (
    <nav aria-label="مراحل تحلیل" className="glass-card p-2">
      <p className="px-1 pb-1.5 text-[10px] font-bold text-surface-500">
        مراحل یازده‌گانه — هر مرحله کلید مرحلهٔ بعد است
      </p>
      <ol className="space-y-1">
        {stages.map((stage) => {
          const p = previews.find((s) => s.id === stage.id);
          const status = p?.status ?? "empty";
          const meta = STAGE_STATUS_META[status];
          const locked = p?.locked ?? false;
          const isActive = stage.id === active;
          return (
            <li key={stage.id}>
              <button
                type="button"
                onClick={() => onSelect(stage.id)}
                aria-current={isActive ? "step" : undefined}
                aria-disabled={locked}
                title={locked ? "ابتدا مرحله‌های پیشین را کامل کنید" : stage.purpose}
                className={cn(
                  "w-full rounded-lg px-2 py-1.5 text-right transition-colors",
                  isActive ? "bg-primary-600/20 ring-1 ring-primary-500/40" : "hover:bg-surface-800",
                  locked && "opacity-55"
                )}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      "grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-mono",
                      isActive ? "bg-primary-500 text-white" : "bg-surface-700 text-surface-300"
                    )}
                    dir="ltr"
                  >
                    {stage.id}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[11px] font-bold text-surface-200">{stage.title}</span>
                    <span className={cn("block text-[9.5px]", meta.className)}>
                      {locked ? "قفل" : meta.label}
                      {!locked && p && p.total > 0 && ` — ${p.answered}/${p.total}`}
                    </span>
                  </span>
                  {locked ? (
                    <Lock className="w-3 h-3 shrink-0 text-surface-600" />
                  ) : (
                    stopperCounts[stage.id] > 0 && (
                      <span className="shrink-0 text-[9px] font-bold text-accent-rose" dir="ltr">
                        ★{stopperCounts[stage.id]}
                      </span>
                    )
                  )}
                </span>
                <span className="mt-1 block h-0.5 overflow-hidden rounded-full bg-surface-700">
                  <span
                    className={cn("block h-full rounded-full transition-all duration-500", meta.dot)}
                    style={{ width: `${p?.progressPct ?? 0}%` }}
                  />
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
