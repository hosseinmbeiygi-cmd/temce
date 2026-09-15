"use client";

import { Shield, Droplets, TrendingUp, AlertTriangle, Clock } from "lucide-react";
import { cn } from "@/lib/cn";
import type { SymbolArmorResult } from "@/stores/precomputeStore";

function scoreColor(score: number): string {
  if (score >= 70) return "text-up";
  if (score >= 40) return "text-warn";
  return "text-down";
}
function scoreBg(score: number): string {
  if (score >= 70) return "bg-up/10 border-up/20";
  if (score >= 40) return "bg-warn/10 border-warn/20";
  return "bg-down/10 border-down/20";
}
function driColor(dri: number): string {
  if (dri >= 80) return "bg-up";
  if (dri >= 50) return "bg-warn";
  return "bg-down";
}

export function SymbolArmorCard({ result, index }: { result: SymbolArmorResult; index: number }) {
  const isStale = !!result.is_stale;
  const unreliable = result.is_unreliable || result.data_dri < 40;

  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-2xl border bg-card p-3.5 shadow-[var(--shadow-card)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[var(--shadow-card-hover)]",
        unreliable ? "border-warn/30" : "border-line",
        isStale && "opacity-75 border-dashed"
      )}
      style={{ animationDelay: `${index * 30}ms` }}
    >
      {/* STALE / Unreliable badges */}
      <div className="absolute left-2 top-2 flex gap-1">
        {isStale && (
          <span className="inline-flex items-center gap-1 rounded-full bg-warn/15 px-2 py-0.5 text-[9px] font-bold text-warn">
            <Clock className="size-3" /> STALE
          </span>
        )}
        {unreliable && <span className="inline-flex items-center gap-1 rounded-full bg-down/15 px-2 py-0.5 text-[9px] font-bold text-down">Unreliable</span>}
      </div>

      {/* Symbol header */}
      <div className="flex items-start justify-between gap-2 pr-2">
        <div className="min-w-0">
          <p className="font-mono text-[13px] font-black text-ink truncate" dir="ltr">
            {result.symbol}
          </p>
          <p className="text-[10px] text-ink-3">
            گروه {result.group} · DRI {Math.round(result.data_dri)}
          </p>
        </div>
        <div className={cn("grid size-10 place-items-center rounded-xl border text-[11px] font-black tabular-nums", scoreBg(result.armor_score), scoreColor(result.armor_score))}>
          {Math.round(result.armor_score)}
        </div>
      </div>

      {/* DRI bar */}
      <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-soft">
        <div className={cn("h-full rounded-full transition-all", driColor(result.data_dri))} style={{ width: `${Math.min(100, Math.max(0, result.data_dri))}%` }} />
      </div>

      {/* Scores grid */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-soft px-2 py-2 text-center">
          <Shield className="mx-auto size-3.5 text-ink-3" />
          <p className={cn("mt-1 font-mono text-[12px] font-bold tabular-nums", scoreColor(result.technical_score))}>{Math.round(result.technical_score)}</p>
          <p className="text-[9px] text-ink-3">تکنیکال</p>
        </div>
        <div className="rounded-xl bg-soft px-2 py-2 text-center">
          <Droplets className="mx-auto size-3.5 text-ink-3" />
          <p className={cn("mt-1 font-mono text-[12px] font-bold tabular-nums", scoreColor(result.liquidity_score))}>{Math.round(result.liquidity_score)}</p>
          <p className="text-[9px] text-ink-3">نقدشوندگی</p>
        </div>
        <div className="rounded-xl bg-soft px-2 py-2 text-center">
          <TrendingUp className="mx-auto size-3.5 text-ink-3" />
          <p className={cn("mt-1 font-mono text-[12px] font-bold tabular-nums", scoreColor(result.money_flow_score))}>{Math.round(result.money_flow_score)}</p>
          <p className="text-[9px] text-ink-3">پول</p>
        </div>
      </div>

      {/* Price footer */}
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-2.5 text-[10px]">
        <span className="font-mono tabular-nums text-ink-2" dir="ltr">
          {result.last_price.toLocaleString("en-US")} <span className="text-ink-3">آخرین</span>
        </span>
        <span className="font-mono tabular-nums text-ink-3" dir="ltr">
          {result.closing_price.toLocaleString("en-US")} پایانی
        </span>
      </div>

      {/* Red flags */}
      {result.red_flags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {result.red_flags.slice(0, 3).map((flag) => (
            <span key={flag} className="inline-flex items-center gap-1 rounded-full bg-down/10 px-2 py-0.5 text-[9px] font-medium text-down">
              <AlertTriangle className="size-3" />
              {flag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default SymbolArmorCard;
