"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import { apiGet } from "@/lib/api";

interface NewsItem {
  id: string;
  title: string;
  summary: string;
  source: string;
  date: string;
  category: string;
  fullContent: string;
  trending: boolean;
}

type CategoryKey = "all" | "market" | "companies" | "economic" | "political" | "international";

const CATEGORIES: { key: CategoryKey; label: string }[] = [
  { key: "all", label: "همه" },
  { key: "market", label: "بازار" },
  { key: "companies", label: "شرکت‌ها" },
  { key: "economic", label: "اقتصادی" },
  { key: "political", label: "سیاسی" },
  { key: "international", label: "بین‌المللی" },
];

const CATEGORY_LABELS: Record<string, string> = {
  market: "بازار", companies: "شرکت‌ها", economic: "اقتصادی",
  political: "سیاسی", international: "بین‌المللی",
};

export default function NewsPage() {
  const [filter, setFilter] = useState<CategoryKey>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: news, isLoading } = useQuery({
    queryKey: ["news-full"],
    queryFn: async () => {
      try {
        return await apiGet<any>("/news");
      } catch {}
      return [];
    },
    refetchInterval: 120000,
  });

  const filtered = news?.filter((item: any) => {
    if (filter !== "all" && item.category !== filter) return false;
    if (searchQuery) {
      const q = searchQuery.trim();
      return item.title.includes(q) || item.summary.includes(q) || item.source.includes(q);
    }
    return true;
  });

  const trendingNews = news?.filter((n: any) => n.trending);

  const getCategoryBadge = (cat: string) => {
    const colors: Record<string, string> = {
      market: "bg-accent-amber/15 text-accent-amber",
      companies: "bg-primary-600/15 text-primary-300",
      economic: "bg-accent-emerald/15 text-accent-emerald",
      political: "bg-accent-rose/15 text-accent-rose",
      international: "bg-accent-cyan/15 text-accent-cyan",
    };
    return colors[cat] || "bg-surface-600/30 text-surface-400";
  };

  return (
    <AppLayout title="اخبار بازار" subtitle="آخرین اخبار و رویدادهای بازار سرمایه">
      <div className="flex flex-wrap items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="جستجوی اخبار..."
            className="px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-56"
          />
          {isLoading && <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />}
        </div>
      </div>

      <div className="flex gap-2 mb-6 flex-wrap">
        {CATEGORIES.map((c) => (
          <button key={c.key} onClick={() => setFilter(c.key)}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === c.key ? "bg-primary-600 text-white" : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}>{c.label}</button>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {isLoading ? (
            [1,2,3].map(i => <div key={i} className="glass-card p-5"><div className="h-20 bg-surface-800 animate-pulse rounded-lg" /></div>)
          ) : filtered?.map((item: any) => (
            <div key={item.id} className="glass-card p-5">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${getCategoryBadge(item.category)}`}>
                    {CATEGORY_LABELS[item.category] || item.category}
                  </span>
                  {item.trending && <span className="text-xs text-accent-amber">🔥 داغ</span>}
                </div>
                <span className="text-xs text-surface-500">{item.source} • {item.date}</span>
              </div>
              <h3 className="font-bold text-surface-200 mb-1">{item.title}</h3>
              <p className="text-sm text-surface-400 leading-relaxed">{item.summary}</p>
              <button
                onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                className="text-xs text-primary-400 hover:text-primary-300 mt-2 transition-colors"
              >
                {expandedId === item.id ? "بستن" : "مشاهده کامل"}
              </button>
              {expandedId === item.id && (
                <div className="mt-3 pt-3 border-t border-surface-700">
                  <p className="text-sm text-surface-300 leading-relaxed">{item.fullContent}</p>
                </div>
              )}
            </div>
          )) || <div className="glass-card p-8 text-center text-surface-500">هیچ خبری با این معیارها یافت نشد</div>}
        </div>

        <div className="space-y-4">
          <div className="glass-card p-5">
            <h3 className="font-bold text-surface-200 mb-3">🔥 داغ‌ترین اخبار</h3>
            <div className="space-y-3">
              {isLoading ? (
                [1,2,3].map(i => <div key={i} className="h-10 bg-surface-800 animate-pulse rounded-lg" />)
              ) : trendingNews?.map((item: any) => (
                <div key={item.id} className="pb-3 border-b border-surface-700/50 last:border-0 last:pb-0">
                  <p className="text-sm text-surface-200 leading-snug mb-1">{item.title}</p>
                  <span className="text-xs text-surface-500">{item.source} • {item.date}</span>
                </div>
              )) || <div className="text-xs text-surface-600 text-center py-2">موردی یافت نشد</div>}
            </div>
          </div>
          <div className="glass-card p-5">
            <h3 className="font-bold text-surface-200 mb-3">موضوعات داغ</h3>
            <div className="flex flex-wrap gap-2">
              {["فولاد", "افزایش سرمایه", "نرخ بهره", "تورم", "عرضه اولیه", "شاخص کل"].map((topic) => (
                <span key={topic} className="text-xs px-2.5 py-1 rounded-full bg-surface-800 text-surface-300 hover:bg-surface-700 transition-colors cursor-pointer">
                  {topic}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
