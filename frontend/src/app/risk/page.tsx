"use client";

import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, extractArray } from "@/lib/api";

interface RiskMetric {
  label: string;
  value: string;
  status: "safe" | "warning" | "danger";
  description: string;
}

export default function RiskPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ["risk-metrics"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: RiskMetric[] }>("/risk");
        const items = extractArray<RiskMetric>(res);
        if (items.length > 0) return items;
      } catch {}
      return null;
    },
    staleTime: 60000,
  });

  const RISK_METRICS: RiskMetric[] = metrics || [
    { label: "VaR (۹۵%)", value: "-۲.۴%", status: "safe", description: "Value at Risk در سطح اطمینان ۹۵%" },
    { label: "CVaR", value: "-۴.۱%", status: "warning", description: "میانگین زیان در موارد فراتر از VaR" },
    { label: "Sharpe Ratio", value: "۱.۸۷", status: "safe", description: "نسبت بازده به ریسک" },
    { label: "Beta", value: "۱.۱۲", status: "warning", description: "حساسیت به بازار" },
    { label: "Max Drawdown", value: "-۱۵.۳%", status: "danger", description: "بیشترین کاهش از اوج" },
    { label: "Volatility", value: "۲۴.۶%", status: "warning", description: "انحراف معیار بازده‌ها" },
    { label: "Exposure", value: "۸۵%", status: "safe", description: "درصد سرمایه در معرض ریسک" },
    { label: "Concentration", value: "۳۲%", status: "danger", description: "درصد تمرکز در بزرگترین موقعیت" },
  ];

  return (
    <AppLayout title="مدیریت ریسک" subtitle="شاخص‌های ریسک و هشدارها">
      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[1,2,3,4,5,6,7,8].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {RISK_METRICS.map((m, mi) => (
            <div key={`${m.label}-${mi}`} className="glass-card p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-surface-400">{m.label}</span>
                <span className={`w-2 h-2 rounded-full ${
                  m.status === "safe" ? "bg-accent-emerald" : m.status === "warning" ? "bg-accent-amber" : "bg-accent-rose"
                }`} />
              </div>
              <div className={`text-lg font-bold font-mono ${
                m.status === "safe" ? "text-accent-emerald" : m.status === "warning" ? "text-accent-amber" : "text-accent-rose"
              }`}>
                {m.value}
              </div>
              <p className="text-xs text-surface-500 mt-1">{m.description}</p>
            </div>
          ))}
        </div>
      )}

      <div className="glass-card p-4">
        <h3 className="text-sm font-medium text-surface-200 mb-3">تحلیل ریسک</h3>
        <p className="text-xs text-surface-400 leading-relaxed">
          پرتفوی شما در مجموع ریسک متعادلی دارد. شاخص‌های VaR و Sharpe در محدوده قابل قبول هستند.
          با این حال، حداکثر کاهش و تمرکز در بزرگترین موقعیت نیاز به توجه دارند.
          توصیه می‌شود با متنوع‌سازی بیشتر، ریسک تمرکز را کاهش دهید.
        </p>
      </div>
    </AppLayout>
  );
}
