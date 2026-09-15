"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, apiPost, extractArray } from "@/lib/api";

interface NewsItem {
  id: string;
  title: string;
  summary: string;
  source: string;
  url: string;
  date: string;
  category: string;
  fullContent: string;
  trending: boolean;
  sentiment: string;
  sentiment_score: number;
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
  const [sourceFilter, setSourceFilter] = useState("");
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const PAGE_SIZE = 20;

  const { data: news, isLoading, isError, error } = useQuery({
    queryKey: ["news-full"],
    queryFn: async () => {
      const response = await apiGet<unknown>("/news");
      const items = extractArray<Record<string, unknown>>(response);
      if (items.length > 0 && items[0]?.published_at) {
        return items.map((item) => ({
          id: String(item.id || ""),
          title: String(item.title || ""),
          summary: String(item.summary || ""),
          source: String(item.source || ""),
          url: String(item.url || ""),
          date: String(item.published_at || item.date || "").split("T")[0] || "",
          category: String(item.category || "market").replace("company", "companies"),
          fullContent: String(item.content || item.summary || ""),
          trending: Boolean(item.trending || false),
          sentiment: String(item.sentiment || "neutral"),
          sentiment_score: Number(item.sentiment_score || 0),
        })) as unknown as NewsItem[];
      }
      if (items.length > 0 && typeof items[0]?.title === "string") {
        return items.map((item) => ({
          id: String(item.id || ""),
          title: String(item.title || ""),
          summary: String(item.summary || ""),
          source: String(item.source || ""),
          url: String(item.url || ""),
          date: String(item.date || item.published_at || "").split("T")[0] || "",
          category: String(item.category || "market").replace("company", "companies"),
          fullContent: String(item.fullContent || item.content || item.summary || ""),
          trending: Boolean(item.trending || false),
          sentiment: String(item.sentiment || "neutral"),
          sentiment_score: Number(item.sentiment_score || 0),
        })) as unknown as NewsItem[];
      }
      return [] as NewsItem[];
    },
    refetchInterval: 120000,
  });

  // Refresh news mutation
  const refreshMutation = useMutation({
    mutationFn: async () => {
      const res = await apiPost<{ success: boolean; data: { status: string; last_result?: Record<string, number> } }>("/news/refresh", {});
      return res;
    },
    onSuccess: () => {
      setRefreshActive(true);
    },
  });

  // Poll refresh status
  const [refreshActive, setRefreshActive] = useState(false);
  const { data: refreshStatus } = useQuery({
    queryKey: ["news-refresh-status"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: { running: boolean; last_run?: string; last_result?: Record<string, number> } }>("/news/refresh/status");
      return res?.data;
    },
    enabled: refreshActive,
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (refreshActive && refreshStatus && !refreshStatus.running) {
      queryClient.invalidateQueries({ queryKey: ["news-full"] });
      setRefreshActive(false);
    }
  }, [refreshActive, refreshStatus, queryClient]);

  // Extract unique sources for filter
  const allSources = news ? [...new Set(news.map((n: NewsItem) => n.source).filter(Boolean))].sort() : [];

  // Filter + paginate
  const filtered = news?.filter((item: NewsItem) => {
    if (filter !== "all" && item.category !== filter) return false;
    if (sourceFilter && item.source !== sourceFilter) return false;
    if (searchQuery) {
      const q = searchQuery.trim().toLowerCase();
      return item.title.toLowerCase().includes(q) || item.summary.toLowerCase().includes(q) || item.source.toLowerCase().includes(q);
    }
    return true;
  });

  const totalPages = Math.max(1, Math.ceil((filtered?.length || 0) / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const paginated = filtered?.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE) || [];
  const trendingNews = news?.filter((n: NewsItem) => n.trending);

  // Reset page when filters change — event-driven pagination sync, not derived state.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage(1);
  }, [filter, sourceFilter, searchQuery]);

  const getSentimentColor = (sentiment_score: number) => {
    if (sentiment_score > 0.3) return "text-accent-emerald";
    if (sentiment_score < -0.3) return "text-accent-rose";
    return "text-surface-500";
  };

  const getSentimentDot = (sentiment_score: number) => {
    if (sentiment_score > 0.3) return "bg-accent-emerald";
    if (sentiment_score < -0.3) return "bg-accent-rose";
    return "bg-surface-500";
  };

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
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending || refreshActive}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-700 text-white text-sm rounded-lg transition-colors"
        >
          {(refreshMutation.isPending || refreshActive) ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              در حال بروزرسانی...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              بروزرسانی اخبار
            </>
          )}
        </button>
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
          {isError ? (
            <div className="glass-card p-8 text-center text-surface-500">
              <p className="mb-2 text-accent-rose">خطا در دریافت اخبار</p>
              <p className="text-xs text-surface-600">{error?.message || "اتصال به سرور برقرار نشد"}</p>
            </div>
          ) : isLoading ? (
            [1,2,3].map(i => <div key={i} className="glass-card p-5"><div className="h-20 bg-surface-800 animate-pulse rounded-lg" /></div>)
          ) : filtered && filtered.length > 0 ? filtered.map((item: NewsItem, i: number) => (
            <a
              key={item.id || `news-${i}`}
              href={item.url || "#"}
              target={item.url ? "_blank" : undefined}
              rel={item.url ? "noopener noreferrer" : undefined}
              className="glass-card p-5 block hover:bg-surface-800/50 transition-colors"
            >
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
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setExpandedId(expandedId === item.id ? null : item.id); }}
                className="text-xs text-primary-400 hover:text-primary-300 mt-2 transition-colors"
              >
                {expandedId === item.id ? "بستن" : "مشاهده کامل"}
              </button>
              {expandedId === item.id && (
                <div className="mt-3 pt-3 border-t border-surface-700">
                  <p className="text-sm text-surface-300 leading-relaxed">{item.fullContent}</p>
                </div>
              )}
            </a>
          )) : <div className="glass-card p-8 text-center text-surface-500">
              <p className="mb-2">هیچ خبری یافت نشد</p>
              <p className="text-xs text-surface-600">برای دریافت اخبار، ابتدا دستور <code className="bg-surface-800 px-1.5 py-0.5 rounded">python scripts/fetch_news.py</code> را اجرا کنید</p>
            </div>}
        </div>

        <div className="space-y-4">
          <div className="glass-card p-5">
            <h3 className="font-bold text-surface-200 mb-3">🔥 داغ‌ترین اخبار</h3>
            <div className="space-y-3">
              {isError ? (
                <div className="text-xs text-surface-600 text-center py-2">خطا در بارگذاری</div>
              ) : isLoading ? (
                [1,2,3].map(i => <div key={i} className="h-10 bg-surface-800 animate-pulse rounded-lg" />)
              ) : trendingNews && trendingNews.length > 0 ? trendingNews.map((item: NewsItem, i: number) => (
                <a
                  key={item.id || `trending-${i}`}
                  href={item.url || "#"}
                  target={item.url ? "_blank" : undefined}
                  rel={item.url ? "noopener noreferrer" : undefined}
                  className="block pb-3 border-b border-surface-700/50 last:border-0 last:pb-0 hover:bg-surface-800/30 rounded px-1 transition-colors"
                >
                  <p className="text-sm text-surface-200 leading-snug mb-1">{item.title}</p>
                  <span className="text-xs text-surface-500">{item.source} • {item.date}</span>
                </a>
              )) : <div className="text-xs text-surface-600 text-center py-2">موردی یافت نشد</div>}
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