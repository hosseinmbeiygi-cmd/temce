"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import { apiGet, apiPost } from "@/lib/api";
import type { CostResult, SizingResult, IvRankResult, ChecklistItem } from "./types";
import { fmt } from "./helpers";

type ToolTab = "costs" | "sizing" | "ivrank" | "checklist";

export default function ProfessionalTools() {
  const [tab, setTab] = useState<ToolTab>("costs");

  const [costParams, setCostParams] = useState({ stock_price: 1000, strike: 1000, premium: 50, contracts: 1, is_call: true, is_buy: true });
  const [sizingParams, setSizingParams] = useState({ capital: 100_000_000, risk_per_trade: 0.02, max_loss_per_contract: 100_000 });
  const [ivParams, setIvParams] = useState({ stock_price: 1000, strike: 1000, time_to_expiry: 0.25, option_price: 50, option_type: "call" });

  const costsMutation = useMutation({
    mutationFn: (p: typeof costParams) =>
      apiPost<{ success: boolean; data: CostResult }>("/api/v1/options/professional/costs", {
        stock_price: p.stock_price,
        strike: p.strike,
        premium: p.premium,
        contracts: p.contracts,
        is_call: p.is_call,
        is_buy: p.is_buy,
      }),
    onError: (err) => toast.error(err.message),
  });

  const sizingMutation = useMutation({
    mutationFn: (p: typeof sizingParams) =>
      apiPost<{ success: boolean; data: SizingResult }>("/api/v1/options/professional/position-sizing", p),
    onError: (err) => toast.error(err.message),
  });

  const ivRankMutation = useMutation({
    mutationFn: (p: typeof ivParams) =>
      apiPost<{ success: boolean; data: IvRankResult }>("/api/v1/options/professional/iv-rank", p),
    onError: (err) => toast.error(err.message),
  });

  const checklistMutation = useMutation({
    mutationFn: () =>
      apiPost<{ success: boolean; data: ChecklistItem[] }>("/api/v1/options/professional/checklist", {}),
    onError: (err) => toast.error(err.message),
  });

  const { data: iranCosts } = useMutation({
    mutationFn: () => apiGet<{ success: boolean; data: Record<string, any> }>("/api/v1/options/professional/iran-costs"),
  });

  const tabs = [
    { id: "costs" as ToolTab, label: "\u0645\u062d\u0627\u0633\u0628\u0647 \u06a9\u0627\u0631\u0645\u0632\u062f" },
    { id: "sizing" as ToolTab, label: "\u0627\u0646\u062f\u0627\u0632\u0647 \u0645\u0639\u0627\u0645\u0644\u0647" },
    { id: "ivrank" as ToolTab, label: "IV Rank" },
    { id: "checklist" as ToolTab, label: "\u0686\u06a9\u200c\u0644\u06cc\u0633\u062a" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-1 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className="flex-1 py-2 rounded-lg text-xs font-bold transition-all"
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "costs" && (
        <Card title="\u0645\u062d\u0627\u0633\u0628\u0647 \u0647\u0632\u06cc\u0646\u0647\u200c\u0647\u0627 \u0648 \u06a9\u0627\u0631\u0645\u0632\u062f\u0647\u0627">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            {[
              { k: "stock_price", l: "\u0642\u06cc\u0645\u062a \u0633\u0647\u0645", v: costParams.stock_price },
              { k: "strike", l: "\u0627\u0639\u0645\u0627\u0644", v: costParams.strike },
              { k: "premium", l: "\u067e\u0631\u06cc\u0645\u06cc\u0648\u0645", v: costParams.premium },
              { k: "contracts", l: "\u062a\u0639\u062f\u0627\u062f \u0642\u0631\u0627\u0631\u062f\u0627\u062f", v: costParams.contracts },
            ].map((f) => (
              <div key={f.k}>
                <label className="text-[10px] text-surface-500">{f.l}</label>
                <input type="number" value={f.v}
                  onChange={(e) => setCostParams(p => ({ ...p, [f.k]: Number(e.target.value) }))}
                  className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mb-4">
            <button onClick={() => setCostParams(p => ({ ...p, is_call: true }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Call</button>
            <button onClick={() => setCostParams(p => ({ ...p, is_call: false }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Put</button>
            <button onClick={() => setCostParams(p => ({ ...p, is_buy: true }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">\u062e\u0631\u06cc\u062f</button>
            <button onClick={() => setCostParams(p => ({ ...p, is_buy: false }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">\u0641\u0631\u0648\u0634</button>
          </div>
          <button onClick={() => costsMutation.mutate(costParams)}
            disabled={costsMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            {costsMutation.isPending ? "\u062f\u0631 \u062d\u0627\u0644 \u0645\u062d\u0627\u0633\u0628\u0647..." : "\u0645\u062d\u0627\u0633\u0628\u0647"}
          </button>
          {costsMutation.data?.data && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              {[
                { l: "\u0633\u0648\u062f \u0646\u0627\u062e\u0627\u0644\u0635", v: fmt(costsMutation.data.data.gross_pnl) },
                { l: "\u06a9\u0627\u0631\u0645\u0632\u062f", v: fmt(costsMutation.data.data.commission) },
                { l: "\u0633\u0648\u062f \u062e\u0627\u0644\u0635", v: fmt(costsMutation.data.data.net_pnl) },
                { l: "\u062f\u0631\u0635\u062f \u0633\u0648\u062f", v: costsMutation.data.data.net_pnl_pct.toFixed(2) + "\u066a" },
              ].map((r) => (
                <div key={r.l} className="bg-surface-800/40 rounded-xl p-2.5 text-center">
                  <p className="text-[10px] text-surface-500">{r.l}</p>
                  <p className="text-sm font-bold text-surface-200">{r.v}</p>
                </div>
              ))}
              <div className="bg-surface-800/40 rounded-xl p-2.5 text-center col-span-2 md:col-span-4">
                <p className="text-[10px] text-surface-500">\u0646\u0642\u0637\u0647 \u0633\u0631\u0628\u0647\u200c\u0633\u0631\u06cc</p>
                <p className="text-sm font-bold text-accent-amber">{fmt(costsMutation.data.data.breakeven)}</p>
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "sizing" && (
        <Card title="\u0645\u062d\u0627\u0633\u0628\u0647 \u0627\u0646\u062f\u0627\u0632\u0647 \u0645\u0639\u0627\u0645\u0644\u0647">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            {[
              { k: "capital", l: "\u0633\u0631\u0645\u0627\u06cc\u0647 (\u062a\u0648\u0645\u0627\u0646)", v: sizingParams.capital },
              { k: "risk_per_trade", l: "\u0631\u06cc\u0633\u06a9 \u0628\u0647 \u0627\u0632\u0627\u06cc \u0645\u0639\u0627\u0645\u0644\u0647", v: sizingParams.risk_per_trade },
              { k: "max_loss_per_contract", l: "\u062d\u062f\u0627\u06a9\u062b\u0631 \u0636\u06cc\u0627\u0646 \u0628\u0647 \u0627\u0632\u0627\u06cc \u0642\u0631\u0627\u0631\u062f\u0627\u062f", v: sizingParams.max_loss_per_contract },
            ].map((f) => (
              <div key={f.k}>
                <label className="text-[10px] text-surface-500">{f.l}</label>
                <input type="number" value={f.v}
                  onChange={(e) => setSizingParams(p => ({ ...p, [f.k]: Number(e.target.value) }))}
                  className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
              </div>
            ))}
          </div>
          <button onClick={() => sizingMutation.mutate(sizingParams)}
            disabled={sizingMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            \u0645\u062d\u0627\u0633\u0628\u0647 \u0627\u0646\u062f\u0627\u0632\u0647
          </button>
          {sizingMutation.data?.data && (
            <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
              <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                <p className="text-[10px] text-surface-500">\u062d\u062f\u0627\u06a9\u062b\u0631 \u0642\u0631\u0627\u0631\u062f\u0627\u062f</p>
                <p className="text-lg font-bold text-surface-200">{sizingMutation.data.data.max_contracts}</p>
              </div>
              <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                <p className="text-[10px] text-surface-500">\u0647\u0632\u06cc\u0646\u0647 \u06a9\u0644</p>
                <p className="text-lg font-bold text-surface-200">{fmt(sizingMutation.data.data.total_cost)}</p>
              </div>
              <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                <p className="text-[10px] text-surface-500">\u062f\u0631\u0635\u062f \u0633\u0631\u0645\u0627\u06cc\u0647</p>
                <p className="text-lg font-bold text-surface-200">{sizingMutation.data.data.pct_of_capital}\u066a</p>
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "ivrank" && (
        <Card title="IV Rank \u0648 \u067e\u0631\u0633\u0646\u062a\u0627\u06cc\u0644">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {[
              { k: "stock_price", l: "\u0642\u06cc\u0645\u062a \u0633\u0647\u0645", v: ivParams.stock_price },
              { k: "strike", l: "\u0627\u0639\u0645\u0627\u0644", v: ivParams.strike },
              { k: "time_to_expiry", l: "\u0632\u0645\u0627\u0646 \u062a\u0627 \u0633\u0631\u0631\u0633\u06cc\u062f", v: ivParams.time_to_expiry },
              { k: "option_price", l: "\u0642\u06cc\u0645\u062a \u0627\u062e\u062a\u06cc\u0627\u0631", v: ivParams.option_price },
            ].map((f) => (
              <div key={f.k}>
                <label className="text-[10px] text-surface-500">{f.l}</label>
                <input type="number" step="any" value={f.v}
                  onChange={(e) => setIvParams(p => ({ ...p, [f.k]: Number(e.target.value) }))}
                  className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mb-4">
            <button onClick={() => setIvParams(p => ({ ...p, option_type: "call" }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Call</button>
            <button onClick={() => setIvParams(p => ({ ...p, option_type: "put" }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Put</button>
          </div>
          <button onClick={() => ivRankMutation.mutate(ivParams)}
            disabled={ivRankMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            \u0645\u062d\u0627\u0633\u0628\u0647 IV Rank
          </button>
          {ivRankMutation.data?.data && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500">IV Rank</p>
                  <p className="text-lg font-bold text-surface-200">{ivRankMutation.data.data.rank.toFixed(2)}</p>
                </div>
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500">\u067e\u0631\u0633\u0646\u062a\u0627\u06cc\u0644</p>
                  <p className="text-lg font-bold text-surface-200">{ivRankMutation.data.data.percentile.toFixed(1)}\u066a</p>
                </div>
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500">\u062a\u0641\u0633\u06cc\u0631</p>
                  <p className="text-sm font-bold text-accent-amber">{ivRankMutation.data.data.interpretation_fa}</p>
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "checklist" && (
        <Card title="\u0686\u06a9\u200c\u0644\u06cc\u0633\u062a \u067e\u06cc\u0634 \u0627\u0632 \u0645\u0639\u0627\u0645\u0644\u0647">
          <button onClick={() => checklistMutation.mutate()}
            disabled={checklistMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50 mb-4">
            \u062f\u0631\u06cc\u0627\u0641\u062a \u0686\u06a9\u200c\u0644\u06cc\u0633\u062a
          </button>
          {checklistMutation.data?.data && Array.isArray(checklistMutation.data.data) && (
            <div className="space-y-2">
              {checklistMutation.data.data.map((item: any, i: number) => (
                <div key={i} className="flex items-start gap-3 bg-surface-800/40 rounded-xl p-3">
                  <span className="text-accent-emerald mt-0.5">\u2713</span>
                  <div>
                    <p className="text-xs font-bold text-surface-200">{item.check_fa || item.check}</p>
                    <p className="text-[10px] text-surface-500 mt-0.5">{item.detail || item.check_fa}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
