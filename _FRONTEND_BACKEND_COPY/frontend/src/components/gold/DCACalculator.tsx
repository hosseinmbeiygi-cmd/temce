"use client";
import React, { useState } from "react";
import { planDCA } from "@/lib/goldApi";
import type { DCAPlan, RiskProfile, Vehicle } from "@/types/gold";

export function DCACalculator({ className = "" }: { className?: string }) {
  const [capital, setCapital] = useState(100_000_000);
  const [risk, setRisk] = useState<RiskProfile>("balanced");
  const [score, setScore] = useState(65);
  const [vehicle, setVehicle] = useState<Vehicle | "">("");
  const [plan, setPlan] = useState<DCAPlan | null>(null);
  const [loading, setLoading] = useState(false);

  const onCalculate = async () => {
    setLoading(true);
    try {
      const r = await planDCA({
        total_capital_irt: capital,
        risk_profile: risk,
        current_score: score,
        preferred_vehicle: (vehicle || undefined) as Vehicle | undefined,
      });
      setPlan(r);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="p-4 border border-zinc-700 rounded-lg bg-zinc-900 space-y-3">
        <div className="text-sm font-semibold text-zinc-300">ماشین‌حساب DCA</div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">سرمایه (تومان)</label>
          <input
            type="number"
            value={capital}
            onChange={(e) => setCapital(parseInt(e.target.value) || 0)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
          />
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">ریسک</label>
          <select
            value={risk}
            onChange={(e) => setRisk(e.target.value as RiskProfile)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
          >
            <option value="conservative">محافظه‌کارانه (20/40/40)</option>
            <option value="balanced">متعادل (30/40/30)</option>
            <option value="aggressive">تهاجمی (50/30/20)</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">امتیاز فعلی</label>
          <input
            type="number"
            min={0}
            max={100}
            value={score}
            onChange={(e) => setScore(parseInt(e.target.value) || 0)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
          />
        </div>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">ابزار (اختیاری)</label>
          <select
            value={vehicle}
            onChange={(e) => setVehicle(e.target.value as Vehicle | "")}
            className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
          >
            <option value="">— خودکار —</option>
            <option value="etf">صندوق ETF</option>
            <option value="cert">گواهی شمش</option>
            <option value="melted">طلای آب‌شده</option>
            <option value="coin">سکه فیزیکی</option>
            <option value="jewelry">طلای زینتی</option>
          </select>
        </div>
        <button
          onClick={onCalculate}
          disabled={loading || capital <= 0}
          className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded px-3 py-2 text-sm font-semibold"
        >
          {loading ? "در حال محاسبه..." : "محاسبه پلن"}
        </button>
      </div>

      {plan && (
        <div className="p-4 border border-zinc-700 rounded-lg bg-zinc-900 space-y-3">
          <div className="text-sm font-semibold text-zinc-300">نتیجه</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">ابزار پیشنهادی</div>
              <div className="text-zinc-100 font-semibold mt-1">{plan.recommended_vehicle}</div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">کارمزد کل</div>
              <div className="text-zinc-100 font-mono mt-1">{plan.total_fee_irt.toLocaleString("fa-IR")}</div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">خالص سرمایه‌گذاری</div>
              <div className="text-zinc-100 font-mono mt-1">{plan.net_investable_irt.toLocaleString("fa-IR")}</div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">Stop / Take</div>
              <div className="text-zinc-100 font-mono mt-1">
                -{plan.stop_loss_pct}٪ / +{plan.take_profit_pct}٪
              </div>
            </div>
          </div>
          <div className="space-y-2 mt-3">
            {plan.ladder.map((t) => (
              <div key={t.tranche} className="bg-zinc-800/50 p-3 rounded border border-zinc-800">
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-300 font-semibold">پله {t.tranche}</span>
                  <span className="text-zinc-100 font-mono">{(t.pct * 100).toFixed(0)}٪</span>
                </div>
                <div className="text-xs text-zinc-400 mt-1">مبلغ: {t.amount_irt.toLocaleString("fa-IR")} تومان</div>
                <div className="text-xs text-zinc-500 mt-1">📌 {t.trigger}</div>
                <div className="text-[10px] text-zinc-500 mt-1">کارمزد: {t.estimated_fee_irt.toLocaleString("fa-IR")}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
