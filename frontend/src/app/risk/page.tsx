"use client";

import { useState, useEffect } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";

interface RiskMetric {
  label: string;
  value: string;
  status: "safe" | "warning" | "danger";
  description: string;
}

const RISK_METRICS: RiskMetric[] = [
  { label: "VaR (۹۵%)", value: "-۲.۴%", status: "safe", description: "Value at Risk در سطح اطمینان ۹۵%" },
  { label: "CVaR", value: "-۴.۱%", status: "warning", description: "میانگین زیان در موارد فراتر از VaR" },
  { label: "Sharpe Ratio", value: "۱.۸۷", status: "safe", description: "نسبت بازده به ریسک" },
  { label: "Beta", value: "۱.۱۲", status: "warning", description: "حساسیت به بازار" },
  { label: "Max Drawdown", value: "-۱۵.۳%", status: "danger", description: "بیشترین کاهش از اوج" },
  { label: "Volatility", value: "۲۴.۶%", status: "warning", description: "انحراف معیار بازده‌ها" },
  { label: "Exposure", value: "۸۵%", status: "safe", description: "درصد سرمایه در معرض ریسک" },
  { label: "Concentration", value: "۳۲%", status: "danger", description: "درصد تمرکز در بزرگترین موقعیت" },
];

export default function RiskPage() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  return (
    <AppLayout title="مدیریت ریسک" subtitle="شاخص‌های ریسک و هشدارها">
      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[1,2,3,4,5,6,7,8].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {RISK_METRICS.map((m) => (
            <div key={m.label} className="glass-card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-surface-400">{m.label}</span>
                <span className={`w-2 h-2 rounded-full ${
                  m.status === "safe" ? "bg-accent-emerald" : m.status === "warning" ? "bg-accent-amber" : "bg-accent-rose"
                }`} />
              </div>
              <div className={`text-lg font-bold font-mono ${
                m.status === "safe" ? "text-accent-emerald" : m.status === "warning" ? "text-accent-amber" : "text-accent-rose"
              }`}>{m.value}</div>
              <div className="text-xs text-surface-500 mt-1">{m.description}</div>
            </div>
          ))}
        </div>
      )}

      <div className="glass-card p-5">
        <h2 className="font-bold text-surface-200 mb-4">هشدارهای ریسک</h2>
        <div className="space-y-2">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-accent-rose/10 border border-accent-rose/20">
            <span className="text-accent-rose text-lg">⚠</span>
            <div>
              <p className="text-sm text-surface-200">Max Drawdown از حد مجاز فراتر رفته</p>
              <p className="text-xs text-surface-400">حد مجاز: -۱۰٪ | مقدار فعلی: -۱۵.۳٪</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-accent-amber/10 border border-accent-amber/20">
            <span className="text-accent-amber text-lg">⚡</span>
            <div>
              <p className="text-sm text-surface-200">تمرکز پرتفوی بالا</p>
              <p className="text-xs text-surface-400">بزرگترین موقعیت ۳۲٪ از پرتفوی را تشکیل می‌دهد</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-800/50 border border-surface-700">
            <span className="text-accent-emerald text-lg">✓</span>
            <div>
              <p className="text-sm text-surface-200">همه شاخص‌های دیگر در محدوده مجاز</p>
              <p className="text-xs text-surface-400">آخرین بررسی: ۱۴۰۴/۰۳/۲۶ ۱۲:۰۰</p>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
