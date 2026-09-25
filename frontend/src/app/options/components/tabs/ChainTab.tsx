"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowLeftRight, Loader2 } from "lucide-react";
import { apiGet } from "@/lib/api";
import { fmt } from "../helpers";
import { TableSkeleton } from "./Skeleton";
import type { ChainData, LiveSymbol, OptionContract } from "../types";

type Source = "tsetmc" | "ime";
type Moneyness = "all" | "itm" | "atm" | "otm";

const IME_COMMODITIES = [
  { id: "GoldBar", label: "شمش طلا" },
  { id: "ZR", label: "زعفران (ZR)" },
  { id: "SilverBar", label: "شمش نقره" },
];

function moneynessOf(leg: OptionContract, spot: number): "ITM" | "ATM" | "OTM" {
  if (!spot) return "OTM";
  const strike = leg.strike;
  const isCall = (leg.type ?? "").toLowerCase() === "call" || leg.symbol?.includes("C");
  const diffPct = Math.abs(strike - spot) / spot;
  if (diffPct <= 0.03) return "ATM";
  if (isCall) return strike < spot ? "ITM" : "OTM";
  return strike > spot ? "ITM" : "OTM";
}

function spreadPct(leg: OptionContract): number | null {
  if (!leg.bid || !leg.ask) return null;
  const mid = (leg.bid + leg.ask) / 2;
  return mid > 0 ? ((leg.ask - leg.bid) / mid) * 100 : null;
}

const MONEYESSES = ["all", "itm", "atm", "otm"] as const;
const MONEY_LABEL: Record<string, string> = {
  all: "همه",
  itm: "ITM",
  atm: "ATM",
  otm: "OTM",
};

