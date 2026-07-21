"use client";

import { useState, useCallback } from "react";
import AppLayout from "@/components/layout/AppLayout";
import Link from "next/link";

// ── Constants ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

const METHODS = [
  { id: "vectorized", name: "بک‌تست برداری", icon: "⚡", layer: 1, desc: "محاسبه ماتریسی سریع سیگنال‌ها و بازده‌ها", speed: "فوق‌العاده سریع", accuracy: "متوسط", tse_fit: "غربالگری اولیه", code: "returns = close.pct_change()\nsignal = model_prediction.shift(1)\nstrategy_return = signal * returns\nequity_curve = (1 + strategy_return).cumprod()" },
  { id: "event_driven", name: "بک‌تست رخدادمحور", icon: "🔄", layer: 2, desc: "موتور شبیه‌سازی معاملات واقعی با رویدادها", speed: "متوسط", accuracy: "بالا", tse_fit: "هسته اصلی بک‌تست", code: "Market Event → Signal → Risk Check → Order\n→ Fill Simulation → Portfolio Update" },
  { id: "order_level", name: "بک‌تست سطح سفارش", icon: "📋", layer: 3, desc: "شبیه‌سازی دقیق صف خرید/فروش و اجرای جزئی", speed: "کند", accuracy: "بسیار بالا", tse_fit: "حیاتی برای TSE", code: " صف خرید/فروش | حجم مبنا | دامنه نوسان\nاولویت زمانی | Partial Fill | توقف نماد" },
  { id: "execution", name: "اجرای آگاه سفارش", icon: "🎯", layer: 4, desc: "ارزیابی قابلیت اجرای سیگنال در بازار واقعی", speed: "متوسط", accuracy: "بالا", tse_fit: "کنترل اسلیپیج", code: "VWAP = Σ(Pt × Vt) / Σ(Vt)\nExecutableVolume = α × MarketVolume\nDaysToLiquidate = PositionValue / (Participation × AvgDailyValue)" },
  { id: "walk_forward", name: "Walk-Forward", icon: "🔍", layer: 5, desc: "اعتبارسنجی متحرک برای جلوگیری از بیش‌برازش", speed: "متوسط", accuracy: "بالا", tse_fit: "جلوگیری overfitting", code: "Train: 1397-1399 → Test: 1400\nTrain: 1398-1400 → Test: 1401\nRolling Window | Expanding Window" },
  { id: "cpcv", name: "CPCV", icon: "🔬", layer: 5, desc: "اعتبارسنجی متقاطع با حذف و قرنطینه", speed: "کند", accuracy: "بسیار بالا", tse_fit: "مدل‌های ML", code: "Purging: حذف نمونه‌های هم‌پوشان\nEmbargo: فاصله زمانی بعد از تست\nEmbargoLength = γ × T" },
  { id: "monte_carlo", name: "مونت‌کارلو", icon: "🎲", layer: 6, desc: "هزاران مسیر احتمالی برای سنجش تاب‌آوری", speed: "کند", accuracy: "بالا", tse_fit: "سناریوهای مختلف", code: "Scenario 1: هزینه 2x\nScenario 2: اسلیپیج 3x\nScenario 3: 20% تأخیر اجرا\n→ توزیع Sharpe, 5% Worst-Case" },
  { id: "stress", name: "تست استرس", icon: "💥", layer: 6, desc: "شبیه‌سازی شرایط بحرانی بازار تهران", speed: "سریع", accuracy: "بالا", tse_fit: "بحران صف فروش", code: "سقوط 30% شاخص | صف فروش 5 روزه\nشوک نرخ ارز 20% | توقف 30% نمادها\nکاهش 70% نقدشوندگی" },
  { id: "regime", name: "تحلیل رژیمی", icon: "📊", layer: 7, desc: "ارزیابی جداگانه عملکرد در هر رژیم بازار", speed: "سریع", accuracy: "بالا", tse_fit: "عملکرد در نزولی", code: "رژیم صعودی: Return, Sharpe, DD\nرژیم نزولی: آیا زنده می‌ماند؟\nرژیم رنج: نرخ برد\nرژیم صف‌محور: نرخ شکست" },
  { id: "liquidity", name: "تعدیل نقدشوندگی", icon: "💧", layer: 8, desc: "کنترل هزینه واقعی معامله در سهام کم‌عمق", speed: "سریع", accuracy: "متوسط", tse_fit: "سهام کم‌حجم", code: "DaysToLiquidate = PV / (α × ADV)\nAmihud Illiquidity = |Return| / Value\nQueue Lock Ratio" },
  { id: "capacity", name: "تست ظرفیت", icon: "📐", layer: 9, desc: "بررسی حداکثر سرمایه قابل اجرای استراتژی", speed: "کند", accuracy: "بالا", tse_fit: "مقیاس سرمایه", code: "1B → 5B → 10B → 50B → 100B → 500B\nبررسی: Return, Fill Rate, Slippage\nLiquidity Failure, Rebalance Time" },
  { id: "deflated_sharpe", name: "شارپ تعدیل‌شده", icon: "📉", layer: 10, desc: "اعتبار آماری نتایج پس از تست‌های زیاد", speed: "سریع", accuracy: "بسیار بالا", tse_fit: "جلوگیری data snooping", code: "DSR = (SR_observed - E[max_SR]) / SE\nE[max_SR] = √(2ln(N)) × (1 - γ/2ln(N))\nProb(Real SR > 0) > 95%?" },
];

