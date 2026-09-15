"use client";

/** صفحه بازار فیزیکی — حباب سکه + آربیتراژ ETF ↔ فیزیکی */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  getArbitrage,
  getGoldLivePrices,
  postCoinBubble,
  type ArbitrageResp,
  type CoinBubbleResp,
} from "@/lib/goldApi";

const fmt = (n: number | null | undefined, digits = 0): string => {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("fa-IR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

const fmtPct = (n: number | null | undefined, digits = 2): string => {
  if (n === null || n === undefined) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}٪`;
};

const bubbleTone = (signal: string) => {
  if (signal === "BUY") return { text: "text-emerald-300", bg: "bg-emerald-500/10", ring: "ring-emerald-500/40", label: "خرید" };
  if (signal === "SELL") return { text: "text-rose-300", bg: "bg-rose-500/10", ring: "ring-rose-500/40", label: "فروش" };
  return { text: "text-amber-300", bg: "bg-amber-500/10", ring: "ring-amber-500/40", label: "خنثی" };
};

const arbTone = (action: string) => {
  if (action === "BUY_ETF_SELL_PHYSICAL")
    return { text: "text-emerald-300", bg: "bg-emerald-500/10", ring: "ring-emerald-500/40" };
  if (action === "BUY_PHYSICAL_SELL_ETF")
    return { text: "text-rose-300", bg: "bg-rose-500/10", ring: "ring-rose-500/40" };
  return { text: "text-zinc-300", bg: "bg-zinc-700/30", ring: "ring-zinc-600/30" };
};

export default function GoldPhysicalPage() {
  // Live
  const { data: live } = useQuery({
    queryKey: ["gold", "live"],
    queryFn: () => getGoldLivePrices(),
    refetchInterval: 5000,
  });

  // Coin bubble — auto-calc از live prices
  const bubbleMut = useMutation({
    mutationFn: (p: { coin: number; oz: number; usd: number }) =>
      postCoinBubble({
        coin_price_irr: p.coin,
        gold_oz_usd: p.oz,
        usd_irr: p.usd,
      }),
  });

  // اگر live موجود، محاسبه خودکار
  useState(() => {
    if (live?.coin_bahar_irr && live?.gold_oz_usd && live?.usd_irr) {
      bubbleMut.mutate({
        coin: live.coin_bahar_irr,
        oz: live.gold_oz_usd,
        usd: live.usd_irr,
      });
    }
  });

  // Arbitrage
  const { data: arb } = useQuery({
    queryKey: ["gold", "arbitrage"],
    queryFn: getArbitrage,
    refetchInterval: 10_000,
  });

  // Manual inputs (override)
  const [manualCoin, setManualCoin] = useState<number | undefined>(undefined);
  const [manualOz, setManualOz] = useState<number | undefined>(undefined);
  const [manualUsd, setManualUsd] = useState<number | undefined>(undefined);

  const handleManualCalc = () => {
    bubbleMut.mutate({
      coin: manualCoin ?? live?.coin_bahar_irr ?? 0,
      oz: manualOz ?? live?.gold_oz_usd ?? 0,
      usd: manualUsd ?? live?.usd_irr ?? 0,
    });
  };

  const b: CoinBubbleResp | undefined = bubbleMut.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">بازار فیزیکی و آربیتراژ</h1>
        <p className="text-xs text-zinc-500 mt-1">
          رصد قیمت سکه، طلای آب‌شده و کشف فرصت آربیتراژ ETF ↔ فیزیکی
        </p>
      </div>

      {/* Live prices */}
      {live && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <PriceTile
            label="سکه بهار آزادی"
            value={fmt(live.coin_bahar_irr)}
            unit="ریال"
          />
          <PriceTile label="طلای ۱۸ عیار (گرم)" value={fmt(live.gold_18k_irr)} unit="ریال" />
          <PriceTile label="اونس جهانی" value={fmt(live.gold_oz_usd, 2)} unit="USD" />
          <PriceTile label="دلار آزاد" value={fmt(live.usd_irr)} unit="ریال" />
        </div>
      )}

      {/* Coin Bubble */}
      <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-5">
        <h2 className="text-base font-semibold text-zinc-200 mb-4">🫧 حباب سکه بهار آزادی</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <Input
            label="قیمت سکه (ریال)"
            value={manualCoin ?? live?.coin_bahar_irr}
            onChange={(v) => setManualCoin(v)}
          />
          <Input
            label="اونس (USD)"
            value={manualOz ?? live?.gold_oz_usd}
            onChange={(v) => setManualOz(v)}
          />
          <Input
            label="دلار (ریال)"
            value={manualUsd ?? live?.usd_irr}
            onChange={(v) => setManualUsd(v)}
          />
        </div>
        <button
          onClick={handleManualCalc}
          disabled={bubbleMut.isPending}
          className="w-full bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 ring-1 ring-amber-500/40 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-50"
        >
          {bubbleMut.isPending ? "..." : "محاسبه حباب"}
        </button>
        {b && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
            <BubbleResult b={b} />
          </div>
        )}
      </div>

      {/* Arbitrage */}
      <div className="rounded-xl ring-1 ring-zinc-800/60 bg-zinc-900/40 backdrop-blur p-5">
        <h2 className="text-base font-semibold text-zinc-200 mb-4">⚡ اسکنر آربیتراژ</h2>
        {arb ? (
          <ArbitrageCard a={arb} />
        ) : (
          <div className="text-zinc-500 text-sm text-center py-4">
            در حال بررسی بازار...
          </div>
        )}
      </div>
    </div>
  );
}

function PriceTile({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="rounded-lg border border-zinc-700/50 bg-zinc-900/60 p-3">
      <div className="text-[10px] text-zinc-400 mb-1">{label}</div>
      <div className="text-lg font-bold text-amber-300 tabular-nums">
        {value}
        <span className="text-[10px] text-zinc-500 mr-1">{unit}</span>
      </div>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
}) {
  return (
    <div>
      <label className="text-xs text-zinc-400 mb-1 block">{label}</label>
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? +e.target.value : undefined)}
        className="w-full bg-zinc-800/60 border border-zinc-700/60 rounded-lg px-3 py-2 text-sm text-zinc-100 tabular-nums"
      />
    </div>
  );
}

function BubbleResult({ b }: { b: CoinBubbleResp }) {
  const t = bubbleTone(b.signal);
  return (
    <div
      className={`rounded-lg ring-1 ${t.ring} ${t.bg} p-4 backdrop-blur`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-zinc-300">حباب / تخفیف</div>
        <span
          className={`text-[10px] px-2 py-0.5 rounded-full ring-1 ${t.ring} ${t.text}`}
        >
          {t.label}
        </span>
      </div>
      <div className={`text-3xl font-black tabular-nums ${t.text} mb-2`}>
        {fmtPct(b.bubble_pct, 1)}
      </div>
      <div className="text-xs text-zinc-400 space-y-1">
        <div>ذاتی: <span className="text-zinc-200 tabular-nums">{fmt(b.coin_intrinsic_irr)}</span> ریال</div>
        <div>بازار: <span className="text-zinc-200 tabular-nums">{fmt(b.coin_market_irr)}</span> ریال</div>
        <div className="leading-relaxed pt-2 border-t border-zinc-800/40">{b.reason}</div>
      </div>
    </div>
  );
}

function ArbitrageCard({ a }: { a: ArbitrageResp }) {
  const t = arbTone(a.action);
  return (
    <div className={`rounded-lg ring-1 ${t.ring} ${t.bg} p-4`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-sm font-semibold text-zinc-100">{a.pair}</div>
          <div className="text-[10px] text-zinc-500 mt-0.5">Spread Analysis</div>
        </div>
        <span
          className={`text-[10px] px-2 py-1 rounded ring-1 ${t.ring} ${t.text} font-semibold`}
        >
          {a.action.replace(/_/g, " ")}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <div className="text-[10px] text-zinc-500">Gross Spread</div>
          <div className="text-lg font-bold text-zinc-200 tabular-nums">
            {fmtPct(a.gross_spread_pct)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500">Net (after fees)</div>
          <div className={`text-lg font-bold tabular-nums ${t.text}`}>
            {fmtPct(a.net_spread_pct)}
          </div>
        </div>
      </div>
      <div className="text-xs text-zinc-300 leading-relaxed border-t border-zinc-800/40 pt-2">
        {a.strategy}
      </div>
    </div>
  );
}
