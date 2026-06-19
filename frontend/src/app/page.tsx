"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Sidebar from "@/components/Sidebar";
import Skeleton from "@/components/Skeleton";
import { apiGet } from "@/lib/api";

interface Market {
  name: string;
  status: string;
  instruments: number;
  lastUpdate: string;
  change: string;
}

interface Signal {
  symbol: string;
  signal: string;
  strength: number;
  horizon: string;
  confidence: string;
}

interface Experiment {
  id: string;
  strategy: string;
  sharpe: number;
  trades: number;
  status: string;
}

interface CodalEntry {
  symbol: string;
  company: string;
  industry: string;
  lastPrice: number;
  change: number;
  volume: number;
  status: string;
}

interface NewsItem {
  id: string;
  title: string;
  summary: string;
  source: string;
  date: string;
  sentiment: string;
}

interface AnalysisData {
  sentiment: string;
  trend: string;
  marketStatus: string;
  topSectors: { name: string; change: string }[];
  summary: string;
}

interface ManualInput {
  symbol: string;
  name: string;
  apiKey: string;
  apiUrl: string;
}

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color: string }) {
  return (
    <div className="glass-card p-4 text-center">
      <div className={`text-2xl font-black ${color}`}>{value}</div>
      <div className="text-sm text-surface-400 mt-1">{label}</div>
      {sub && <div className="text-xs text-surface-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = { live: "bg-accent-emerald", delayed: "bg-accent-amber", error: "bg-accent-rose" };
  return <span className={`w-2 h-2 rounded-full ${colors[status] || "bg-surface-500"} inline-block`} />;
}

export default function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const [newSymbol, setNewSymbol] = useState('');
  const [newName, setNewName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiUrl, setApiUrl] = useState('');

  const { data: markets, isLoading: loadingMarkets } = useQuery({
    queryKey: ["markets-overview"],
    queryFn: async () => {
      const res = await fetch('/api/v1/market/overview');
      const json = await res.json();
      return json.success ? json.data.markets : [];
    },
    refetchInterval: 30000,
  });

  const { data: signals, isLoading: loadingSignals } = useQuery({
    queryKey: ["signals-recent"],
    queryFn: async () => {
      const res = await fetch('/api/v1/signals?page=1&page_size=5');
      const json = await res.json();
      return json.success ? json.data : [];
    },
    refetchInterval: 30000,
  });

  const { data: codal, isLoading: loadingCodal } = useQuery({
    queryKey: ["codal-recent"],
    queryFn: async () => {
      const res = await fetch('/api/v1/codal/?page=1&page_size=5');
      const json = await res.json();
      return json.success ? (json.data.results || json.data) : [];
    },
    refetchInterval: 30000,
  });

  const { data: news, isLoading: loadingNews } = useQuery({
    queryKey: ["news-recent"],
    queryFn: async () => {
      const res = await fetch('/api/v1/news/?page=1&page_size=3');
      const json = await res.json();
      return json.success ? (json.data.results || json.data) : [];
    },
    refetchInterval: 60000,
  });

  const { data: analysis, isLoading: loadingAnalysis } = useQuery({
    queryKey: ["analysis-overview"],
    queryFn: async () => {
      const res = await fetch('/api/v1/analysis/');
      const json = await res.json();
      return json.success ? json.data : null;
    },
    refetchInterval: 60000,
  });

  const isLoading = loadingMarkets || loadingSignals || loadingCodal || loadingNews || loadingAnalysis;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />

      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="flex flex-wrap items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">داشبورد</h1>
            <p className="text-sm text-surface-500 mt-1">خلاصه وضعیت سامانه — {new Date().toLocaleDateString("fa-IR")}</p>
          </div>
          <div className="flex items-center gap-2 mt-3 sm:mt-0">
            <span className={`w-2 h-2 rounded-full ${isLoading ? "bg-accent-amber animate-pulse" : "bg-accent-emerald animate-pulse"}`} />
            <span className="text-sm text-surface-400">
              {isLoading ? "در حال به‌روزرسانی..." : "سیستم فعال"}
            </span>
          </div>
        </div>

        {/* Manual Input Section */}
        <div className="glass-card p-5 mb-6">
          <h2 className="font-bold text-surface-200 mb-3">ورود اطلاعات دستی</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <div>
              <label className="text-xs text-surface-400 block mb-1">نماد (کلید دسترسی)</label>
              <input type="text" value={newSymbol} onChange={e => setNewSymbol(e.target.value)} placeholder="مثلا: فولاد..." className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500" />
            </div>
            <div>
              <label className="text-xs text-surface-400 block mb-1">نام</label>
              <input type="text" value={newName} onChange={e => setNewName(e.target.value)} placeholder="نام اختیاری..." className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500" />
            </div>
            <div>
              <label className="text-xs text-surface-400 block mb-1">کلید API</label>
              <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="کلید API..." className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500" />
            </div>
            <div>
              <label className="text-xs text-surface-400 block mb-1">URL API</label>
              <input type="text" value={apiUrl} onChange={e => setApiUrl(e.target.value)} placeholder="https://api.example.com/..." className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500" />
            </div>
            <div>
              <button className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded text-sm font-medium transition-colors">افزودن ورودی</button>
            </div>
          </div>
        </div>

        {/* Codal Section */}
        <div className="glass-card p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold text-surface-200">آخرین اطلاعات کدال</h2>
            <span className="text-xs text-surface-500">{codal?.length || 0} شرکت</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 font-medium">نماد</th>
                  <th className="pb-2 font-medium">شرکت</th>
                  <th className="pb-2 font-medium">آخرین قیمت</th>
                  <th className="pb-2 font-medium">تغییر</th>
                </tr>
              </thead>
              <tbody>
                {loadingCodal ? (
                  [1,2,3,4,5].map(i => <tr key={i} className="border-b border-surface-800/50"><td colSpan={4} className="py-4"><Skeleton className="h-4 w-full" /></td></tr>)
                ) : codal?.slice(0, 5).map((c: any) => (
                  <tr key={c.symbol} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 font-bold text-surface-200">{c.symbol}</td>
                    <td className="py-2.5 text-surface-300">{c.company}</td>
                    <td className="py-2.5 font-mono text-surface-200">{c.lastPrice?.toLocaleString()}</td>
                    <td className={`py-2.5 font-mono ${c.change >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {c.change >= 0 ? "+" : ""}{c.change}%
                    </td>
                  </tr>
                )) || <tr><td colSpan={4} className="py-4 text-center text-surface-600">داده‌ای یافت نشد</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* News + Analysis Row */}
        <div className="grid lg:grid-cols-2 gap-4 mb-6">
          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-3">اخبار آخر</h2>
            <div className="space-y-3">
              {loadingNews ? (
                [1,2,3].map(i => <Skeleton key={i} className="h-20 w-full rounded-lg" />)
              ) : news?.slice(0, 3).map((n: any) => (
                <div key={n.id} className="p-3 rounded-lg bg-white/5">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-medium text-surface-200 line-clamp-2">{n.title}</h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                      n.sentiment === "positive" ? "bg-accent-emerald/15 text-accent-emerald" :
                      n.sentiment === "negative" ? "bg-accent-rose/15 text-accent-rose" :
                      "bg-surface-600/30 text-surface-400"
                    }`}>
                      {n.sentiment === "positive" ? "مثبت" : n.sentiment === "negative" ? "منفی" : "خنثی"}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 mt-1 line-clamp-2">{n.summary}</p>
                  <div className="flex items-center gap-2 mt-2 text-xs text-surface-500">
                    <span>{n.source}</span><span>·</span><span>{n.date}</span>
                  </div>
                </div>
              )) || <div className="text-center py-4 text-surface-600">خبری یافت نشد</div>}
            </div>
          </div>

          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-3">تحلیل بازار</h2>
            {loadingAnalysis ? (
              <Skeleton className="h-48 w-full" />
            ) : analysis ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-400">احساسات:</span>
                    <span className={`text-sm font-medium ${
                      analysis.sentiment === "مثبت" ? "text-accent-emerald" :
                      analysis.sentiment === "منفی" ? "text-accent-rose" :
                      "text-accent-amber"
                    }`}>{analysis.sentiment}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-400">روند:</span>
                    <span className={`text-sm font-medium ${
                      analysis.trend === "صعودی" ? "text-accent-emerald" : "text-accent-rose"
                    }`}>{analysis.trend}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-400">وضعیت:</span>
                    <span className="text-sm text-surface-200">{analysis.marketStatus}</span>
                  </div>
                </div>
                <p className="text-xs text-surface-400 leading-relaxed">{analysis.summary}</p>
                {analysis.topSectors?.length > 0 && (
                  <div>
                    <span className="text-xs text-surface-500 block mb-1">بخش‌های برتر:</span>
                    <div className="flex flex-wrap gap-2">
                      {analysis.topSectors.map((s: any) => (
                        <span key={s.name} className="text-xs px-2 py-1 rounded-full bg-white/5 text-surface-300">
                          {s.name} <span className={s.change.startsWith("+") ? "text-accent-emerald" : "text-accent-rose"}>{s.change}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : <p className="text-xs text-surface-500">داده‌ای در دسترس نیست</p>}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <StatCard label="موتور فعال" value="۵۳" sub="از ۵۵" color="text-accent-emerald" />
          <StatCard label="بازار متصل" value={markets?.length || 0} sub="با اتصال فعال" color="text-accent-cyan" />
          <StatCard label="آخرین Signal" value={signals?.length || 0} sub={`قوی: ${signals?.filter((s: any) => s.confidence === "بالا").length || 0} سیگنال`} color="text-accent-amber" />
          <StatCard label="Experiment‌ها" value="۱۲۴" sub="امروز: ۸" color="text-accent-violet" />
        </div>

        <div className="grid lg:grid-cols-2 gap-4 mb-6">
          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-3">بازارهای فعال</h2>
            <div className="space-y-2">
              {loadingMarkets ? (
                [1,2,3,4].map(i => <Skeleton key={i} className="h-12 w-full" />)
              ) : markets?.map((m: any) => (
                <div key={m.name} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/5">
                  <div className="flex items-center gap-2">
                    <StatusDot status={m.status} />
                    <span className="text-sm text-surface-200">{m.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-surface-400">{m.instruments} نماد</span>
                    <span className={m.change.startsWith("+") ? "text-accent-emerald" : "text-accent-rose"}>{m.change}</span>
                  </div>
                </div>
              )) || <div className="text-center py-4 text-surface-600">بازاری یافت نشد</div>}
            </div>
          </div>

          <div className="glass-card p-5">
            <h2 className="font-bold text-surface-200 mb-3">آخرین سیگنال‌ها</h2>
            <div className="space-y-1">
              {loadingSignals ? (
                [1,2,3,4,5].map(i => <Skeleton key={i} className="h-12 w-full" />)
              ) : signals?.map((s: any) => (
                <div key={s.symbol} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/5">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-surface-200 w-14">{s.symbol}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      s.signal === "خرید" ? "bg-accent-emerald/15 text-accent-emerald" :
                      s.signal === "فروش" ? "bg-accent-rose/15 text-accent-rose" :
                      "bg-surface-600/30 text-surface-400"
                    }`}>{s.signal}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-surface-400">
                    <span>{s.confidence}</span>
                    <span className="font-mono">{(s.strength * 100).toFixed(0)}%</span>
                  </div>
                </div>
              )) || <div className="text-center py-4 text-surface-600">سیگنالی یافت نشد</div>}
            </div>
          </div>
        </div>

        <div className="glass-card p-5">
          <h2 className="font-bold text-surface-200 mb-3">آخرین Experiment‌ها</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 font-medium">ID</th>
                  <th className="pb-2 font-medium">استراتژی</th>
                  <th className="pb-2 font-medium">Sharpe</th>
                  <th className="pb-2 font-medium">معاملات</th>
                  <th className="pb-2 font-medium">وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { id: "EXP-۰۰۱", strategy: "Momentum_v3", sharpe: 2.14, trades: 342, status: "موفق" },
                  { id: "EXP-۰۰۲", strategy: "MeanReversion_v2", sharpe: 1.87, trades: 891, status: "موفق" },
                  { id: "EXP-۰۰۳", strategy: "QueueImbalance_v1", sharpe: 0.92, trades: 56, status: "ناموفق" },
                  { id: "EXP-۰۰۴", strategy: "ML_Alpha_v5", sharpe: 2.43, trades: 1204, status: "موفق" },
                ].map((e) => (
                  <tr key={e.id} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 font-mono text-xs text-surface-400">{e.id}</td>
                    <td className="py-2.5 text-surface-200">{e.strategy}</td>
                    <td className={`py-2.5 font-mono ${e.sharpe > 1.5 ? "text-accent-emerald" : "text-accent-rose"}`}>{e.sharpe.toFixed(2)}</td>
                    <td className="py-2.5 text-surface-400">{e.trades.toLocaleString()}</td>
                    <td className="py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        e.status === "موفق" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"
                      }`}>{e.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
