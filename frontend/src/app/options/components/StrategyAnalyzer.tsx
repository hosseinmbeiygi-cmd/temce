"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";
import type { StrategyInfo, StrategyAnalysis } from "./types";
import { fmt, riskColor, riskBg, riskLabel, marketLabel, PayoffDiagram } from "./helpers";

const STRATEGY_CATEGORIES = [
  { id: "all", label: "\u0647\u0645\u0647" },
  { id: "directional", label: "\u062c\u0647\u062a\u200c\u062f\u0627\u0631" },
  { id: "income", label: "\u062f\u0631\u0622\u0645\u062f" },
  { id: "volatility", label: "\u0646\u0648\u0633\u0627\u0646" },
  { id: "spread", label: "\u0627\u0633\u067e\u0631\u062f" },
  { id: "arbitrage", label: "\u0622\u0631\u0628\u06cc\u062a\u0631\u0627\u0698" },
  { id: "time", label: "\u0632\u0645\u0627\u0646" },
];

export default function StrategyAnalyzer() {
  const [category, setCategory] = useState("all");
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyInfo | null>(null);
  const [stockPrice, setStockPrice] = useState(1000);
  const [strike, setStrike] = useState(1000);
  const [callPremium, setCallPremium] = useState(50);
  const [putPremium, setPutPremium] = useState(30);

  const { data: strategiesResp, isLoading } = useQuery({
    queryKey: ["options", "strategies"],
    queryFn: () => apiGet<{ success: boolean; data: StrategyInfo[] }>("/options/strategies"),
    staleTime: 300_000,
  });

  const analyzeMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiPost<{ success: boolean; data: StrategyAnalysis }>("/options/analyze", body),
    onError: (err: Error) => toast.error(err.message),
  });

  const strategies = strategiesResp?.data ?? [];
  const filtered = category === "all" ? strategies : strategies.filter((s) => s.category === category);
  const analysis = analyzeMutation.data?.data;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Strategy List */}
      <Card title="\u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc\u200c\u0647\u0627" className="lg:col-span-1 max-h-[600px] overflow-y-auto">
        <div className="flex flex-wrap gap-1 mb-3">
          {STRATEGY_CATEGORIES.map((c) => (
            <button
              key={c.id}
              onClick={() => { setCategory(c.id); setSelectedStrategy(null); }}
              className={`px-2.5 py-1.5 rounded-lg text-[10px] font-bold transition-all border ${category === c.id ? "bg-primary-600 text-white border-primary-500" : "bg-surface-800 text-surface-400 border-surface-700/30 hover:bg-surface-700"}`}
            >
              {c.label}
            </button>
          ))}
        </div>
        {isLoading ? (
          <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : (
          <div className="space-y-1">
            {filtered.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedStrategy(s)}
                className={`w-full text-right p-2.5 rounded-xl transition-all text-xs border ${selectedStrategy?.id === s.id ? "bg-primary-600/20 border-primary-600/40" : "bg-surface-800/30 border-surface-700/30 hover:bg-surface-800/50"}`}
              >
                <div className="font-bold text-surface-200">{s.name_fa}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px]">{riskLabel(s.risk)}</span>
                  <span className="text-[10px] text-surface-400">{marketLabel(s.market)}</span>
                  <span className="text-[10px] text-surface-400">{s.legs} \u067e\u0627</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Analysis Panel */}
      <div className="lg:col-span-2 space-y-4">
        {selectedStrategy ? (
          <>
            <Card title={selectedStrategy.name_fa} subtitle={selectedStrategy.name}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div>
                  <label className="text-[10px] text-surface-500">\u0642\u06cc\u0645\u062a \u0633\u0647\u0645</label>
                  <input type="number" value={stockPrice} onChange={(e) => setStockPrice(Number(e.target.value))}
                    className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
                </div>
                <div>
                  <label className="text-[10px] text-surface-500">\u0642\u06cc\u0645\u062a \u0627\u0639\u0645\u0627\u0644</label>
                  <input type="number" value={strike} onChange={(e) => setStrike(Number(e.target.value))}
                    className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
                </div>
                <div>
                  <label className="text-[10px] text-surface-500">\u0642\u06cc\u0645\u062a \u0627\u062e\u062a\u06cc\u0627\u0631 \u062e\u0631\u06cc\u062f</label>
                  <input type="number" value={callPremium} onChange={(e) => setCallPremium(Number(e.target.value))}
                    className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
                </div>
                <div>
                  <label className="text-[10px] text-surface-500">\u0642\u06cc\u0645\u062a \u0627\u062e\u062a\u06cc\u0627\u0631 \u0641\u0631\u0648\u0634</label>
                  <input type="number" value={putPremium} onChange={(e) => setPutPremium(Number(e.target.value))}
                    className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
                </div>
              </div>
              <button
                onClick={() =>
                  analyzeMutation.mutate({
                    strategy: selectedStrategy.id,
                    stock_price: stockPrice,
                    strike,
                    call_premium: callPremium,
                    put_premium: putPremium,
                  })
                }
                disabled={analyzeMutation.isPending}
                className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50"
              >
                {analyzeMutation.isPending ? "\u062f\u0631 \u062d\u0627\u0644 \u062a\u062d\u0644\u06cc\u0644..." : "\u062a\u062d\u0644\u06cc\u0644 \u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc"}
              </button>
            </Card>

            {analyzeMutation.isPending && (
              <div className="space-y-3">
                <Skeleton className="h-48 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            )}

            {analysis && (
              <>
                {/* Payoff Diagram */}
                <Card title="\u0646\u0645\u0648\u062f\u0627\u0631 \u0633\u0648\u062f/\u0636\u06cc\u0627\u0646 \u062f\u0631 \u0633\u0631\u0631\u0633\u06cc\u062f">
                  <PayoffDiagram analysis={analysis} />
                </Card>

                {/* Results */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <Card className="text-center">
                    <p className="text-[10px] text-surface-500 mb-1">\u0628\u06cc\u0634\u062a\u0631\u06cc\u0646 \u0633\u0648\u062f</p>
                    <p className="text-lg font-bold text-accent-emerald">{fmt(analysis.max_profit)}</p>
                  </Card>
                  <Card className="text-center">
                    <p className="text-[10px] text-surface-500 mb-1">\u0628\u06cc\u0634\u062a\u0631\u06cc\u0646 \u0636\u06cc\u0627\u0646</p>
                    <p className="text-lg font-bold text-accent-rose">{fmt(analysis.max_loss)}</p>
                  </Card>
                  <Card className="text-center">
                    <p className="text-[10px] text-surface-500 mb-1">\u0647\u0632\u06cc\u0646\u0647 \u0627\u0648\u0644\u06cc\u0647</p>
                    <p className="text-lg font-bold text-surface-200">{fmt(analysis.initial_cost)}</p>
                  </Card>
                  <Card className="text-center">
                    <p className="text-[10px] text-surface-500 mb-1">\u0646\u0642\u0637\u0647 \u0633\u0631\u0628\u0647\u200c\u0633\u0631\u06cc</p>
                    <p className="text-lg font-bold text-accent-amber">{analysis.break_even.map(b => fmt(b)).join(", ")}</p>
                  </Card>
                </div>

                {/* Strategy Info */}
                <Card title="\u0627\u0637\u0644\u0627\u0639\u0627\u062a \u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc">
                  <div className="space-y-3 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-surface-500">\u0634\u0631\u0627\u06cc\u0637 \u0628\u0627\u0632\u0627\u0631:</span>
                      <span className="text-surface-200 font-bold">{marketLabel(analysis.market_condition)}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] border ${riskBg(analysis.risk_level)} ${riskColor(analysis.risk_level)}`}>
                        {riskLabel(analysis.risk_level)}
                      </span>
                    </div>
                    <div>
                      <span className="text-surface-500">\u062a\u0648\u0635\u06cc\u0647 \u0628\u0647:</span>
                      <p className="text-surface-200 mt-0.5">{analysis.best_for}</p>
                    </div>
                    <div>
                      <span className="text-surface-500">\u062a\u0648\u0636\u06cc\u062d:</span>
                      <p className="text-surface-300 mt-0.5 leading-relaxed">{analysis.description_fa}</p>
                    </div>
                    <div>
                      <span className="text-surface-500">\u067e\u0627\u0647\u0627:</span>
                      <div className="mt-1 space-y-1">
                        {analysis.legs.map((leg, i) => (
                          <div key={i} className="bg-surface-800/40 rounded-lg px-3 py-2 text-surface-300">
                            {leg.side === "buy" ? "\u062e\u0631\u06cc\u062f" : "\u0641\u0631\u0648\u0634"} {leg.type}
                            {leg.strike ? " - \u0627\u0639\u0645\u0627\u0644" : ""}
                            {leg.premium ? " - \u067e\u0631\u06cc\u0645\u06cc\u0648\u0645" : ""}
                            {leg.quantity > 1 ? " - \u062a\u0639\u062f\u0627\u062f" : ""}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </Card>
              </>
            )}
          </>
        ) : (
          <div className="flex items-center justify-center h-64 text-surface-500 text-sm">
            \u06cc\u06a9 \u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc \u0627\u0632 \u0644\u06cc\u0633\u062a \u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f
          </div>
        )}
      </div>
    </div>
  );
}
