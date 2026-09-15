"use client";

/**
 * ArbitrageTable — جدول فرصت‌های آربیتراژ بین صندوق‌های هم‌گروه.
 * برای هر گروه: گران‌ترین (P/NAV بالا) ← ارزان‌ترین (P/NAV پایین)؛ اسپرد = تفاوت.
 * Live: اتصال SSE به /funds/intraday/stream برای نمادهای کاندید (حداکثر ۵) —
 * با هر تیک، قیمت و به‌تبع آن P/NAV و اسپرد لحظه‌ای به‌روز می‌شود.
 */

import { useEffect, useMemo, useState } from "react";
import { calcBubble } from "@/lib/fund-categories";
import type { Fund } from "@/lib/fund-analysis";

interface ArbitrageTableProps {
  funds: Fund[];
  onPick?: (symbol: string) => void;
}

interface ArbRow {
  group: string;
  groupLabel: string;
  rich: { symbol: string; name: string; bubble: number };
  cheap: { symbol: string; name: string; bubble: number };
  spread: number; // pp
  matched: number; // تعداد صندوق‌های هم‌گروه
}

function detectGroupForArbitrage(fund: Fund): string {
  const lower = (fund.name || "").toLowerCase();
  if (/اهرمی|leverage/.test(lower) || fund.fund_type?.includes("leveraged")) return "leveraged";
  if (/طلا|gold/.test(lower) || fund.fund_type?.includes("gold")) return "gold";
  if (/درآمد ثابت|fixed/.test(lower)) return "fixed_income";
  if (/مختلط|mixed/.test(lower)) return "mixed";
  if (/شاخصی|index/.test(lower)) return "index";
  if (/بخشی|sector/.test(lower)) return "sector";
  return "equity";
}

const GROUP_DISPLAY: Record<string, { label: string; icon: string }> = {
  leveraged: { label: "اهرمی", icon: "⚡" },
  gold: { label: "طلا", icon: "💰" },
  fixed_income: { label: "درآمد ثابت", icon: "🏦" },
  mixed: { label: "مختلط", icon: "📊" },
  index: { label: "شاخصی", icon: "📈" },
  sector: { label: "بخشی", icon: "🏷️" },
  equity: { label: "سهامی", icon: "📉" },
};