function LegTable({
  title,
  legs,
  accent,
  spot,
  moneyness,
  maxSpread,
  minOi,
}: {
  title: string;
  legs: OptionContract[];
  accent: string;
  spot: number;
  moneyness: Moneyness;
  maxSpread: number;
  minOi: number;
}) {
  const rows = legs.filter((l) => {
    const m = moneynessOf(l, spot);
    if (moneyness !== "all" && m.toLowerCase() !== moneyness) return false;
    if (minOi > 0 && (l.oi ?? 0) < minOi) return false;
    const sp = spreadPct(l);
    if (maxSpread > 0 && sp !== null && sp > maxSpread) return false;
    return true;
  });

  if (!legs.length) return null;
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
      <div className={`px-4 py-2 text-xs font-bold flex items-center justify-between ${accent}`}>
        <span>{title}</span>
        <span className="text-slate-500 font-normal">{rows.length} از {legs.length}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" dir="ltr">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-2 py-2 font-normal">Strike</th>
              <th className="px-2 py-2 font-normal">Price</th>
              <th className="px-2 py-2 font-normal">Bid/Ask</th>
              <th className="px-2 py-2 font-normal">Spr%</th>
              <th className="px-2 py-2 font-normal">Vol</th>
              <th className="px-2 py-2 font-normal">OI</th>
              <th className="px-2 py-2 font-normal">DTE</th>
              <th className="px-2 py-2 font-normal">M</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {rows.slice(0, 15).map((l) => {
              const sp = spreadPct(l);
              const m = moneynessOf(l, spot);
              const mColor = m === "ITM" ? "text-emerald-400" : m === "ATM" ? "text-amber-400" : "text-slate-500";
              return (
                <tr key={l.symbol} className="border-b border-slate-800/50 hover:bg-slate-800/40 text-slate-200">
                  <td className="px-2 py-1.5">{fmt(l.strike)}</td>
                  <td className="px-2 py-1.5">{fmt(l.price)}</td>
                  <td className="px-2 py-1.5 text-slate-400">{fmt(l.bid)}/{fmt(l.ask)}</td>
                  <td className={`px-2 py-1.5 ${(sp ?? 0) > maxSpread ? "text-rose-400" : "text-slate-400"}`}>
                    {sp === null ? "—" : sp.toFixed(1)}
                  </td>
                  <td className="px-2 py-1.5">{fmt(l.volume)}</td>
                  <td className="px-2 py-1.5">{fmt(l.oi)}</td>
                  <td className="px-2 py-1.5">{l.days_to_expiry}</td>
                  <td className={`px-2 py-1.5 font-bold ${mColor}`}>{m}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ChainTab() {
  const [source, setSource] = useState<Source>("tsetmc");
  const [symbols, setSymbols] = useState<LiveSymbol[]>([]);
  const [underlying, setUnderlying] = useState("");
  const [commodity, setCommodity] = useState("GoldBar");
  const [chain, setChain] = useState<ChainData | null>(null);
  const [loading, setLoading] = useState(false);
  const [imeReady, setImeReady] = useState(true);
  // Liquidity & moneyness filters (mission tab 2)
  const [moneyness, setMoneyness] = useState<Moneyness>("all");
  const [minOi, setMinOi] = useState("0");
  const [maxSpread, setMaxSpread] = useState("15");

  useEffect(() => {
    if (source !== "tsetmc") return;
    apiGet<{ success: boolean; data: LiveSymbol[] }>("/options/live/symbols")
      .then((r) => {
        const list = r.success ? r.data ?? [] : [];
        setSymbols(list);
        if (list.length && !underlying) setUnderlying(list[0].symbol);
      })
      .catch(() => setSymbols([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  useEffect(() => {
    const key = source === "tsetmc" ? underlying : commodity;
    if (!key) return;
    setLoading(true);
    const url =
      source === "tsetmc"
        ? `/options/live/chain/${encodeURIComponent(underlying)}?limit=50`
        : `/options/live/commodity-chain?commodity=${encodeURIComponent(commodity)}&limit=50`;
    apiGet<{ success: boolean; data: ChainData }>(url)
      .then((r) => {
        setChain(r.success ? r.data : null);
        if (source === "ime") setImeReady(r.success);
      })
      .catch(() => {
        setChain(null);
        if (source === "ime") setImeReady(false);
      })
      .finally(() => setLoading(false));
  }, [source, underlying, commodity]);

  const spot = chain?.underlying_price ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setSource(source === "tsetmc" ? "ime" : "tsetmc")}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-slate-900 border border-slate-700 text-slate-200 hover:border-emerald-600/60"
        >
          <ArrowLeftRight size={14} className="text-emerald-400" />
          {source === "tsetmc" ? "آپشن سهام (TSETMC)" : "آپشن کالا (IME)"}
        </button>
        {source === "tsetmc" ? (
          <select
            value={underlying}
            onChange={(e) => setUnderlying(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200"
          >
            {symbols.map((s) => (
              <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
            ))}
          </select>
        ) : (
          <div className="flex gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
            {IME_COMMODITIES.map((c) => (
              <button
                key={c.id}
                onClick={() => setCommodity(c.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold ${commodity === c.id ? "bg-amber-600 text-white" : "text-slate-400 hover:text-slate-200"}`}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}

        {/* Liquidity + moneyness filters */}
        <div className="flex gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
          {MONEYESSES.map((m) => (
            <button
              key={m}
              onClick={() => setMoneyness(m)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-bold ${moneyness === m ? "bg-slate-700 text-white" : "text-slate-400 hover:text-slate-200"}`}
            >
              {MONEY_LABEL[m]}
            </button>
          ))}
        </div>
        <input
          value={minOi}
          onChange={(e) => setMinOi(e.target.value)}
          placeholder="حداقل OI"
          inputMode="numeric"
          className="bg-slate-900 border border-slate-700 rounded-xl px-2.5 py-2 text-xs text-slate-200 w-24 font-mono"
          dir="ltr"
        />
        <input
          value={maxSpread}
          onChange={(e) => setMaxSpread(e.target.value)}
          placeholder="حداکثر Spread%"
          inputMode="decimal"
          className="bg-slate-900 border border-slate-700 rounded-xl px-2.5 py-2 text-xs text-slate-200 w-28 font-mono"
          dir="ltr"
        />
        {loading && <Loader2 size={16} className="animate-spin text-slate-500" />}
      </div>

      {loading && <TableSkeleton />}

      {source === "ime" && !imeReady && !loading && (
        <div className="text-center text-amber-400/90 text-xs bg-amber-500/10 border border-amber-500/30 rounded-2xl py-4">
          دادهٔ زنجیره کالایی IME در دسترس نیست (جدول brsapi_ime_options خالی یا دیتابیس قطع است).
        </div>
      )}

      {chain && (
        <>
          <div className="text-xs text-slate-400">
            قیمت مبنا: <span className="font-mono text-slate-200" dir="ltr">{fmt(chain.underlying_price)}</span>
            <span className="text-slate-600"> • {chain.total_contracts} قرارداد</span>
            {source === "ime" && <span className="text-slate-600"> • مدل: Black-76 (بورس کالا)</span>}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <LegTable title="کال (Call)" legs={chain.calls} accent="text-emerald-400" spot={spot} moneyness={moneyness} maxSpread={Number(maxSpread) || 0} minOi={Number(minOi) || 0} />
            <LegTable title="پوت (Put)" legs={chain.puts} accent="text-rose-400" spot={spot} moneyness={moneyness} maxSpread={Number(maxSpread) || 0} minOi={Number(minOi) || 0} />
          </div>
        </>
      )}
    </div>
  );
}
