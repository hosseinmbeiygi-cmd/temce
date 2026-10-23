"use client";

import { useMemo } from "react";
import { Coins, TrendingUp, Activity, Calculator } from "lucide-react";
import { fa } from "./helpers";

interface PreciousItem {
  symbol?: string;
  name?: string;
  price?: number;
}

interface RatioState {
  gold: number | null;
  silver: number | null;
  ratio: number | null;
  label: string;
  tone: string;
  note: string;
}

const HISTORICAL_BANDS = [
  { from: 30, to: 45, status: "طلا و نقره نسبتاً متعادل — نرخ تاریخی پایین", badge: "متعادل / پایین", tone: "text-warn" },
  { from: 45, to: 60, status: "طلا ممکن است بیش‌ارزش باشد", badge: "طلا در رده بالا", tone: "text-down" },
  { from: 60, to: 80, status: "طلا بسیار غالبی — نقره احتمالاً زیرارزش", badge: "نقره زیرارزش", tone: "text-down" },
  { from: 80, to: 999, status: "حباب طلا یا آسیب شدید نقره", badge: "غیرمعمول", tone: "text-rose-400" },
];

export default function GoldSilverRatioCard({ gold, silver }: { gold: number | null; silver: number | null }) {
  const ratioState = useMemo<RatioState>(() => {
    if (gold == null || silver == null || silver <= 0) {
      return { gold: null, silver: null, ratio: null, label: "نسبت ناکام", tone: "text-ink-3", note: "داده کافی برای محاسبه نسبت موجود نیست" };
    }
    const ratio = gold / silver;
    let label = "متعادل";
    let tone = "text-ink";
    let note = "طلا و نقره در بازه اندکی متعادل";
    for (const band of HISTORICAL_BANDS) {
      if (ratio >= band.from && ratio < band.to) {
        label = band.badge;
        tone = band.tone;
        note = band.status;
        break;
      }
    }
    if (ratio >= 80) {
      label = "نسبت غیرمعمول";
      tone = "text-rose-400";
      note = "نرخ تاریخی غالبی; ممکن است معامله‌های معکوس یا بررسیی نسبت به طلا توصیه شود";
    }
    return { gold, silver, ratio, label, tone, note };
  }, [gold, silver]);

  return (
    <div className="rounded-2xl border border-line bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-primary-500" />
          <h3 className="text-sm font-black text-ink">نسبت طلا به نقره (XAU/XAG)</h3>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {gold != null && <span className="font-mono text-ink-2">{fa(gold)}</span>}
          <span className="text-ink-3">÷</span>
          {silver != null && <span className="font-mono text-ink-2">{fa(silver)}</span>}
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="rounded-xl bg-soft/60 p-4 text-center">
          <p className="text-[10px] text-ink-3">نسبت لحظه‌ای</p>
          <p className={`mt-1 font-mono text-3xl font-black ${ratioState.tone}`} dir="ltr">
            {ratioState.ratio == null ? "—" : ratioState.ratio.toFixed(2)}
          </p>
          <p className={`mt-1 text-xs font-bold ${ratioState.tone}`}>{ratioState.label}</p>
        </div>

        <div className="grid gap-2 text-xs">
          <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-ink-3"><Coins className="size-4" /> قیمت طلا</span>
            <b className="font-mono text-ink" dir="ltr">{gold == null ? "—" : `${fa(gold)} $`}</b>
          </div>
          <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-ink-3"><Coins className="size-4" /> قیمت نقره</span>
            <b className="font-mono text-ink" dir="ltr">{silver == null ? "—" : `${fa(silver)} $`}</b>
          </div>
          <div className="rounded-xl bg-soft px-3 py-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-ink-3"><Calculator className="size-4" /> نسبت</span>
            <b className="font-mono text-ink" dir="ltr">{ratioState.ratio == null ? "—" : ratioState.ratio.toFixed(2) + ":1"}</b>
          </div>
        </div>

        <div className="rounded-xl border border-line bg-soft/30 p-3">
          <div className="flex items-center gap-2 text-[11px] text-ink-2">
            <Activity className="size-4 text-primary-500" />
            راهنمای وضعیت تاریخی
          </div>
          <p className="mt-1 text-[11px] text-ink-3">{ratioState.note}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[10px]">
        {HISTORICAL_BANDS.map((b) => (
          <span key={b.from} className={`rounded-full border px-2 py-1 ${ratioState.ratio != null && ratioState.ratio >= b.from && ratioState.ratio < b.to ? "border-primary-500 bg-primary-600/10 text-primary-600" : "border-line bg-soft text-ink-3"}`}>
            {b.from}:{b.to} — {b.badge}
          </span>
        ))}
      </div>
    </div>
  );
}