export default function ArbitrageTable({ funds, onPick }: ArbitrageTableProps) {
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});

  const navMap = useMemo(() => new Map(funds.map((f) => [f.symbol, f.nav])), [funds]);

  const rows = useMemo<ArbRow[]>(() => {
    const byGroup = new Map<string, { symbol: string; name: string; bubble: number }[]>();
    for (const f of funds) {
      const b = calcBubble(f.price_last, f.nav);
      if (b === null) continue;
      const g = detectGroupForArbitrage(f);
      const list = byGroup.get(g) ?? [];
      list.push({ symbol: f.symbol, name: f.name, bubble: b });
      byGroup.set(g, list);
    }
    const out: ArbRow[] = [];
    byGroup.forEach((list, group) => {
      if (list.length < 2) return;
      const sorted = [...list].sort((a, b) => a.bubble - b.bubble);
      const cheap = sorted[0];
      const rich = sorted[sorted.length - 1];
      const spread = rich.bubble - cheap.bubble;
      if (spread < 1.5) return;
      out.push({
        group,
        groupLabel: `${GROUP_DISPLAY[group].icon} ${GROUP_DISPLAY[group].label}`,
        rich,
        cheap,
        spread,
        matched: list.length,
      });
    });
    return out.sort((a, b) => b.spread - a.spread).slice(0, 12);
  }, [funds]);

  // ── SSE live stream (فقط روی نمادهای کاندید، max 5) ──
  const streamSymbols = useMemo(
    () => [...new Set(rows.flatMap((r) => [r.rich.symbol, r.cheap.symbol]))].slice(0, 5),
    [rows]
  );
  const streamKey = streamSymbols.join(",");

  useEffect(() => {
    if (!streamSymbols.length) return;
    const base = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
    const es = new EventSource(
      `${base}/funds/intraday/stream?symbols=${encodeURIComponent(streamKey)}&poll_seconds=5`
    );
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as { type?: string; events?: { symbol?: string; price?: number | null }[] };
        if (msg.type === "ticks") {
          const events = msg.events;
          if (Array.isArray(events)) {
            setLivePrices((prev) => {
              const next = { ...prev };
              for (const ev of events) {
                if (ev.symbol && typeof ev.price === "number") next[ev.symbol] = ev.price;
              }
              return next;
            });
          }
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    // EventSource خودکار reconnect می‌کند؛ error handler برای جلوگیری از unhandled log
    es.onerror = () => {};
    return () => es.close();
  }, [streamKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // bubble زنده: قیمت تیک آخر / NAV ثابت
  const liveBubble = (symbol: string, fallback: number): { bubble: number; live: boolean } => {
    const price = livePrices[symbol];
    const nav = navMap.get(symbol);
    if (price && nav && nav > 0) {
      return { bubble: ((price - nav) / nav) * 100, live: true };
    }
    return { bubble: fallback, live: false };
  };

  const hasLive = Object.keys(livePrices).length > 0;

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-[13px] font-black text-ink flex items-center gap-2">
            <span className="material-icons text-base text-primary-400">sync_alt</span>
            فرصت‌های آربیتراژ — هم‌گروه
          </h3>
          <p className="text-[10px] text-ink-3 mt-0.5">
            اسپرد بین گران‌ترین و ارزان‌ترین صندوق هر گروه — بیش از ‎۱.۵٪ معنادار
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-ink-3">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          {hasLive ? "زنده (SSE)" : "لحظه‌ای"}
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="p-6 text-center text-ink-3 text-xs">
          <p className="text-3xl mb-2">⚖️</p>
          فعلاً اسپرد معناداری بین صندوق‌های هم‌گروه پیدا نشد.
        </div>
      ) : (
        <div className="overflow-x-auto -mx-2">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-ink-3 text-[9px] uppercase tracking-wider">
                <th className="text-right px-2 py-1.5 font-bold">گروه</th>
                <th className="text-right px-2 py-1.5 font-bold">گران‌ترین</th>
                <th className="text-center px-2 py-1.5 font-bold">حباب</th>
                <th className="text-right px-2 py-1.5 font-bold">ارزان‌ترین</th>
                <th className="text-center px-2 py-1.5 font-bold">حباب</th>
                <th className="text-center px-2 py-1.5 font-bold">اسپرد</th>
                <th className="text-center px-2 py-1.5 font-bold"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const richLive = liveBubble(r.rich.symbol, r.rich.bubble);
                const cheapLive = liveBubble(r.cheap.symbol, r.cheap.bubble);
                const spread = richLive.bubble - cheapLive.bubble;
                return (
                  <tr key={r.group} className="border-t border-line/40 hover:bg-soft/40 transition-colors">
                    <td className="px-2 py-2">
                      <span className="font-bold text-ink">{r.groupLabel}</span>
                      <span className="block text-[8px] text-ink-3">{r.matched} صندوق</span>
                    </td>
                    <td className="px-2 py-2">
                      <button onClick={() => onPick?.(r.rich.symbol)} className="font-mono text-rose-300 hover:underline font-bold">
                        {r.rich.symbol}
                      </button>
                      <p className="text-[8px] text-ink-3 truncate max-w-[140px]">{r.rich.name}</p>
                    </td>
                    <td className="text-center px-2 py-2 font-mono font-bold text-rose-300">
                      +{richLive.bubble.toFixed(2)}٪{richLive.live && <span className="text-[7px] text-emerald-400 align-top mr-0.5">●</span>}
                    </td>
                    <td className="px-2 py-2">
                      <button onClick={() => onPick?.(r.cheap.symbol)} className="font-mono text-emerald-300 hover:underline font-bold relative">
                        <span className="absolute -right-1 top-1 flex h-1.5 w-1.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
                        </span>
                        {r.cheap.symbol}
                      </button>
                      <p className="text-[8px] text-ink-3 truncate max-w-[140px]">{r.cheap.name}</p>
                    </td>
                    <td className="text-center px-2 py-2 font-mono font-bold text-emerald-300">
                      {cheapLive.bubble > 0 ? "+" : ""}{cheapLive.bubble.toFixed(2)}٪{cheapLive.live && <span className="text-[7px] text-emerald-400 align-top mr-0.5">●</span>}
                    </td>
                    <td className="text-center px-2 py-2">
                      <span className="px-2 py-0.5 rounded-md bg-primary-600/20 text-primary-300 font-mono font-black">
                        {spread.toFixed(2)}٪
                      </span>
                    </td>
                    <td className="text-center px-2 py-2">
                      <button
                        onClick={() => onPick?.(r.cheap.symbol)}
                        title={`مشاهده ${r.cheap.symbol}`}
                        className="px-2 py-1 rounded-md bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 text-[9px] font-bold transition-colors"
                      >
                        بررسی ←
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[8px] text-ink-3/60 mt-3 leading-relaxed">
        ⚠ آربیتراژ در صندوق‌ها به‌دلیل کارمزد، صف خرید/فروش و مالیات، اسپرد واقعی کمتر از عدد نمایش‌داده‌شده است.
      </p>
    </div>
  );
}