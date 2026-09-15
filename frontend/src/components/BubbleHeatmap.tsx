"use client";

/**
 * BubbleHeatmap — ماتریس رنگی P/NAV به تفکیک گروه صندوق.
 * سبز تیره = زیر NAV (فرصت ورود)؛ قرمز تیره = حباب بالای ۳٪+ (خروج).
 * سلول‌ها قابل کلیک → فقط هایلایت؛ navigation به drawer در والد انجام می‌شود.
 */

import { useMemo } from "react";
import { FUND_GROUPS, calcBubble, type FundGroup, type FundGroupDef } from "@/lib/fund-categories";
import type { Fund } from "@/lib/fund-analysis";

interface BubbleHeatmapProps {
  funds: Fund[];
  onPickGroup?: (group: FundGroup) => void;
  activeGroup?: FundGroup | "all";
}

interface GroupCell {
  group: FundGroupDef;
  count: number;
  avgBubble: number | null;
  discountCount: number; // bubble < -2%
  bubbleCount: number;   // bubble > +3%
  topSymbol: { symbol: string; bubble: number } | null;
  intensity: number; // 0..1 برای رنگ پس‌زمینه
}

function heatColor(bubble: number | null): { bg: string; text: string } {
  if (bubble === null) return { bg: "bg-soft/50", text: "text-ink-3" };
  if (bubble <= -3) return { bg: "bg-emerald-500/30", text: "text-emerald-200" };
  if (bubble <= -1) return { bg: "bg-emerald-500/15", text: "text-emerald-300" };
  if (bubble < 1) return { bg: "bg-zinc-700/40", text: "text-ink-2" };
  if (bubble < 3) return { bg: "bg-amber-500/20", text: "text-amber-300" };
  if (bubble < 5) return { bg: "bg-rose-500/25", text: "text-rose-300" };
  return { bg: "bg-rose-600/40", text: "text-rose-200" };
}

export default function BubbleHeatmap({ funds, onPickGroup, activeGroup }: BubbleHeatmapProps) {
  const cells = useMemo<GroupCell[]>(() => {
    return FUND_GROUPS.map((g) => {
      const inGroup = funds.filter((f) => {
        // تشخیص گروه بر اساس fund_type/name ساده — همان الگوی صفحه /funds
        const lowerName = (f.name || "").toLowerCase();
        if (g.id === "leveraged") return /اهرمی|leverage/.test(lowerName) || f.fund_type?.includes("leveraged");
        if (g.id === "gold") return /طلا|gold/.test(lowerName) || f.fund_type?.includes("gold");
        if (g.id === "fixed_income") return /درآمد ثابت|fixed/.test(lowerName);
        if (g.id === "mixed") return /مختلط|mixed/.test(lowerName);
        if (g.id === "index") return /شاخصی|index/.test(lowerName);
        if (g.id === "sector") return /بخشی|sector/.test(lowerName);
        return f.fund_type?.includes("equity") || /سهامی/.test(lowerName);
      });

      const bubbles = inGroup
        .map((f) => calcBubble(f.price_last, f.nav))
        .filter((b): b is number => b !== null);

      const avg = bubbles.length ? bubbles.reduce((s, b) => s + b, 0) / bubbles.length : null;
      const discount = bubbles.filter((b) => b < -2).length;
      const bubbly = bubbles.filter((b) => b > 3).length;

      let top: GroupCell["topSymbol"] = null;
      for (const f of inGroup) {
        const b = calcBubble(f.price_last, f.nav);
        if (b === null) continue;
        if (!top || b > top.bubble) top = { symbol: f.symbol, bubble: b };
      }

      const intensity = avg === null ? 0 : Math.min(1, Math.abs(avg) / 5);
      return { group: g, count: inGroup.length, avgBubble: avg, discountCount: discount, bubbleCount: bubbly, topSymbol: top, intensity };
    });
  }, [funds]);

  const totalDiscount = cells.reduce((s, c) => s + c.discountCount, 0);
  const totalBubble = cells.reduce((s, c) => s + c.bubbleCount, 0);

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-[13px] font-black text-ink flex items-center gap-2">
            <span className="material-icons text-base text-primary-400">grid_view</span>
            هیت‌مپ حباب P/NAV — تفکیک گروه
          </h3>
          <p className="text-[10px] text-ink-3 mt-0.5">
            سبز = تخفیف (فرصت ورود) · قرمز = حباب (احتیاط)
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 font-bold">{totalDiscount} تخفیف</span>
          <span className="px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-300 font-bold">{totalBubble} حباب</span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {cells.map((c) => {
          const color = heatColor(c.avgBubble);
          const isActive = activeGroup === c.group.id;
          return (
            <button
              key={c.group.id}
              onClick={() => onPickGroup?.(c.group.id)}
              className={`${color.bg} ${isActive ? "ring-2 ring-primary-500" : "ring-1 ring-line/50"} rounded-xl p-3 text-right transition-all hover:scale-[1.02] hover:ring-primary-400 cursor-pointer`}
            >
              <div className="flex items-start justify-between mb-1">
                <span className="text-base">{c.group.icon}</span>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${c.count > 0 ? "bg-black/30" : "bg-black/10"} text-ink-2`}>
                  {c.count}
                </span>
              </div>
              <p className={`text-[11px] font-black leading-tight mb-1 ${color.text}`}>
                {c.group.label}
              </p>
              <p className={`text-[15px] font-mono font-black ${color.text}`}>
                {c.avgBubble === null ? "—" : `${c.avgBubble > 0 ? "+" : ""}${c.avgBubble.toFixed(2)}٪`}
              </p>
              <div className="flex items-center gap-1 mt-1.5">
                {c.discountCount > 0 && (
                  <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/30 text-emerald-200 font-bold">
                    -{c.discountCount}
                  </span>
                )}
                {c.bubbleCount > 0 && (
                  <span className="text-[8px] px-1 py-0.5 rounded bg-rose-500/30 text-rose-200 font-bold">
                    +{c.bubbleCount}
                  </span>
                )}
              </div>
              {c.topSymbol && c.topSymbol.bubble > 3 && (
                <p className="text-[8px] text-rose-300/60 mt-1 truncate">
                  ▲ {c.topSymbol.symbol}
                </p>
              )}
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-2 mt-3 text-[8px] text-ink-3">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/30" /> ‎-۳٪ یا کمتر</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-zinc-700/40" /> خنثی</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500/20" /> ‎+۱٪</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-rose-600/40" /> ‎+۵٪ یا بیشتر</span>
      </div>
    </div>
  );
}