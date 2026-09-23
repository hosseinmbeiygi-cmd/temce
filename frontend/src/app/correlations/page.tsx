"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  HelpCircle,
} from "lucide-react";

interface CorrelationPair {
  pair: string;
  symbolA: string;
  symbolB: string;
  correlation: number;
  strength: "strong" | "moderate" | "weak";
  direction: "positive" | "negative";
  trend: "increasing" | "stable" | "decreasing";
  description: string;
}

interface CorrelationCategory {
  name: string;
  pairs: CorrelationPair[];
}

function fmtCorr(v: number): string {
  return (v * 100).toFixed(1) + "%";
}

function getStrengthColor(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 0.7) return "text-accent-emerald";
  if (abs >= 0.4) return "text-accent-amber";
  return "text-surface-400";
}

function getStrengthBg(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 0.7) return "bg-accent-emerald/10";
  if (abs >= 0.4) return "bg-accent-amber/10";
  return "bg-surface-800/30";
}

function getDirectionIcon(dir: string) {
  if (dir === "positive") return TrendingUp;
  if (dir === "negative") return TrendingDown;
  return Minus;
}

const MOCK_CATEGORIES: CorrelationCategory[] = [
  {
    name: "فلزات اساسی",
    pairs: [
      { pair: "مس / فولاد", symbolA: "CU", symbolB: "SB", correlation: 0.82, strength: "strong", direction: "positive", trend: "increasing", description: "همبستگی قوی به دلیل وابستگی هر دو به بخش ساخت‌وساز و صنعت" },
      { pair: "روی / سرب", symbolA: "ZN", symbolB: "PB", correlation: 0.74, strength: "strong", direction: "positive", trend: "stable", description: "همبستگی تاریخی به دلیل استخراج هم‌محصول" },
      { pair: "آلومینیوم / مس", symbolA: "AL", symbolB: "CU", correlation: 0.65, strength: "moderate", direction: "positive", trend: "decreasing", description: "جانشینی مس با آلومینیوم در برخی صنایع باعث کاهش همبستگی شده" },
    ],
  },
  {
    name: "محصولات کشاورزی",
    pairs: [
      { pair: "زعفران / زیره", symbolA: "ZRS1", symbolB: "ZIR", correlation: 0.36, strength: "weak", direction: "positive", trend: "stable", description: "همبستگی ضعیف به دلیل عوامل اقلیمی متفاوت" },
      { pair: "گندم / جو", symbolA: "GND", symbolB: "JO", correlation: 0.78, strength: "strong", direction: "positive", trend: "increasing", description: "کشت مشترک و وابستگی به شرایط آب‌وهوایی یکسان" },
      { pair: "پسته / بادام", symbolA: "PST", symbolB: "BAD", correlation: 0.52, strength: "moderate", direction: "positive", trend: "stable", description: "بازارهای صادراتی مشترک" },
    ],
  },
  {
    name: "پتروشیمی",
    pairs: [
      { pair: "پلی‌اتیلن / پروپیلن", symbolA: "PCC", symbolB: "PP", correlation: 0.88, strength: "strong", direction: "positive", trend: "increasing", description: "وابستگی هر دو به قیمت نفت خام" },
      { pair: "قیر / نفت خام", symbolA: "QIR", symbolB: "CRU", correlation: 0.91, strength: "strong", direction: "positive", trend: "stable", description: "بالاترین همبستگی به دلیل خوراک مستقیم" },
      { pair: "یوتیلیتی / متانول", symbolA: "UTL", symbolB: "MTL", correlation: 0.43, strength: "weak", direction: "positive", trend: "decreasing", description: "جداسازی تدریجی بازارها" },
    ],
  },
  {
    name: "شاخص‌های اقتصادی",
    pairs: [
      { pair: "نرخ ارز / طلا", symbolA: "USD-IRR", symbolB: "GLD", correlation: 0.85, strength: "strong", direction: "positive", trend: "increasing", description: "همبستگی سنتی بازار ایران" },
      { pair: "شاخص بورس / نقدینگی", symbolA: "TEDPIX", symbolB: "LIQ", correlation: 0.67, strength: "moderate", direction: "positive", trend: "stable", description: "نقدینگی موتور اصلی بازار سهام" },
      { pair: "سکه / دلار", symbolA: "SKK", symbolB: "USD", correlation: 0.93, strength: "strong", direction: "positive", trend: "stable", description: "قوی‌ترین همبستگی در بازار ایران" },
    ],
  },
  {
    name: "بین‌المللی",
    pairs: [
      { pair: "طلا (داخلی) / طلا (جهانی)", symbolA: "GLD-IR", symbolB: "XAU", correlation: 0.72, strength: "strong", direction: "positive", trend: "decreasing", description: "تحت تأثیر نرخ ارز و عوارض واردات" },
      { pair: "نفت برنت / پتروشیمی", symbolA: "BRENT", symbolB: "PCC", correlation: 0.69, strength: "moderate", direction: "positive", trend: "stable", description: "با تأخیر زمانی ۲-۳ هفته" },
    ],
  },
];

function CorrelationBar({ value }: { value: number }) {
  const abs = Math.abs(value);
  const barWidth = Math.min(abs * 100, 100);
  const barColor = value >= 0
    ? "bg-gradient-to-r from-accent-emerald/60 to-accent-emerald"
    : "bg-gradient-to-r from-accent-rose to-accent-rose/60";

  return (
    <div className="flex items-center gap-3 w-full">
      <div className="flex-1 h-2 bg-surface-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-bold w-14 text-right ${getStrengthColor(value)}`}>
        {fmtCorr(value)}
      </span>
    </div>
  );
}

