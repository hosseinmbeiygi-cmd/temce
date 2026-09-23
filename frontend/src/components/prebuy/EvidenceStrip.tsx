"use client";

/**
 * The evidence strip: what the platform already knows for the question above it.
 *
 * An unavailable figure stays unavailable. The resolver's Persian reason is shown next
 * to the source path instead of a proxy number, because a decision sheet that fills its
 * own gaps with approximations is worse than one that admits them.
 */

import { CircleDashed, Database } from "lucide-react";
import type { BankEvidence, EvidenceValue } from "@/lib/pre-buy";
import { fmt, toneText } from "./ui";

export function EvidenceStrip({
  items,
  resolved,
  dense = false,
}: {
  items: BankEvidence[];
  resolved: Record<string, EvidenceValue> | null | undefined;
  dense?: boolean;
}) {
  if (items.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 border-r-2 border-surface-700/70 pr-2">
      {items.map((item) => {
        const value = resolved?.[item.key];
        const ok = value?.status === "available";
        // Three states, said differently: a number, a figure this symbol's row does not carry,
        // and a figure the platform has no column for at all.
        const gap = !ok && value?.declared;
        return (
          <li key={item.key} className="flex items-baseline gap-1.5">
            <Icon ok={ok} gap={Boolean(gap)} />
            <span className="text-[10px] text-surface-500">{item.label}</span>
            <span className={`text-[11px] font-bold ${toneText(ok ? "pos" : "muted")}`} dir="ltr">
              {ok ? fmt(value?.value, isFraction(item) ? 2 : 0) : "—"}
            </span>
            {item.unit && <span className="text-[9px] text-surface-600">{item.unit}</span>}
            {!ok && gap && (
              <span className="text-[9px] leading-relaxed text-accent-rose/80">
                {value?.note || "این داده در پلتفرم ذخیره نمی‌شود."}
              </span>
            )}
            {!ok && !gap && !dense && value?.note && (
              <span className="text-[9px] leading-relaxed text-accent-amber/80">{value.note}</span>
            )}
            {!ok && !gap && dense && <span className="text-[9px] text-surface-600">برای این نماد نیست</span>}
            {value?.source && (
              <span className="text-[8px] text-surface-700 font-mono" dir="ltr">
                {value.source}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

const isFraction = (item: BankEvidence) =>
  item.key.endsWith("_ratio") || item.key.endsWith("_pct") || item.key.includes("free_float");

function Icon({ ok, gap }: { ok: boolean; gap: boolean }) {
  if (ok) return <Database className="w-2.5 h-2.5 text-accent-emerald/70 shrink-0 self-center" />;
  return gap ? (
    <CircleDashed className="w-2.5 h-2.5 text-accent-rose/60 shrink-0 self-center" />
  ) : (
    <CircleDashed className="w-2.5 h-2.5 text-surface-600 shrink-0 self-center" />
  );
}
