"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import { apiGet, apiPost } from "@/lib/api";
import type { GreeksResult, ArbitrageParity, VolatilityAnalysis, PortfolioAnalysis } from "./types";
import { fmt, fmtPct, riskColor, riskLabel } from "./helpers";

type Tab = "greeks" | "arbitrage" | "volatility" | "portfolio";

export default function AnalyticsPanel() {
  const [tab, setTab] = useState<Tab>("greeks");
  const [greeksParams, setGreeksParams] = useState({ stock_price: 1000, strike: 1000, time_to_expiry: 0.25, volatility: 0.35, option_type: "call" });
  const [arbParams, setArbParams] = useState({ call_price: 100, put_price: 80, stock_price: 1000, strike: 1000, time_to_expiry: 0.25 });
  const [volParams, setVolParams] = useState({ stock_price: 1000, option_price: 80, strike: 1000, time_to_expiry: 0.25, option_type: "call" });
  const [portfolioParams, setPortfolioParams] = useState({ positions: JSON.stringify([{ type: "call", side: "buy", quantity: 1, strike: 1000, premium: 50, time_to_expiry: 0.25 }], null, 2), stock_price: 1000 });

  const greeksMutation = useMutation({
    mutationFn: (p: typeof greeksParams) => apiGet<{ success: boolean; data: GreeksResult }>("/api/v1/options/greeks?" + new URLSearchParams(p as any)),
    onError: (err) => toast.error(err.message),
  });

  const arbitrageMutation = useMutation({
    mutationFn: (p: typeof arbParams) => apiGet<{ success: boolean; data: ArbitrageParity }>("/api/v1/options/analytics/arbitrage/parity?" + new URLSearchParams(p as any)),
    onError: (err) => toast.error(err.message),
  });

  const volatilityMutation = useMutation({
    mutationFn: (p: typeof volParams) => apiPost<{ success: boolean; data: VolatilityAnalysis }>("/api/v1/options/analytics/volatility", p),
    onError: (err) => toast.error(err.message),
  });

  const portfolioMutation = useMutation({
    mutationFn: (p: typeof portfolioParams) => apiPost<{ success: boolean; data: PortfolioAnalysis }>("/api/v1/options/analytics/portfolio", { positions: JSON.parse(p.positions), stock_price: p.stock_price }),
    onError: (err) => toast.error(err.message),
  });

  const tabs = [
    { id: "greeks" as Tab, label: "\u06cc\u0648\u0646\u0627\u0646\u200c\u0647\u0627 (\u0627\u063a\u0631\u06cc\u06a9)" },
    { id: "arbitrage" as Tab, label: "\u0622\u0631\u0628\u06cc\u062a\u0631\u0627\u0698" },
    { id: "volatility" as Tab, label: "\u0646\u0648\u0633\u0627\u0646" },
    { id: "portfolio" as Tab, label: "\u067e\u0648\u0631\u062a\u0641\u0648\u06cc" },
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

      {tab === "greeks" && (
        <Card title="\u0645\u062d\u0627\u0633\u0628\u0647 \u06cc\u0648\u0646\u0627\u0646\u200c\u0647\u0627">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {[
              { k: "stock_price", l: "\u0642\u06cc\u0645\u062a \u0633\u0647\u0645", v: greeksParams.stock_price },
              { k: "strike", l: "\u0627\u0639\u0645\u0627\u0644", v: greeksParams.strike },
              { k: "time_to_expiry", l: "\u0632\u0645\u0627\u0646 \u062a\u0627 \u0633\u0631\u0631\u0633\u06cc\u062f", v: greeksParams.time_to_expiry },
              { k: "volatility", l: "\u0646\u0648\u0633\u0627\u0646", v: greeksParams.volatility },
            ].map((f) => (
              <div key={f.k}>
                <label className="text-[10px] text-surface-500">{f.l}</label>
                <input type="number" step="any" value={f.v}
                  onChange={(e) => setGreeksParams(p => ({ ...p, [f.k]: Number(e.target.value) }))}
                  className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mb-4">
            <button onClick={() => setGreeksParams(p => ({ ...p, option_type: "call" }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Call</button>
            <button onClick={() => setGreeksParams(p => ({ ...p, option_type: "put" }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Put</button>
          </div>
          <button onClick={() => greeksMutation.mutate(greeksParams)}
            disabled={greeksMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            {greeksMutation.isPending ? "\u062f\u0631 \u062d\u0627\u0644 \u0645\u062d\u0627\u0633\u0628\u0647..." : "\u0645\u062d\u0627\u0633\u0628\u0647 \u06cc\u0648\u0646\u0627\u0646\u200c\u0647\u0627"}
          </button>
          {greeksMutation.data?.data && (
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mt-4">
              {[
                { l: "\u0394 Delta", v: greeksMutation.data.data.delta },
                { l: "\u0393 Gamma", v: greeksMutation.data.data.gamma },
                { l: "\u0398 Theta", v: greeksMutation.data.data.theta },
                { l: "\u039d Vega", v: greeksMutation.data.data.vega },
                { l: "\u03a1 Rho", v: greeksMutation.data.data.rho },
                { l: "\u0627\u0631\u0632\u0634 \u0630\u0627\u062a\u06cc", v: greeksMutation.data.data.intrinsic_value },
              ].map((g) => (
                <div key={g.l} className="bg-surface-800/40 rounded-xl p-2.5 text-center">
                  <p className="text-[10px] text-surface-500">{g.l}</p>
                  <p className="text-sm font-bold text-surface-200 font-mono mt-0.5" dir="ltr">{typeof g.v === "number" ? g.v.toFixed(4) : g.v}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {tab === "arbitrage" && (
        <Card title="\u0628\u0631\u0631\u0633\u06cc \u067e\u0627\u0631\u06cc\u062a\u06cc \u067e\u0648\u062a-\u06a9\u0627\u0644">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            {[
              { k: "call_price", l: "\u0642\u06cc\u0645\u062a Call", v: arbParams.call_price },
              { k: "put_price", l: "\u0642\u06cc\u0645\u062a Put", v: arbParams.put_price },
              { k: "stock_price", l: "\u0642\u06cc\u0645\u062a \u0633\u0647\u0645", v: arbParams.stock_price },
              { k: "strike", l: "\u0627\u0639\u0645\u0627\u0644", v: arbParams.strike },
              { k: "time_to_expiry", l: "\u0632\u0645\u0627\u0646 \u062a\u0627 \u0633\u0631\u0631\u0633\u06cc\u062f", v: arbParams.time_to_expiry },
            ].map((f) => (
              <div key={f.k}>
                <label className="text-[10px] text-surface-500">{f.l}</label>
                <input type="number" step="any" value={f.v}
                  onChange={(e) => setArbParams(p => ({ ...p, [f.k]: Number(e.target.value) }))}
                  className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
              </div>
            ))}
          </div>
          <button onClick={() => arbitrageMutation.mutate(arbParams)}
            disabled={arbitrageMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            \u0628\u0631\u0631\u0633\u06cc \u067e\u0627\u0631\u06cc\u062a\u06cc
          </button>
          {arbitrageMutation.data?.data && (
            <div className="mt-4 space-y-3">
              <div className="rounded-xl p-3">
                <p className="text-sm font-bold mb-1">
                  {arbitrageMutation.data.data.parity_violated ? "\u26a0 \u0646\u0642\u0636 \u067e\u0627\u0631\u06cc\u062a\u06cc \u06a9\u0634\u0641 \u0634\u062f" : "\u2713 \u067e\u0627\u0631\u06cc\u062a\u06cc \u0628\u0631\u0642\u0631\u0627\u0631 \u0627\u0633\u062a"}
                </p>
                {arbitrageMutation.data.data.parity_violated && (
                  <>
                    <p className="text-xs text-surface-300 mt-1">{arbitrageMutation.data.data.action_fa}</p>
                    <p className="text-xs text-accent-emerald mt-1">\u0633\u0648\u062f \u067e\u062a\u0627\u0646\u0633\u06cc\u0644: {fmt(arbitrageMutation.data.data.profit ?? 0)}</p>
                  </>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-surface-800/40 rounded-lg p-2"><span className="text-surface-500">\u0637\u0631\u0641 \u0686\u067e:</span> <span className="text-surface-200 font-mono" dir="ltr">{arbitrageMutation.data.data.left_side}</span></div>
                <div className="bg-surface-800/40 rounded-lg p-2"><span className="text-surface-500">\u0637\u0631\u0641 \u0631\u0627\u0633\u062a:</span> <span className="text-surface-200 font-mono" dir="ltr">{arbitrageMutation.data.data.right_side}</span></div>
                <div className="bg-surface-800/40 rounded-lg p-2"><span className="text-surface-500">\u0627\u062e\u062a\u0644\u0627\u0641:</span> <span className="text-surface-200 font-mono" dir="ltr">{arbitrageMutation.data.data.difference}</span></div>
                <div className="bg-surface-800/40 rounded-lg p-2"><span className="text-surface-500">Call \u062a\u0626\u0648\u0631\u06cc\u06a9:</span> <span className="text-surface-200 font-mono" dir="ltr">{arbitrageMutation.data.data.theoretical_call}</span></div>
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "volatility" && (
        <Card title="\u062a\u062d\u0644\u06cc\u0644 \u0646\u0648\u0633\u0627\u0646">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            {[
              { k: "stock_price", l: "\u0642\u06cc\u0645\u062a \u0633\u0647\u0645", v: volParams.stock_price },
              { k: "option_price", l: "\u0642\u06cc\u0645\u062a \u0627\u062e\u062a\u06cc\u0627\u0631", v: volParams.option_price },
              { k: "strike", l: "\u0627\u0639\u0645\u0627\u0644", v: volParams.strike },
              { k: "time_to_expiry", l: "\u0632\u0645\u0627\u0646 \u062a\u0627 \u0633\u0631\u0631\u0633\u06cc\u062f", v: volParams.time_to_expiry },
            ].map((f) => (
              <div key={f.k}>
                <label className="text-[10px] text-surface-500">{f.l}</label>
                <input type="number" step="any" value={f.v}
                  onChange={(e) => setVolParams(p => ({ ...p, [f.k]: Number(e.target.value) }))}
                  className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mb-4">
            <button onClick={() => setVolParams(p => ({ ...p, option_type: "call" }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Call</button>
            <button onClick={() => setVolParams(p => ({ ...p, option_type: "put" }))}
              className="px-3 py-1.5 rounded-lg text-xs font-bold ">Put</button>
          </div>
          <button onClick={() => volatilityMutation.mutate(volParams)}
            disabled={volatilityMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            \u062a\u062d\u0644\u06cc\u0644 \u0646\u0648\u0633\u0627\u0646
          </button>
          {volatilityMutation.data?.data && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-surface-500 text-[10px]">IV</p>
                  <p className="text-lg font-bold text-surface-200 font-mono" dir="ltr">{fmtPct(volatilityMutation.data.data.implied_volatility / 100)}</p>
                </div>
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-surface-500 text-[10px]">HV</p>
                  <p className="text-lg font-bold text-surface-200 font-mono" dir="ltr">{fmtPct(volatilityMutation.data.data.historical_volatility / 100)}</p>
                </div>
              </div>
              <div className="bg-surface-800/30 rounded-xl p-3 text-xs text-surface-300 leading-relaxed">
                {volatilityMutation.data.data.interpretation}
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "portfolio" && (
        <Card title="\u062a\u062d\u0644\u06cc\u0644 \u067e\u0648\u0631\u062a\u0641\u0648\u06cc">
          <div className="mb-4">
            <label className="text-[10px] text-surface-500">\u0642\u06cc\u0645\u062a \u0633\u0647\u0645</label>
            <input type="number" value={portfolioParams.stock_price}
              onChange={(e) => setPortfolioParams(p => ({ ...p, stock_price: Number(e.target.value) }))}
              className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
          </div>
          <div className="mb-4">
            <label className="text-[10px] text-surface-500">\u067e\u0632\u06cc\u0634\u0648\u0646\u200c\u0647\u0627 (JSON)</label>
            <textarea value={portfolioParams.positions}
              onChange={(e) => setPortfolioParams(p => ({ ...p, positions: e.target.value }))}
              rows={5}
              className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 font-mono mt-1" />
          </div>
          <button onClick={() => portfolioMutation.mutate(portfolioParams)}
            disabled={portfolioMutation.isPending}
            className="w-full bg-primary-600/40 hover:bg-primary-600/60 text-primary-300 font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            \u062a\u062d\u0644\u06cc\u0644 \u067e\u0648\u0631\u062a\u0641\u0648\u06cc
          </button>
          {portfolioMutation.data?.data && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                {[
                  { l: "\u0394 Delta", v: portfolioMutation.data.data.portfolio_delta },
                  { l: "\u0393 Gamma", v: portfolioMutation.data.data.portfolio_gamma },
                  { l: "\u0398 Theta", v: portfolioMutation.data.data.portfolio_theta },
                  { l: "\u039d Vega", v: portfolioMutation.data.data.portfolio_vega },
                  { l: "\u03a1 Rho", v: portfolioMutation.data.data.portfolio_rho },
                ].map((g) => (
                  <div key={g.l} className="bg-surface-800/40 rounded-xl p-2.5 text-center">
                    <p className="text-[10px] text-surface-500">{g.l}</p>
                    <p className="text-sm font-bold text-surface-200 font-mono" dir="ltr">{typeof g.v === "number" ? g.v.toFixed(4) : g.v}</p>
                  </div>
                ))}
              </div>
              <div className="bg-surface-800/30 rounded-xl p-3">
                <p className="text-[10px] text-surface-500 mb-1">{portfolioMutation.data.data.delta_explanation}</p>
                <p className="text-xs text-accent-emerald">{portfolioMutation.data.data.hedging_suggestion}</p>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
