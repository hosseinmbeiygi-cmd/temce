"use client";

import { useEffect, useState } from "react";
import { ArrowLeftRight, Loader2 } from "lucide-react";
import { apiGet } from "@/lib/api";
import { fmt } from "../helpers";
import type { ChainData, LiveSymbol, OptionContract } from "../types";

type Source = "tsetmc" | "ime";

const IME_COMMODITIES = [
  { id: "GoldBar", label: "شمش طلا" },
  { id: "ZR", label: "زعفران (ZR)" },
  { id: "SilverBar", label: "شمش نقره" },
];

function LegTable({ title, legs, accent }: { title: string; legs: OptionContract[]; accent: string }) {
  if (!legs.length) return null;
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
      <div className={`px-4 py-2 text-xs font-bold ${accent}`}>{title}</div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" dir="ltr">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="px-3 py-2 font-normal">Strike</th>
              <th className="px-3 py-2 font-normal">Price</th>
              <th className="px-3 py-2 font-normal">Bid/Ask</th>
              <th className="px-3 py-2 font-normal">Vol</th>
              <th className="px-3 py-2 font-normal">OI</th>
              <th className="px-3 py-2 font-normal">DTE</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {legs.slice(0, 12).map((l) => (
              <tr key={l.symbol} className="border-b border-slate-800/50 hover:bg-slate-800/40 text-slate-200">
                <td className="px-3 py-1.5">{fmt(l.strike)}</td>
                <td className="px-3 py-1.5">{fmt(l.price)}</td>
                <td className="px-3 py-1.5 text-slate-400">{fmt(l.bid)}/{fmt(l.ask)}</td>
                <td className="px-3 py-1.5">{fmt(l.volume)}</td>
                <td className="px-3 py-1.5">{fmt(l.oi)}</td>
                <td className="px-3 py-1.5">{l.days_to_expiry}</td>
              </tr>
            ))}
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
        {loading && <Loader2 size={16} className="animate-spin text-slate-500" />}
      </div>

      {source === "ime" && !imeReady && (
        <div className="text-center text-amber-400/90 text-xs bg-amber-500/10 border border-amber-500/30 rounded-2xl py-4">
          زنجیره کالایی هنوز به بک‌اند متصل نیست (GET /options/live/commodity-chain در راه است).
        </div>
      )}

      {chain && (
        <>
          <div className="text-xs text-slate-400">
            قیمت مبنا: <span className="font-mono text-slate-200" dir="ltr">{fmt(chain.underlying_price)}</span>
            <span className="text-slate-600"> • {chain.total_contracts} قرارداد</span>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <LegTable title="کال (Call)" legs={chain.calls} accent="text-emerald-400" />
            <LegTable title="پوت (Put)" legs={chain.puts} accent="text-rose-400" />
          </div>
        </>
      )}
    </div>
  );
}