export default function CorrelationsPage() {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"strength" | "name">("strength");

  const { data: categories, isLoading } = useQuery({
    queryKey: ["correlations"],
    queryFn: async () => {
      try {
        // Real computed correlations (backend /analysis/correlations);
        // static demo list is only a last-resort fallback.
        const r = await apiGet<{ success?: boolean; data?: { categories?: CorrelationCategory[] } | CorrelationCategory[] }>(
          "/analysis/correlations"
        );
        const payload = r?.data;
        const list = Array.isArray(payload) ? payload : payload?.categories;
        if (list?.length) return list as CorrelationCategory[];
      } catch {}
      return MOCK_CATEGORIES;
    },
    staleTime: 300000,
  });

  const displayCategories = categories?.map((cat) => {
    const sorted = [...cat.pairs].sort((a, b) =>
      sortBy === "strength" ? Math.abs(b.correlation) - Math.abs(a.correlation) : a.pair.localeCompare(b.pair)
    );
    return { ...cat, pairs: sorted };
  });

  return (
    <AppLayout title="همبستگی‌ها" subtitle="تحلیل همبستگی بین دارایی‌ها و بازارهای مختلف">
      {/* Disclaimer */}
      <div className="mb-5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-[11px] text-amber-300">
        <strong>⚠️ هشدار:</strong> همبستگی‌ها ممکن است در طول زمان تغییر کنند و نباید به‌تنهایی مبنای تصمیم‌گیری قرار گیرند.
      </div>

      {/* Controls */}
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-500">مرتب‌سازی:</span>
          <button
            onClick={() => setSortBy("strength")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              sortBy === "strength" ? "bg-accent-cyan/20 text-accent-cyan" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            قدرت همبستگی
          </button>
          <button
            onClick={() => setSortBy("name")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              sortBy === "name" ? "bg-accent-cyan/20 text-accent-cyan" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            نام
          </button>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-surface-500">
          <span className="flex items-center gap-1"><TrendingUp className="size-3 text-accent-emerald" /> مثبت</span>
          <span className="flex items-center gap-1"><TrendingDown className="size-3 text-accent-rose" /> منفی</span>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : !displayCategories?.length ? (
        <div className="flex min-h-[30vh] flex-col items-center justify-center gap-2 text-surface-600">
          <BarChart3 className="size-12" />
          <p className="text-sm">داده‌ای برای نمایش وجود ندارد</p>
        </div>
      ) : (
        <div className="space-y-6" dir="rtl">
          {displayCategories.map((cat) => (
            <Card key={cat.name} title={cat.name}>
              <div className="space-y-3">
                {cat.pairs.map((p) => {
                  const DirIcon = getDirectionIcon(p.direction);
                  const isExpanded = expandedCategory === p.pair;
                  return (
                    <div
                      key={p.pair}
                      className="rounded-lg bg-surface-800/20 p-4 transition-all hover:bg-surface-800/40 cursor-pointer"
                      onClick={() => setExpandedCategory(isExpanded ? null : p.pair)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-surface-500">{p.symbolA}</span>
                          <span className="text-xs text-surface-600">/</span>
                          <span className="font-mono text-xs text-surface-500">{p.symbolB}</span>
                          <span className="text-sm font-medium text-surface-200 mr-2">{p.pair}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <DirIcon className={`size-3.5 ${p.direction === "positive" ? "text-accent-emerald" : p.direction === "negative" ? "text-accent-rose" : "text-surface-400"}`} />
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${getStrengthBg(p.correlation)} ${getStrengthColor(p.correlation)}`}>
                            {p.strength === "strong" ? "قوی" : p.strength === "moderate" ? "متوسط" : "ضعیف"}
                          </span>
                          <span className="text-[10px] text-surface-600">
                            {p.trend === "increasing" ? "⬆" : p.trend === "decreasing" ? "⬇" : "➡"}
                          </span>
                        </div>
                      </div>
                      <CorrelationBar value={p.correlation} />
                      {isExpanded && (
                        <div className="mt-3 border-t border-surface-800 pt-3 text-xs text-surface-400">
                          <HelpCircle className="inline size-3 ml-1 text-surface-500" />
                          {p.description}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Summary Stats */}
      {displayCategories && displayCategories.length > 0 && (
        <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "همبستگی قوی", value: displayCategories.flatMap(c => c.pairs).filter(p => p.strength === "strong").length.toString(), color: "text-accent-emerald" },
            { label: "همبستگی متوسط", value: displayCategories.flatMap(c => c.pairs).filter(p => p.strength === "moderate").length.toString(), color: "text-accent-amber" },
            { label: "همبستگی ضعیف", value: displayCategories.flatMap(c => c.pairs).filter(p => p.strength === "weak").length.toString(), color: "text-surface-400" },
            { label: "دسته‌بندی‌ها", value: displayCategories.length.toString(), color: "text-accent-cyan" },
          ].map((s) => (
            <div key={s.label} className="rounded-lg bg-surface-800/30 p-3 text-center">
              <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
              <div className="text-[10px] text-surface-500 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>
      )}
    </AppLayout>
  );
}