const LAYERS = [
  { level: 1, name: "Research", methods: ["vectorized"] },
  { level: 2, name: "Walk-Forward", methods: ["walk_forward", "cpcv"] },
  { level: 3, name: "Event-Driven", methods: ["event_driven", "order_level", "execution"] },
  { level: 4, name: "Liquidity", methods: ["liquidity", "capacity"] },
  { level: 5, name: "Regime", methods: ["regime"] },
  { level: 6, name: "Robustness", methods: ["monte_carlo", "stress"] },
  { level: 7, name: "Statistical", methods: ["deflated_sharpe"] },
];

// ── Main Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export default function BacktestMethodsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<"all" | "layers" | "tse">("all");

  const selectedMethod = METHODS.find(m => m.id === selected);

  return (
    <AppLayout title="چارچوب بک‌تست جامع" subtitle="۲۰ روش بک‌تست حرفه‌ای ویژه بورس تهران">
      <div className="max-w-7xl mx-auto space-y-3">

        {/* Tabs */}
        <div className="flex gap-1 bg-surface-800/50 rounded-lg p-1">
          {[
            { id: "all" as const, icon: "📋", label: "همه روش‌ها" },
            { id: "layers" as const, icon: "🏗️", label: "لایه‌بندی" },
            { id: "tse" as const, icon: "🇮🇷", label: "اولویت TSE" },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded text-[10px] font-bold transition-colors ${tab === t.id ? "bg-primary-600 text-white" : "text-surface-400 hover:text-surface-200"}`}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {/* Left: Method List */}
          <div className="lg:col-span-1 space-y-3">
            {tab === "all" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">📋 روش‌های بک‌تست ({METHODS.length})</h3>
                <div className="space-y-1 max-h-[600px] overflow-y-auto">
                  {METHODS.map(m => (
                    <button key={m.id} onClick={() => setSelected(m.id)}
                      className={`w-full text-right p-2 rounded border text-[10px] transition-all ${selected === m.id ? "border-primary-500 bg-primary-600/10" : "border-surface-700/50 hover:border-surface-500"}`}>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span>{m.icon}</span>
                          <span className="font-bold text-surface-200">{m.name}</span>
                        </div>
                        <span className="text-[8px] text-surface-600">L{m.layer}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {tab === "layers" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">🏗️ لایه‌بندی پیشنهادی</h3>
                <div className="space-y-2">
                  {LAYERS.map(layer => (
                    <div key={layer.level} className="p-2 bg-surface-800/30 rounded border-l-2 border-primary-500">
                      <div className="text-[9px] font-bold text-primary-300 mb-1">لایه {layer.level}: {layer.name}</div>
                      <div className="flex flex-wrap gap-0.5">
                        {layer.methods.map(mid => {
                          const m = METHODS.find(x => x.id === mid);
                          return m ? (
                            <button key={mid} onClick={() => setSelected(mid)}
                              className={`text-[8px] px-1.5 py-0.5 rounded transition-colors ${selected === mid ? "bg-primary-600 text-white" : "bg-surface-700 text-surface-400 hover:text-surface-200"}`}>
                              {m.icon} {m.name}
                            </button>
                          ) : null;
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "tse" && (
              <div className="glass-card p-3">
                <h3 className="font-bold text-surface-200 text-[11px] mb-2">🇮🇷 اولویت‌بندی ویژه TSE</h3>
                <div className="space-y-1">
                  {METHODS.sort((a, b) => {
                    const priority: Record<string, number> = {
                      "order_level": 1, "event_driven": 2, "walk_forward": 3,
                      "regime": 4, "stress": 5, "liquidity": 6, "deflated_sharpe": 7,
                      "vectorized": 8, "monte_carlo": 9, "execution": 10,
                      "cpcv": 11, "capacity": 12,
                    };
                    return (priority[a.id] || 99) - (priority[b.id] || 99);
                  }).map((m, i) => (
                    <button key={m.id} onClick={() => setSelected(m.id)}
                      className={`w-full text-right p-1.5 rounded text-[9px] transition-colors ${selected === m.id ? "bg-primary-600/10 border border-primary-500" : "hover:bg-surface-800"}`}>
                      <span className="text-surface-500">{i + 1}.</span>
                      <span className="mr-1">{m.icon}</span>
                      <span className="font-bold text-surface-200">{m.name}</span>
                      <span className="mr-1 text-surface-500">— {m.tse_fit}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Key Principle */}
            <div className="glass-card p-3">
              <h3 className="font-bold text-accent-amber text-[10px] mb-1">💡 نکته کلیدی</h3>
              <p className="text-[9px] text-surface-400 leading-relaxed">
                بک‌تست خوب فقط این نیست که بگوییم «اگر می‌خریدیم و می‌فروختیم، چقدر سود می‌کردیم؟»
                بلکه باید پاسخ دهد: آیا واقعاً می‌توانستیم بخریم/بفروشیم؟ با چه حجمی؟ با چه هزینه‌ای؟
                در صف چه اتفاقی می‌افتاد؟
              </p>
            </div>
          </div>

          {/* Right: Method Details */}
          <div className="lg:col-span-2 space-y-3">
            {selectedMethod ? (
              <>
                <div className="glass-card p-4">
                  <div className="flex items-start gap-3 mb-3">
                    <span className="text-3xl">{selectedMethod.icon}</span>
                    <div>
                      <h2 className="text-sm font-bold text-surface-100">{selectedMethod.name}</h2>
                      <p className="text-[10px] text-surface-500 mt-0.5">{selectedMethod.desc}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {[
                      { l: "سرعت", v: selectedMethod.speed, c: selectedMethod.speed.includes("سریع") ? "text-accent-emerald" : selectedMethod.speed.includes("کند") ? "text-accent-rose" : "text-accent-amber" },
                      { l: "دقت", v: selectedMethod.accuracy, c: selectedMethod.accuracy.includes("بسیار") ? "text-accent-emerald" : "text-surface-200" },
                      { l: "کاربرد TSE", v: selectedMethod.tse_fit, c: "text-primary-300" },
                    ].map((x, i) => (
                      <div key={i} className="p-2 bg-surface-800/30 rounded text-center">
                        <div className={`text-[10px] font-bold ${x.c}`}>{x.v}</div>
                        <div className="text-[7px] text-surface-500">{x.l}</div>
                      </div>
                    ))}
                  </div>
                  <div className="p-3 bg-surface-800/50 rounded-lg border border-surface-700/50">
                    <div className="text-[9px] text-surface-500 mb-1">فرمولاسیون / پیاده‌سازی:</div>
                    <pre className="text-[9px] text-accent-emerald font-mono whitespace-pre-wrap leading-relaxed">{selectedMethod.code}</pre>
                  </div>
                  <div className="mt-3 p-2 bg-surface-800/30 rounded">
                    <div className="text-[9px] text-surface-500 mb-1">لایه: {LAYERS.find(l => l.methods.includes(selectedMethod.id))?.name || "?"} (سطح {selectedMethod.layer})</div>
                  </div>
                </div>
              </>
            ) : (
              <div className="glass-card p-10 text-center text-surface-500">
                <p className="text-5xl mb-4">📚</p>
                <p className="text-sm font-bold text-surface-300 mb-2">چارچوب بک‌تست جامع بورس تهران</p>
                <p className="text-[10px] max-w-lg mx-auto leading-relaxed">
                  ۲۰ روش بک‌تست حرفه‌ای از Vectorized تا Deflated Sharpe Ratio.
                  یک روش را از لیست انتخاب کنید تا جزئیات، فرمول‌ها و کد پیاده‌سازی آن نمایش داده شود.
                </p>
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2 max-w-md mx-auto">
                  {[
                    { v: "20", l: "روش بک‌تست" },
                    { v: "7", l: "لایه" },
                    { v: "8", l: "حداقل پیشنهادی" },
                    { v: "TSE", l: "ویژه بورس تهران" },
                  ].map((s, i) => (
                    <div key={i} className="p-2 bg-surface-800/30 rounded">
                      <div className="text-base font-bold text-primary-300">{s.v}</div>
                      <div className="text-[8px] text-surface-500">{s.l}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 text-[9px]">
          <Link href="/backtest" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">← بک‌تست</Link>
          <Link href="/backtest/engine" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">موتور</Link>
          <Link href="/backtest/adaptive" className="text-surface-500 hover:text-surface-200 px-1.5 py-0.5">انطباقی</Link>
        </div>
      </div>
    </AppLayout>
  );
}
