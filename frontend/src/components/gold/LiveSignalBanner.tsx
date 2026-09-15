"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { subscribeGoldWS } from "@/lib/goldApi";

interface Signal {
  symbol: string;
  signal_type: string;
  severity: string;
  title: string;
  description: string;
  current_value: number;
  threshold: number;
  change_pct: number | null;
  ts: number;
}

const SEVERITY_BG: Record<string, string> = {
  info: "bg-blue-500/15 border-blue-500/40 text-blue-200",
  warn: "bg-amber-500/15 border-amber-500/40 text-amber-200",
  critical: "bg-rose-500/15 border-rose-500/40 text-rose-200",
};

const TYPE_LABEL: Record<string, string> = {
  spike_up: "📈 جهش",
  spike_down: "📉 ریزش",
  score_change: "📊 تغییر امتیاز",
  bubble_extreme: "🔴 حباب شدید",
};

const BEEP_FREQ = { info: 600, warn: 800, critical: 1200 };

function playBeep(freq: number) {
  if (typeof window === "undefined" || !window.AudioContext) return;
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
    osc.start();
    osc.stop(ctx.currentTime + 0.2);
  } catch {
    // ignore
  }
}

export function LiveSignalBanner() {
  const { data } = useQuery({
    queryKey: ["gold", "signals", "recent"],
    queryFn: async () => {
      const r = await apiGet<{ success: boolean; data: { signals: Signal[] } }>("/api/gold/signals/recent?limit=10");
      return r.data;
    },
    refetchInterval: 30_000,
  });

  const seenIds = useRef<Set<number>>(new Set());
  const [activeSignals, setActiveSignals] = useState<Signal[]>([]);

  // WS listener برای signal جدید
  useEffect(() => {
    if (typeof window === "undefined") return;
    const unsub = subscribeGoldWS((snap) => {
      // WS messages: فقط snapshot می‌فرسته. signal از API می‌آید
      void snap;
    });
    return unsub;
  }, []);

  // detect new signals + beep
  useEffect(() => {
    if (!data?.signals) return;
    const fresh = data.signals.filter((s) => !seenIds.current.has(s.ts));
    if (fresh.length > 0) {
      // beep فقط برای signal جدید (نه initial load)
      const isFirstLoad = seenIds.current.size === 0;
      if (!isFirstLoad) {
        fresh.forEach((s) => {
          const freq = (BEEP_FREQ as Record<string, number>)[s.severity] ?? 600;
          playBeep(freq);
        });
      }
      fresh.forEach((s) => seenIds.current.add(s.ts));
      setActiveSignals(fresh.slice(0, 3));
      const t = setTimeout(() => setActiveSignals([]), 8000);
      return () => clearTimeout(t);
    }
  }, [data]);

  if (activeSignals.length === 0) return null;

  return (
    <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 space-y-2 w-full max-w-md pointer-events-none">
      {activeSignals.map((s, i) => (
        <div
          key={s.ts + "_" + i}
          className={`rounded-xl border p-3 backdrop-blur-xl shadow-2xl ${SEVERITY_BG[s.severity] || SEVERITY_BG.info} fade-in pointer-events-auto`}
        >
          <div className="flex items-start gap-2">
            <div className="text-2xl">{TYPE_LABEL[s.signal_type]?.split(" ")[0] || "🔔"}</div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold">{s.title}</div>
              <div className="text-xs opacity-80 mt-0.5">{s.description}</div>
              {s.change_pct !== null && (
                <div className="text-[10px] opacity-60 mt-1 font-mono">
                  {s.change_pct > 0 ? "+" : ""}
                  {s.change_pct.toFixed(2)}٪
                </div>
              )}
            </div>
            <button
              onClick={() => setActiveSignals((prev) => prev.filter((x) => x.ts !== s.ts))}
              className="text-xs opacity-60 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
