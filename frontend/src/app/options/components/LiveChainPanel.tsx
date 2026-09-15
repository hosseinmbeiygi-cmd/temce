"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";
import type { ChainData } from "./types";
import { fmt } from "./helpers";

const UNDERLYING_PRESETS = [
  "\u0630\u0648\u0628", "\u0641\u062e\u0632", "\u0648\u0627\u0645\u062f", "\u06a9\u0686\u0627\u062f",
  "\u0634\u067e\u0646\u0627", "\u0648\u0628\u0635\u0627", "\u0641\u0627\u062e\u0631", "\u0648\u067e\u0645\u06cc",
];

export default function LiveChainPanel() {
  const [underlying, setUnderlying] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["options", "chain", underlying],
    queryFn: () =>
      apiGet<{ success: boolean; data: ChainData }>(`/options/live/chain/${encodeURIComponent(underlying)}?limit=50`),
    enabled: !!underlying,
    refetchInterval: 15_000,
  });

  const chain = data?.data;
  const calls = chain?.calls ?? [];
  const puts = chain?.puts ?? [];

  return (
    <div className="space-y-4">
      {/* Underlying Selector */}
      <Card title="\u0633\u0645\u0628\u0644 \u067e\u0627\u06cc\u0647">
        <div className="flex flex-wrap gap-2">
          {UNDERLYING_PRESETS.map((sym) => (
            <button
              key={sym}
              onClick={() => setUnderlying(sym)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${underlying === sym ? "bg-primary-600 text-white border-primary-500" : "bg-surface-800 text-surface-300 border-surface-700/30 hover:bg-surface-700"}`}
            >
              {sym}
            </button>
          ))}
          <input
            value={underlying}
            onChange={(e) => setUnderlying(e.target.value.toUpperCase())}
            placeholder="\u0633\u0627\u06cc\u0631 \u0633\u0645\u0628\u0644\u200c\u0647\u0627..."
            className="flex-1 min-w-[120px] bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-1.5 text-xs text-surface-200"
          />
        </div>
      </Card>

      {!underlying && (
        <div className="flex items-center justify-center h-32 text-surface-500 text-sm">
          \u06cc\u06a9 \u0633\u0645\u0628\u0644 \u067e\u0627\u06cc\u0647 \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f
        </div>
      )}

      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {error && (
        <div className="text-accent-rose text-sm text-center py-4">
          \u062e\u0637\u0627 \u062f\u0631 \u062f\u0631\u06cc\u0627\u0641\u062a \u062f\u0627\u062f\u0647\u200c\u0647\u0627
        </div>
      )}

      {chain && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">{chain.underlying}</p>
              <p className="text-lg font-bold text-surface-200">{fmt(chain.underlying_price)}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">Call\u200c\u0647\u0627</p>
              <p className="text-lg font-bold text-accent-emerald">{calls.length}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">Put\u200c\u0647\u0627</p>
              <p className="text-lg font-bold text-accent-rose">{puts.length}</p>
            </Card>
            <Card className="text-center">
              <p className="text-[10px] text-surface-500">\u0642\u0631\u0627\u0631\u062f\u0627\u062f</p>
              <p className="text-lg font-bold text-surface-200">{fmt(chain.total_contracts)}</p>
            </Card>
          </div>

          {/* Options Chain Table */}
          <Card title="\u0632\u0646\u062c\u06cc\u0631\u0647 \u0627\u062e\u062a\u06cc\u0627\u0631\u0647\u0627">
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-surface-500 border-b border-surface-700/50">
                    <th className="text-right py-2 px-2">\u0633\u0645\u0628\u0644</th>
                    <th className="text-right py-2 px-2">\u0646\u0648\u0639</th>
                    <th className="text-left py-2 px-2">\u0627\u0639\u0645\u0627\u0644</th>
                    <th className="text-left py-2 px-2">\u0642\u06cc\u0645\u062a</th>
                    <th className="text-left py-2 px-2">\u062d\u062c\u0645</th>
                    <th className="text-left py-2 px-2">\u0639\u0644\u0627\u0642\u0647 \u0628\u0627\u0632</th>
                    <th className="text-left py-2 px-2">\u062a\u0627 \u0633\u0631\u0631\u0633\u06cc\u062f</th>
                    <th className="text-left py-2 px-2">\u0628\u06cc\u062f/\u062e\u0648\u0627\u0633\u062a</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ...calls.map(c => ({ ...c, rowType: "call" as const })),
                    ...puts.map(p => ({ ...p, rowType: "put" as const })),
                  ].map((opt, i) => (
                    <tr
                      key={i}
                      className="order-b border-surface-800/30 hover:bg-surface-800/30"
                    >
                      <td className="py-2 px-2 font-bold">{opt.symbol}</td>
                      <td className="py-2 px-2 ">
                        {opt.rowType === "call" ? "Call" : "Put"}
                      </td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.strike)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.price)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.volume)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{fmt(opt.oi)}</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">{opt.days_to_expiry} \u0631\u0648\u0632</td>
                      <td className="py-2 px-2 text-left font-mono" dir="ltr">
                        {fmt(opt.bid)} / {fmt(opt.ask)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
