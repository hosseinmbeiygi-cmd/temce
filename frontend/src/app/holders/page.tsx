"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";

interface MajorHolder {
  rank: number;
  name: string;
  shares: number;
  percentage: number;
  monthlyChange: number;
}

interface InsiderTrade {
  date: string;
  type: "buy" | "sell";
  count: number;
  price: number;
}

const IRANIAN_SYMBOLS = [
  { code: "فولاد", name: "فولاد مبارکه اصفهان" },
  { code: "شپنا", name: "پالایش نفت اصفهان" },
  { code: "وبملت", name: "بانک ملت" },
  { code: "خودرو", name: "ایران خودرو" },
  { code: "فملی", name: "ملی صنایع مس ایران" },
  { code: "تاپیکو", name: "سرمایه‌گذاری نفت و گاز تامین" },
  { code: "وغدیر", name: "سرمایه‌گذاری غدیر" },
  { code: "شتران", name: "پالایش نفت تهران" },
];

const FALLBACK_HOLDERS: MajorHolder[] = [
  { rank: 1, name: "سازمان توسعه و نوسازی معادن و صنایع معدنی ایران (ایمیدرو)", shares: 2850000000, percentage: 17.8, monthlyChange: 0.0 },
  { rank: 2, name: "شرکت سرمایه‌گذاری تأمین اجتماعی (شستا)", shares: 1950000000, percentage: 12.2, monthlyChange: 0.5 },
  { rank: 3, name: "صندوق بازنشستگی کشوری", shares: 1420000000, percentage: 8.9, monthlyChange: -0.2 },
  { rank: 4, name: "شرکت سرمایه‌گذاری ملی ایران", shares: 980000000, percentage: 6.1, monthlyChange: 0.1 },
  { rank: 5, name: "سرمایه‌گذاران خارجی (سرمایه‌گذاری مستقیم)", shares: 890000000, percentage: 5.6, monthlyChange: -0.5 },
  { rank: 6, name: "صندوق سرمایه‌گذاری بازارگردانی فولاد", shares: 750000000, percentage: 4.7, monthlyChange: 1.2 },
  { rank: 7, name: "شرکت سرمایه‌گذاری صندوق بازنشستگی", shares: 620000000, percentage: 3.9, monthlyChange: 0.0 },
  { rank: 8, name: "شرکت بیمه مرکزی ایران", shares: 510000000, percentage: 3.2, monthlyChange: -0.1 },
  { rank: 9, name: "صندوق سرمایه‌گذاری مشترک توسعه", shares: 430000000, percentage: 2.7, monthlyChange: 0.3 },
  { rank: 10, name: "سهامداران حقیقی (پراکنده)", shares: 4120000000, percentage: 25.8, monthlyChange: -1.3 },
];

const FALLBACK_INSIDER_TRADES: InsiderTrade[] = [
  { date: "۱۴۰۴/۰۳/۱۵", type: "buy", count: 120000, price: 34200 },
  { date: "۱۴۰۴/۰۳/۱۰", type: "sell", count: 85000, price: 35100 },
  { date: "۱۴۰۴/۰۲/۲۸", type: "buy", count: 200000, price: 33800 },
  { date: "۱۴۰۴/۰۲/۲۰", type: "buy", count: 95000, price: 32500 },
  { date: "۱۴۰۴/۰۲/۱۲", type: "sell", count: 150000, price: 34800 },
  { date: "۱۴۰۴/۰۲/۰۵", type: "sell", count: 62000, price: 35500 },
  { date: "۱۴۰۴/۰۱/۲۸", type: "buy", count: 180000, price: 31500 },
  { date: "۱۴۰۴/۰۱/۲۰", type: "buy", count: 85000, price: 30800 },
];

function formatShares(n: number): string {
  if (n >= 1000000000) return (n / 1000000000).toFixed(2) + " میلیارد";
  if (n >= 1000000) return (n / 1000000).toFixed(1) + " میلیون";
  if (n >= 1000) return (n / 1000).toFixed(1) + " هزار";
  return n.toLocaleString("fa-IR");
}

function formatPrice(n: number): string {
  return n.toLocaleString("fa-IR");
}

