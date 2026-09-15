"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import type { LiveSymbol } from "./types";
import { fmt, riskColor, riskLabel, marketLabel } from "./helpers";

export default function OptionsDashboard() {
  const { data: liveSymbols, isLoading: symLoading } = useQuery({
    queryKey: ["options", "live-symbols"],
    queryFn: () => apiGet<{ success: boolean; data: LiveSymbol[] }>("/api/v1/options/live/symbols"),
    refetchInterval: 30_000,
  });

  const { data: strategies } = useQuery({
    queryKey: ["options", "strategies"],
    queryFn: () => apiGet<{ success: boolean; data: any[] }>("/api/v1/options/strategies"),
    staleTime: 300_000,
  });

  const { data: iranCosts } = useQuery({
    queryKey: ["options", "iran-costs"],
    queryFn: () => apiGet<{ success: boolean; data: Record<string, any> }>("/api/v1/options/professional/iran-costs"),
    staleTime: 600_000,
  });

  const symbols = liveSymbols?.data ?? [];
  const strategiesList = strategies?.data ?? [];
  const costs = iranCosts?.data;

  const totalContracts = symbols.reduce((s, x) => s + x.contracts, 0);
  const totalVolume = symbols.reduce((s, x) => s + x.volume, 0);

  return (
    <div className="space-y-6">
      {/* Live Market Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="text-center">
          <p className="text-[10px] text-surface-500 mb-1">\u0633\u0645\u0628\u0644\u200c\u0647\u0627\u06cc \u0641\u0639\u0627\u0644</p>
          <p className="text-2xl font-bold text-surface-200">{symLoading ? "\u2026" : fmt(symbols.length)}</p>
        </Card>
        <Card className="text-center">
          <p className="text-[10px] text-surface-500 mb-1">\u0642\u0631\u0627\u0631\u062f\u0627\u062f\u0647\u0627\u06cc \u0641\u0639\u0627\u0644</p>
          <p className="text-2xl font-bold text-surface-200">{symLoading ? "\u2026" : fmt(totalContracts)}</p>
        </Card>
        <Card className="text-center">
          <p className="text-[10px] text-surface-500 mb-1">\u062d\u062c\u0645 \u06a9\u0644</p>
          <p className="text-2xl font-bold text-surface-200">{symLoading ? "\u2026" : fmt(totalVolume)}</p>
        </Card>
        <Card className="text-center">
          <p className="text-[10px] text-surface-500 mb-1">\u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc\u200c\u0647\u0627</p>
          <p className="text-2xl font-bold text-accent-amber">{strategiesList.length}</p>
        </Card>
      </div>

      {/* Live Symbols Table */}
      <Card title="\u0633\u0645\u0628\u0644\u200c\u0647\u0627\u06cc \u062f\u0627\u0631\u0627\u06cc \u0627\u062e\u062a\u06cc\u0627\u0631 \u0645\u0639\u0627\u0645\u0644\u0647">
        {symLoading ? (
          <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
        ) : symbols.length === 0 ? (
          <p className="text-surface-500 text-sm py-4 text-center">\u0627\u0637\u0644\u0627\u0639\u0627\u062a\u06cc \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700/50">
                  <th className="text-right py-2">\u0633\u0645\u0628\u0644</th>
                  <th className="text-right py-2">\u0642\u0631\u0627\u0631\u062f\u0627\u062f</th>
                  <th className="text-left py-2">\u062d\u062c\u0645</th>
                  <th className="text-left py-2">\u0642\u06cc\u0645\u062a \u0646\u0627\u0634\u06cc</th>
                </tr>
              </thead>
              <tbody>
                {symbols.slice(0, 10).map((s) => (
                  <tr key={s.symbol} className="border-b border-surface-800/50 hover:bg-surface-800/30">
                    <td className="py-2.5 font-bold text-surface-200">{s.symbol}</td>
                    <td className="py-2.5 text-surface-300">{fmt(s.contracts)}</td>
                    <td className="py-2.5 text-surface-300 text-left" dir="ltr">{fmt(s.volume)}</td>
                    <td className="py-2.5 text-surface-300 text-left" dir="ltr">{fmt(s.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Market Rules */}
      <Card title="\u0642\u0648\u0627\u0646\u06cc\u0646 \u0628\u0627\u0632\u0627\u0631 \u0627\u06cc\u0631\u0627\u0646" className="md:col-span-2">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          {[
            { l: "\u06a9\u0627\u0631\u0645\u0632\u062f \u062e\u0631\u06cc\u062f", v: "\u0660.\u0661\u0662\u0665\u066a" },
            { l: "\u06a9\u0627\u0631\u0645\u0632\u062f \u0641\u0631\u0648\u0634", v: "\u0660.\u0666\u0662\u0665\u066a (\u0634\u0627\u0645\u0644 \u0645\u0627\u0644\u06cc\u0627\u062a)" },
            { l: "\u062a\u0633\u0648\u06cc\u0647", v: "T+2" },
            { l: "\u0627\u0646\u062f\u0627\u0632\u0647 \u0642\u0631\u0627\u0631\u062f\u0627\u062f", v: "\u0661,\u0660\u0660\u0660 \u0633\u0647\u0645" },
            { l: "\u0645\u062d\u062f\u0648\u062f\u06cc\u062a \u0642\u06cc\u0645\u062a", v: "\u00b1\u0661\u0669\u066a (\u0627\u062e\u062a\u06cc\u0627\u0631)" },
            { l: "\u0633\u0628\u06a9 \u0627\u0639\u0645\u0627\u0644", v: "\u0627\u0631\u0648\u067e\u0627\u06cc\u06cc" },
            { l: "\u0641\u0631\u0648\u0634 \u0641\u0632\u0627\u06cc\u0646\u062f\u0647", v: "\u0645\u0645\u0646\u0648\u0639" },
            { l: "\u062d\u062f\u0627\u0642\u0644 \u0633\u0631\u0645\u0627\u06cc\u0647", v: "\u0665\u0660 \u0645\u06cc\u0644\u06cc\u0648\u0646 \u062a\u0648\u0645\u0627\u0646" },
          ].map(r => (
            <div key={r.l} className="bg-surface-800/50 rounded-xl p-2.5">
              <p className="text-surface-500 text-[10px]">{r.l}</p>
              <p className="text-surface-200 mt-0.5">{r.v}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
