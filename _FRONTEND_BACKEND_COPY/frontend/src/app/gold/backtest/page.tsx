"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStrategyBacktest, getBacktest } from "@/lib/goldApi";

export default function GoldBacktestPage() {
  const [days, setDays] = useState(90);
  const [bubbleTrigger, setBubbleTrigger] = useState(5);
  const [capital, setCapital] = useState(100_000_000);

  const { data: strategy, isLoading } = useQuery({
    queryKey: ["gold", "backtest-strategy", days, bubbleTrigger, capital],
    queryFn: () => getStrategyBacktest({ days, bubble_trigger: bubbleTrigger, initial_capital: capital }),
  });

  const { data: signal } = useQuery({
    queryKey: ["gold", "backtest-signal", days],
    queryFn: () => getBacktest(days, 8),
  });

  return (
    <div className="space-y-6" dir="rtl">
      <div className="text-sm text-zinc-400">
        بک‌تست استراتژی DCA روی داده‌های تاریخی. مقایسه با buy-and-hold.
      </div>

      <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-zinc-300">پارامترها</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <label className="text-xs text-zinc-400">
            بازه (روز)
            <input
              type="number"
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value) || 30)}
              className="w-full mt-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
            />
          </label>
          <label className="text-xs text-zinc-400">
            Bubble Trigger (٪)
            <input
              type="number"
              step="0.5"
              value={bubbleTrigger}
              onChange={(e) => setBubbleTrigger(parseFloat(e.target.value) || 0)}
              className="w-full mt-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
            />
          </label>
          <label className="text-xs text-zinc-400">
            سرمایه اولیه
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(parseInt(e.target.value) || 1_000_000)}
              className="w-full mt-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100"
            />
          </label>
        </div>
      </div>

      {isLoading ? (
        <div className="text-zinc-500 text-center py-12">در حال محاسبه...</div>
      ) : strategy ? (
        <>
          {strategy.warning && (
            <div className="rounded border border-amber-700 bg-amber-950/30 p-3 text-xs text-amber-300">
              ⚠️ {strategy.warning}
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">بازده DCA</div>
              <div
                className={`text-xl font-bold font-mono mt-1 ${
                  strategy.total_return_pct > 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {strategy.total_return_pct > 0 ? "+" : ""}
                {strategy.total_return_pct}٪
              </div>
            </div>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">Buy & Hold</div>
              <div className="text-xl font-bold font-mono text-zinc-200 mt-1">
                {strategy.buy_hold_return_pct > 0 ? "+" : ""}
                {strategy.buy_hold_return_pct}٪
              </div>
            </div>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">آلفا (DCA − BH)</div>
              <div
                className={`text-xl font-bold font-mono mt-1 ${
                  strategy.alpha_pct > 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {strategy.alpha_pct > 0 ? "+" : ""}
                {strategy.alpha_pct}٪
              </div>
            </div>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">Hit Rate</div>
              <div className="text-xl font-bold font-mono text-zinc-200 mt-1">
                {strategy.hit_rate_pct}٪
              </div>
            </div>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">Max Drawdown</div>
              <div className="text-xl font-bold font-mono text-rose-400 mt-1">
                -{strategy.max_drawdown_pct}٪
              </div>
            </div>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">Sharpe Ratio</div>
              <div className="text-xl font-bold font-mono text-zinc-200 mt-1">
                {strategy.sharpe_ratio}
              </div>
            </div>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">معاملات</div>
              <div className="text-xl font-bold font-mono text-zinc-200 mt-1">
                {strategy.n_successful}/{strategy.n_trades}
              </div>
            </div>
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
              <div className="text-xs text-zinc-400">ارزش نهایی</div>
              <div className="text-xl font-bold font-mono text-zinc-200 mt-1">
                {Math.round(strategy.final_value).toLocaleString("fa-IR")}
              </div>
            </div>
          </div>

          {strategy.trades.length > 0 && (
            <div className="rounded-lg border border-zinc-700 bg-zinc-900 overflow-hidden">
              <div className="px-4 py-3 border-b border-zinc-700 text-sm font-semibold text-zinc-300">
                معاملات انجام‌شده
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-zinc-500 border-b border-zinc-800">
                    <th className="text-right p-3">پله</th>
                    <th className="text-right p-3">تاریخ</th>
                    <th className="text-left p-3">قیمت</th>
                    <th className="text-left p-3">مبلغ</th>
                    <th className="text-left p-3">واحد</th>
                  </tr>
                </thead>
                <tbody>
                  {strategy.trades.map((t, i) => (
                    <tr key={i} className="border-b border-zinc-800/50">
                      <td className="p-3 text-zinc-200">{t.tranche}</td>
                      <td className="p-3 text-zinc-400">{t.date}</td>
                      <td className="p-3 text-left text-zinc-100 font-mono">
                        {Math.round(t.price).toLocaleString("fa-IR")}
                      </td>
                      <td className="p-3 text-left text-zinc-100 font-mono">
                        {Math.round(t.amount_irt).toLocaleString("fa-IR")}
                      </td>
                      <td className="p-3 text-left text-zinc-100 font-mono">{t.units.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}

      {signal && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-4">
          <h3 className="text-sm font-semibold text-zinc-300 mb-2">سیگنال ساده (Bubble Threshold)</h3>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">روز سیگنال</div>
              <div className="text-zinc-100 font-mono mt-1">{signal.signal_days}</div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">بازده ۳۰ روز بعد</div>
              <div className="text-zinc-100 font-mono mt-1">{signal.forward_30d_avg_pct}٪</div>
            </div>
            <div className="bg-zinc-800 p-2 rounded">
              <div className="text-zinc-400">Hit Rate</div>
              <div className="text-zinc-100 font-mono mt-1">{signal.hit_rate_pct}٪</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
