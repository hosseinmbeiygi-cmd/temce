"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card } from "@/components/ui/Card";
import { apiPost } from "@/lib/api";
import type { CostResult, SizingResult, IvRankResult, ChecklistItem } from "./types";
import { fmt } from "./helpers";

type ToolTab = "costs" | "sizing" | "ivrank" | "checklist";

const PRIORITY_BADGE: Record<string, string> = {
  high: "bg-accent-rose/10 text-accent-rose border-accent-rose/20",
  medium: "bg-accent-amber/10 text-accent-amber border-accent-amber/20",
  low: "bg-surface-700/40 text-surface-400 border-surface-600/30",
};

export default function ProfessionalTools() {
  const [tab, setTab] = useState<ToolTab>("costs");

  // costs: backend expects entry_price, exit_price, quantity, is_option, is_short
  const [costEntry, setCostEntry] = useState(500);
  const [costExit, setCostExit] = useState(800);
  const [costQty, setCostQty] = useState(1000);
  const [isShort, setIsShort] = useState(false);

  const [sizingParams, setSizingParams] = useState({ capital: 100_000_000, risk_per_trade_pct: 2, max_loss_per_contract: 100_000 });

  // iv-rank backend: current_iv, iv_52w_high, iv_52w_low (fraction, e.g. 0.35)
  const [ivParams, setIvParams] = useState({ current_iv: 0.35, iv_52w_high: 0.6, iv_52w_low: 0.2 });

  // checklist backend: strategy, stock_price, strike
  const [checkParams, setCheckParams] = useState({ strategy: "covered_call", stock_price: 1000, strike: 1000 });

  const costsMutation = useMutation({
    mutationFn: () =>
      apiPost<{ success: boolean; data: CostResult }>("/options/professional/costs", {
        entry_price: costEntry,
        exit_price: costExit,
        quantity: costQty,
        is_option: true,
        is_short: isShort,
      }),
    onError: (err: Error) => toast.error(err.message),
  });

  const sizingMutation = useMutation({
    mutationFn: () =>
      apiPost<{ success: boolean; data: SizingResult }>("/options/professional/position-sizing", {
        capital: sizingParams.capital,
        risk_per_trade_pct: sizingParams.risk_per_trade_pct,
        max_loss_per_contract: sizingParams.max_loss_per_contract,
      }),
    onError: (err: Error) => toast.error(err.message),
  });

  const ivRankMutation = useMutation({
    mutationFn: () =>
      apiPost<{ success: boolean; data: IvRankResult }>("/options/professional/iv-rank", {
        current_iv: ivParams.current_iv,
        iv_52w_high: ivParams.iv_52w_high,
        iv_52w_low: ivParams.iv_52w_low,
      }),
    onError: (err: Error) => toast.error(err.message),
  });

  const checklistMutation = useMutation({
    mutationFn: () =>
      apiPost<{ success: boolean; data: ChecklistItem[] }>("/options/professional/checklist", {
        strategy: checkParams.strategy,
        stock_price: checkParams.stock_price,
        strike: checkParams.strike,
      }),
    onError: (err: Error) => toast.error(err.message),
  });

  const tabs = [
    { id: "costs" as ToolTab, label: "محاسبه کارمزد" },
    { id: "sizing" as ToolTab, label: "اندازه معامله" },
    { id: "ivrank" as ToolTab, label: "IV Rank" },
    { id: "checklist" as ToolTab, label: "چک‌لیست" },
  ];

  const iv = ivRankMutation.data?.data;

  return (
    <div className="space-y-4">
      <div className="flex gap-1 bg-surface-800/50 rounded-xl p-1 border border-surface-700/50 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${tab === t.id ? "bg-primary-600/30 text-primary-300 shadow-sm" : "text-surface-400 hover:text-surface-200"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "costs" && (
        <Card title="محاسبه هزینه‌ها و کارمزدها (بازار ایران)">
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div>
              <label className="text-[10px] text-surface-500">قیمت ورود</label>
              <input type="number" value={costEntry} onChange={(e) => setCostEntry(Number(e.target.value))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
            <div>
              <label className="text-[10px] text-surface-500">قیمت خروج</label>
              <input type="number" value={costExit} onChange={(e) => setCostExit(Number(e.target.value))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
            <div>
              <label className="text-[10px] text-surface-500">تعداد</label>
              <input type="number" value={costQty} onChange={(e) => setCostQty(Number(e.target.value))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
          </div>
          <div className="flex gap-2 mb-3">
            <button onClick={() => setIsShort(false)} className={`px-3 py-1.5 rounded-lg text-xs font-bold border ${!isShort ? "bg-accent-emerald/20 text-accent-emerald border-accent-emerald/30" : "bg-surface-800 text-surface-400 border-surface-700/30"}`}>خرید (Long)</button>
            <button onClick={() => setIsShort(true)} className={`px-3 py-1.5 rounded-lg text-xs font-bold border ${isShort ? "bg-accent-rose/20 text-accent-rose border-accent-rose/30" : "bg-surface-800 text-surface-400 border-surface-700/30"}`}>فروش (Short)</button>
          </div>
          <button onClick={() => costsMutation.mutate()} disabled={costsMutation.isPending} className="w-full bg-primary-600 hover:bg-primary-500 text-white font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            {costsMutation.isPending ? "در حال محاسبه..." : "محاسبه"}
          </button>
          {costsMutation.data?.data && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              {[
                { l: "سود ناخالص", v: fmt(costsMutation.data.data.gross_pnl) },
                { l: "کارمزد", v: fmt(costsMutation.data.data.commission) },
                { l: "سود خالص", v: fmt(costsMutation.data.data.net_pnl) },
                { l: "درصد سود", v: costsMutation.data.data.net_pnl_pct.toFixed(2) + "٪" },
              ].map((r) => (
                <div key={r.l} className="bg-surface-800/40 rounded-xl p-2.5 text-center">
                  <p className="text-[10px] text-surface-500">{r.l}</p>
                  <p className="text-sm font-bold text-surface-200">{r.v}</p>
                </div>
              ))}
              <div className="bg-surface-800/40 rounded-xl p-2.5 text-center col-span-2 md:col-span-4">
                <p className="text-[10px] text-surface-500">نقطه سربه‌سری</p>
                <p className="text-sm font-bold text-accent-amber">{fmt(costsMutation.data.data.breakeven)}</p>
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "sizing" && (
        <Card title="محاسبه اندازه معامله">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            {[
              { k: "capital", l: "سرمایه (تومان)", v: sizingParams.capital },
              { k: "risk_per_trade_pct", l: "ریسک % هر معامله", v: sizingParams.risk_per_trade_pct },
              { k: "max_loss_per_contract", l: "حداکثر زیان هر قرارداد", v: sizingParams.max_loss_per_contract },
            ].map((f) => (
              <div key={f.k}>
                <label className="text-[10px] text-surface-500">{f.l}</label>
                <input type="number" value={f.v} onChange={(e) => setSizingParams((p) => ({ ...p, [f.k]: Number(e.target.value) }))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
              </div>
            ))}
          </div>
          <button onClick={() => sizingMutation.mutate()} disabled={sizingMutation.isPending} className="w-full bg-primary-600 hover:bg-primary-500 text-white font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            {sizingMutation.isPending ? "در حال محاسبه..." : "محاسبه اندازه"}
          </button>
          {sizingMutation.data?.data && (
            <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
              <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                <p className="text-[10px] text-surface-500">حداکثر قرارداد</p>
                <p className="text-lg font-bold text-surface-200">{sizingMutation.data.data.max_contracts}</p>
              </div>
              <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                <p className="text-[10px] text-surface-500">هزینه کل</p>
                <p className="text-lg font-bold text-surface-200">{fmt(sizingMutation.data.data.total_cost)}</p>
              </div>
              <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                <p className="text-[10px] text-surface-500">درصد سرمایه</p>
                <p className="text-lg font-bold text-surface-200">{sizingMutation.data.data.pct_of_capital}٪</p>
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "ivrank" && (
        <Card title="IV Rank و پرسنایل">
          <p className="text-[10px] text-surface-500 mb-3">IV Rank = (IV فعلی − کف ۵۲هفته) ÷ (سقف ۵۲هفته − کف ۵۲هفته) × ۱۰۰ — مقادیر را به‌صورت اعشاری وارد کنید (۰.۳۵ = ۳۵٪)</p>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div>
              <label className="text-[10px] text-surface-500">IV فعلی</label>
              <input type="number" step="any" value={ivParams.current_iv} onChange={(e) => setIvParams((p) => ({ ...p, current_iv: Number(e.target.value) }))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
            <div>
              <label className="text-[10px] text-surface-500">سقف ۵۲هفته</label>
              <input type="number" step="any" value={ivParams.iv_52w_high} onChange={(e) => setIvParams((p) => ({ ...p, iv_52w_high: Number(e.target.value) }))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
            <div>
              <label className="text-[10px] text-surface-500">کف ۵۲هفته</label>
              <input type="number" step="any" value={ivParams.iv_52w_low} onChange={(e) => setIvParams((p) => ({ ...p, iv_52w_low: Number(e.target.value) }))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
          </div>
          <button onClick={() => ivRankMutation.mutate()} disabled={ivRankMutation.isPending} className="w-full bg-primary-600 hover:bg-primary-500 text-white font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50">
            {ivRankMutation.isPending ? "در حال محاسبه..." : "محاسبه IV Rank"}
          </button>
          {iv && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500">IV Rank</p>
                  <p className="text-lg font-bold text-surface-200" dir="ltr">{iv.iv_rank.toFixed(1)}</p>
                </div>
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500">IV فعلی</p>
                  <p className="text-lg font-bold text-surface-200" dir="ltr">{iv.current_iv}%</p>
                </div>
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500">سقف / کف</p>
                  <p className="text-sm font-bold text-surface-200" dir="ltr">{iv.iv_52w_high}% / {iv.iv_52w_low}%</p>
                </div>
                <div className="bg-surface-800/40 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-surface-500">وضعیت</p>
                  <p className={`text-sm font-bold ${iv.iv_rank > 60 ? "text-accent-rose" : iv.iv_rank < 40 ? "text-accent-emerald" : "text-accent-amber"}`}>
                    {iv.iv_rank > 60 ? "فروش نوسان" : iv.iv_rank < 40 ? "خرید نوسان" : "متوسط"}
                  </p>
                </div>
              </div>
              <div className="bg-surface-800/30 rounded-xl p-3">
                <p className="text-xs text-surface-300">{iv.interpretation_fa}</p>
              </div>
              <div className="bg-primary-600/10 border border-primary-600/20 rounded-xl p-3">
                <p className="text-[10px] text-primary-400 mb-1">استراتژی‌های پیشنهادی</p>
                <p className="text-xs text-primary-300 font-mono" dir="ltr">{iv.suggestion}</p>
              </div>
            </div>
          )}
        </Card>
      )}

      {tab === "checklist" && (
        <Card title="چک‌لیست پیش از معامله">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <div>
              <label className="text-[10px] text-surface-500">استراتژی</label>
              <select value={checkParams.strategy} onChange={(e) => setCheckParams((p) => ({ ...p, strategy: e.target.value }))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1">
                <option value="covered_call">Covered Call</option>
                <option value="married_put">Married Put</option>
                <option value="long_straddle">Long Straddle</option>
                <option value="long_strangle">Long Strangle</option>
                <option value="bull_call_spread">Bull Call Spread</option>
                <option value="bear_put_spread">Bear Put Spread</option>
                <option value="iron_condor">Iron Condor</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-surface-500">قیمت سهم</label>
              <input type="number" value={checkParams.stock_price} onChange={(e) => setCheckParams((p) => ({ ...p, stock_price: Number(e.target.value) }))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
            <div>
              <label className="text-[10px] text-surface-500">قیمت اعمال</label>
              <input type="number" value={checkParams.strike} onChange={(e) => setCheckParams((p) => ({ ...p, strike: Number(e.target.value) }))} className="w-full bg-surface-800/60 border border-surface-700/50 rounded-lg px-3 py-2 text-xs text-surface-200 mt-1" />
            </div>
          </div>
          <button onClick={() => checklistMutation.mutate()} disabled={checklistMutation.isPending} className="w-full bg-primary-600 hover:bg-primary-500 text-white font-bold py-2.5 rounded-xl text-xs transition-all disabled:opacity-50 mb-4">
            {checklistMutation.isPending ? "در حال دریافت..." : "دریافت چک‌لیست"}
          </button>
          {checklistMutation.data?.data && Array.isArray(checklistMutation.data.data) && (
            <div className="space-y-2">
              {checklistMutation.data.data.map((item, i) => (
                <div key={i} className="flex items-start gap-3 bg-surface-800/40 rounded-xl p-3 border border-surface-700/30">
                  <span className="text-accent-emerald mt-0.5">✓</span>
                  <div className="flex-1">
                    <p className="text-xs font-bold text-surface-200">{item.item}</p>
                  </div>
                  <span className={`text-[9px] px-2 py-0.5 rounded-full border ${PRIORITY_BADGE[item.priority] ?? PRIORITY_BADGE.low}`}>
                    {item.priority === "high" ? "حیاتی" : item.priority === "medium" ? "مهم" : "معمولی"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Card title="قوانین بازار ایران" className="md:col-span-2">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          {[
            { l: "کارمزد خرید", v: "۰.۱۲۵٪" },
            { l: "کارمزد فروش", v: "۰.۶۲۵٪ (شامل مالیات)" },
            { l: "تسویه", v: "T+2" },
            { l: "اندازه قرارداد", v: "۱,۰۰۰ سهم" },
            { l: "محدودیت قیمت", v: "±۱۹٪ (اختیار)" },
            { l: "سبک اعمال", v: "اروپایی" },
            { l: "فروش فزاینده", v: "ممنوع" },
            { l: "حداقل سرمایه", v: "۵۰ میلیون تومان" },
          ].map((r) => (
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
