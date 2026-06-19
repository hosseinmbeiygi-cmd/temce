"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Sidebar from "@/components/Sidebar";
import { apiGet, apiPost } from "@/lib/api";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Portfolio {
  id: string;
  name: string;
  description: string;
  initial_capital: number;
  current_value: number;
  currency: string;
  positions: any[];
}

interface PortfolioList {
  items: { id: string; name: string; current_value: number; total_return_pct: number }[];
  total: number;
}

export default function PortfolioPage() {
  const queryClient = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newPortfolioName, setNewPortfolioName] = useState("");

  const { data: portfolios, isLoading: loadingList } = useQuery({
    queryKey: ["portfolios"],
    queryFn: () => apiGet<PortfolioList>("/portfolios"),
  });

  const { data: activePortfolio, isLoading: loadingDetail } = useQuery({
    queryKey: ["portfolio", selectedId],
    queryFn: () => apiGet<Portfolio>(`/portfolios/${selectedId}`),
    enabled: !!selectedId,
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => apiPost("/portfolios", { name, description: "", initial_capital: 0, currency: "IRR" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      toast.success("پرتفوی با موفقیت ایجاد شد");
      setIsCreating(false);
      setNewPortfolioName("");
    },
    onError: (err: any) => toast.error(err.message || "خطا در ایجاد پرتفوی"),
  });

  return (
    <div className="flex h-screen overflow-hidden" dir="rtl">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">مدیریت پرتفوی</h1>
            <p className="text-sm text-surface-500 mt-1">مانیتورینگ دارایی‌ها و تحلیل سود و زیان</p>
          </div>
          <button 
            onClick={() => setIsCreating(!isCreating)}
            className="bg-primary-600 hover:bg-primary-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition"
          >
            {isCreating ? "لغو" : "پرتفوی جدید +"}
          </button>
        </div>

        {isCreating && (
          <div className="glass-card p-6 mb-6 animate-in fade-in slide-in-from-top-4">
            <h2 className="font-bold text-surface-200 mb-4">ایجاد پرتفوی جدید</h2>
            <div className="flex gap-3">
              <input 
                type="text" 
                value={newPortfolioName} 
                onChange={(e) => setNewPortfolioName(e.target.value)}
                placeholder="نام پرتفوی (مثلا: بلندمدت، ریسکی...)"
                className="flex-1 px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500"
              />
              <button 
                onClick={() => createMutation.mutate(newPortfolioName)}
                disabled={createMutation.isPending || !newPortfolioName}
                className="px-6 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded text-sm font-medium disabled:opacity-50"
              >
                {createMutation.isPending ? "در حال ثبت..." : "ثبت"}
              </button>
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-4 gap-6">
          {/* Portfolio List */}
          <div className="lg:col-span-1 space-y-3">
            <h3 className="text-xs font-bold text-surface-500 uppercase tracking-wider mb-3">پرتفوهای من</h3>
            {loadingList ? (
              <div className="space-y-2">
                {[1,2,3].map(i => <div key={i} className="h-16 bg-surface-800 animate-pulse rounded-xl" />)}
              </div>
            ) : portfolios?.items.map(p => (
              <div 
                key={p.id} 
                onClick={() => setSelectedId(p.id)}
                className={`p-4 rounded-xl cursor-pointer transition-all border ${
                  selectedId === p.id ? "bg-primary-600/20 border-primary-600 text-primary-100" : "bg-surface-900/50 border-surface-800 text-surface-400 hover:bg-surface-800"
                }`}
              >
                <div className="font-bold text-sm">{p.name}</div>
                <div className="text-xs opacity-70 mt-1">{p.current_value.toLocaleString()} ریال</div>
              </div>
            )) || <div className="text-xs text-surface-600 text-center py-4">پرتفویی یافت نشد</div>}
          </div>

          {/* Portfolio Detail */}
          <div className="lg:col-span-3 space-y-6">
            {!selectedId ? (
              <div className="glass-card h-full flex flex-col items-center justify-center text-center p-12">
                <span className="text-4xl mb-4">💼</span>
                <h3 className="text-lg font-bold text-surface-200">پرتفویی انتخاب نشده است</h3>
                <p className="text-sm text-surface-500 mt-2">برای مشاهده جزئیات دارایی‌ها، یک پرتفوی را از لیست سمت راست انتخاب کنید.</p>
              </div>
            ) : loadingDetail ? (
              <div className="space-y-6">
                <div className="h-32 bg-surface-800 animate-pulse rounded-2xl" />
                <div className="h-64 bg-surface-800 animate-pulse rounded-2xl" />
                <div className="h-96 bg-surface-800 animate-pulse rounded-2xl" />
              </div>
            ) : activePortfolio && (
              <>
                {/* Stats Summary */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="glass-card p-5">
                    <div className="text-xs text-surface-500 mb-1">ارزش فعلی</div>
                    <div className="text-2xl font-black text-surface-100">{activePortfolio.current_value.toLocaleString()} <span className="text-xs font-normal">ریال</span></div>
                  </div>
                  <div className="glass-card p-5">
                    <div className="text-xs text-surface-500 mb-1">سرمایه اولیه</div>
                    <div className="text-2xl font-black text-surface-400">{activePortfolio.initial_capital.toLocaleString()} <span className="text-xs font-normal">ریال</span></div>
                  </div>
                  <div className="glass-card p-5">
                    <div className="text-xs text-surface-500 mb-1">سود/زیان کل</div>
                    <div className={`text-2xl font-black ${activePortfolio.current_value >= activePortfolio.initial_capital ? "text-accent-emerald" : "text-accent-rose"}`}>
                      {(activePortfolio.current_value - activePortfolio.initial_capital).toLocaleString()}
                    </div>
                  </div>
                </div>

                {/* Equity Curve Chart */}
                <div className="glass-card p-6">
                  <h3 className="font-bold text-surface-200 mb-6">نمودار رشد سرمایه (NAV)</h3>
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={activePortfolio.positions.map((p, i) => ({ name: i, val: p.market_value }))}>
                        <defs>
                          <linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                        <XAxis dataKey="name" hide />
                        <YAxis stroke="#4b5563" fontSize={12} tickFormatter={(val) => `${(val/1e9).toFixed(1)}B`} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#f3f4f6' }}
                          itemStyle={{ color: '#818cf8' }}
                        />
                        <Area type="monotone" dataKey="val" stroke="#6366f1" fillOpacity={1} fill="url(#colorVal)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Positions Table */}
                <div className="glass-card overflow-hidden">
                  <div className="p-5 border-b border-surface-800">
                    <h3 className="font-bold text-surface-200">موقعیت‌های فعلی</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-right text-sm">
                      <thead>
                        <tr className="text-surface-500 bg-surface-900/50 border-b border-surface-800">
                          <th className="p-4 font-medium">نماد</th>
                          <th className="p-4 font-medium">تعداد</th>
                          <th className="p-4 font-medium">میانگین خرید</th>
                          <th className="p-4 font-medium">قیمت فعلی</th>
                          <th className="p-4 font-medium">ارزش بازار</th>
                          <th className="p-4 font-medium">سود/زیان</th>
                          <th className="p-4 font-medium">وزن</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activePortfolio.positions.map((pos, i) => (
                          <tr key={i} className="border-b border-surface-800/50 hover:bg-white/5 transition-colors">
                            <td className="p-4 font-bold text-surface-200">{pos.symbol}</td>
                            <td className="p-4 font-mono text-surface-400">{pos.quantity.toLocaleString()}</td>
                            <td className="p-4 font-mono text-surface-400">{pos.avg_cost?.toLocaleString()}</td>
                            <td className="p-4 font-mono text-surface-200">{pos.current_price?.toLocaleString()}</td>
                            <td className="p-4 font-mono text-surface-200">{pos.market_value?.toLocaleString()}</td>
                            <td className={`p-4 font-mono ${pos.unrealized_pnl >= 0 ? "text-accent-emerald" : "text-accent-rose"}`}>
                              {pos.unrealized_pnl >= 0 ? "+" : ""}{pos.unrealized_pnl?.toLocaleString()}
                            </td>
                            <td className="p-4">
                              <div className="flex items-center gap-2">
                                <div className="w-12 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                                  <div className="h-full bg-primary-500" style={{ width: `${pos.weight_pct}%` }} />
                                </div>
                                <span className="text-xs text-surface-500">{pos.weight_pct}%</span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