export default function HoldersPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [symbol, setSymbol] = useState("فولاد");
  const [searchSymbol, setSearchSymbol] = useState("فولاد");
  const [holders, setHolders] = useState<MajorHolder[]>(FALLBACK_HOLDERS);
  const [insiderTrades, setInsiderTrades] = useState<InsiderTrade[]>(FALLBACK_INSIDER_TRADES);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const fetchHolders = async (sym: string) => {
    if (!sym.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const [holdersRes, insiderRes] = await Promise.all([
        fetch(`/api/v1/codal/${sym}/holders`),
        fetch(`/api/v1/codal/${sym}/insider`),
      ]);

      let holdersData: MajorHolder[] | null = null;
      let insiderData: InsiderTrade[] | null = null;

      if (holdersRes.ok) {
        const d = await holdersRes.json();
        if (d.success && d.data) holdersData = d.data;
      }
      if (insiderRes.ok) {
        const d = await insiderRes.json();
        if (d.success && d.data) insiderData = d.data;
      }

      if (holdersData) setHolders(holdersData);
      if (insiderData) setInsiderTrades(insiderData);
      if (holdersData || insiderData) {
        setLastUpdate(new Date().toLocaleString("fa-IR"));
      } else {
        setHolders(FALLBACK_HOLDERS);
        setInsiderTrades(FALLBACK_INSIDER_TRADES);
        setLastUpdate("داده‌های نمونه");
      }
    } catch {
      setHolders(FALLBACK_HOLDERS);
      setInsiderTrades(FALLBACK_INSIDER_TRADES);
      setLastUpdate("داده‌های نمونه");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHolders(symbol);
    const interval = setInterval(() => fetchHolders(symbol), 120000);
    return () => clearInterval(interval);
  }, [symbol]);

  const handleSearch = () => {
    if (searchSymbol.trim()) {
      setSymbol(searchSymbol.trim());
      setShowSuggestions(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const filteredSymbols = searchSymbol.trim()
    ? IRANIAN_SYMBOLS.filter((s) => s.code.includes(searchSymbol) || s.name.includes(searchSymbol))
    : IRANIAN_SYMBOLS;

  return (
    <div className="flex h-screen overflow-hidden" dir="rtl">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#0a0a14]">
        <div className="flex flex-wrap items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-surface-100">سهامداران عمده و معاملات داخلی</h1>
            <p className="text-sm text-surface-500 mt-1">اطلاعات سهامداران عمده و معاملات داخلی شرکت‌ها</p>
            {lastUpdate && <p className="text-xs text-surface-600 mt-1">آخرین به‌روزرسانی: {lastUpdate}</p>}
          </div>
          <div className="flex items-center gap-2 mt-3 sm:mt-0 relative">
            <div className="relative">
              <input
                type="text"
                value={searchSymbol}
                onChange={(e) => { setSearchSymbol(e.target.value); setShowSuggestions(true); }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                onKeyDown={handleKeyDown}
                placeholder="جستجوی نماد..."
                className="px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500 w-40"
              />
              {showSuggestions && searchSymbol.trim() && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-surface-800 border border-surface-700 rounded-lg shadow-xl z-10 max-h-48 overflow-y-auto">
                  {filteredSymbols.map((s) => (
                    <button key={s.code} onClick={() => { setSearchSymbol(s.code); setSymbol(s.code); setShowSuggestions(false); }}
                      className="w-full text-right px-3 py-2 text-sm text-surface-200 hover:bg-surface-700 transition-colors">
                      <span className="font-mono font-bold">{s.code}</span>
                      <span className="text-surface-500 text-xs mr-2">{s.name}</span>
                    </button>
                  ))}
                  {filteredSymbols.length === 0 && (
                    <div className="px-3 py-2 text-sm text-surface-500">نمادی یافت نشد</div>
                  )}
                </div>
              )}
            </div>
            <button onClick={handleSearch}
              className="px-3 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded text-sm transition-colors">جستجو</button>
            {isLoading && <span className="w-2 h-2 rounded-full bg-accent-amber animate-pulse" />}
          </div>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg mb-4 text-sm">خطا: {error}</div>
        )}

        <div className="glass-card p-5 mb-6">
          <h2 className="font-bold text-surface-200 mb-4">
            سهامداران عمده — <span className="font-mono text-primary-300">{symbol}</span>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 font-medium">رتبه</th>
                  <th className="pb-2 font-medium">نام سهامدار</th>
                  <th className="pb-2 font-medium">تعداد سهام</th>
                  <th className="pb-2 font-medium">درصد مالکیت</th>
                  <th className="pb-2 font-medium">تغییر ماه</th>
                </tr>
              </thead>
              <tbody>
                {holders.map((h) => (
                  <tr key={h.rank} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 font-mono text-surface-400">{h.rank}</td>
                    <td className="py-2.5 text-surface-200 text-xs">{h.name}</td>
                    <td className="py-2.5 font-mono text-surface-200">{formatShares(h.shares)}</td>
                    <td className="py-2.5 font-mono text-accent-cyan">{h.percentage.toFixed(1)}%</td>
                    <td className="py-2.5">
                      <span className={`font-mono text-xs ${
                        h.monthlyChange > 0 ? "text-accent-emerald" : h.monthlyChange < 0 ? "text-accent-rose" : "text-surface-400"
                      }`}>
                        {h.monthlyChange > 0 ? "+" : ""}{h.monthlyChange.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="glass-card p-5">
          <h2 className="font-bold text-surface-200 mb-4">
            معاملات داخلی اخیر — <span className="font-mono text-primary-300">{symbol}</span>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="text-surface-500 border-b border-surface-700">
                  <th className="pb-2 font-medium">تاریخ</th>
                  <th className="pb-2 font-medium">نوع معامله</th>
                  <th className="pb-2 font-medium">تعداد</th>
                  <th className="pb-2 font-medium">قیمت</th>
                </tr>
              </thead>
              <tbody>
                {insiderTrades.map((t, i) => (
                  <tr key={i} className="border-b border-surface-800/50 hover:bg-white/5">
                    <td className="py-2.5 text-surface-400 text-xs">{t.date}</td>
                    <td className="py-2.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        t.type === "buy" ? "bg-accent-emerald/15 text-accent-emerald" : "bg-accent-rose/15 text-accent-rose"
                      }`}>{t.type === "buy" ? "خرید" : "فروش"}</span>
                    </td>
                    <td className="py-2.5 font-mono text-surface-200">{formatShares(t.count)}</td>
                    <td className="py-2.5 font-mono text-surface-200">{formatPrice(t.price)}</td>
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
