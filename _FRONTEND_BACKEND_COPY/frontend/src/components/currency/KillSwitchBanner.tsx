"use client";

import { AlertTriangle } from "lucide-react";

/** بنر قرمز هشدار — فقط وقتی kill_switch.active true است رندر می‌شود. */
export function KillSwitchBanner({ reasons }: { reasons: string[] }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-rose-500/40 bg-rose-500/10 p-4">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-500" />
      <div>
        <div className="text-sm font-extrabold text-rose-600 dark:text-rose-400">
          KILL-SWITCH فعال شد — از ورود به پوزیشن جدید خودداری کنید
        </div>
        <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-rose-500 dark:text-rose-300">
          {reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
