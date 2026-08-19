"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Bell, Bot, CandlestickChart, Search } from "lucide-react";

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

const NAV_ITEMS = [
  { href: "/", label: "داشبورد", icon: "📊" },
  { href: "/smart-screener", label: "غربالگر هوشمند", icon: "🤖" },
  { href: "/markets", label: "بازارها", icon: "📈" },
  { href: "/instruments", label: "نمادها", icon: "💹" },
  { href: "/options", label: "آپشن", icon: "🎯" },
  { href: "/funds", label: "صندوق‌ها", icon: "🏦" },
  { href: "/quotes", label: "قیمت‌ها", icon: "💵" },
  { href: "/codal", label: "کدال", icon: "🏢" },
  { href: "/news", label: "اخبار", icon: "📰" },

  { href: "/analysis", label: "تحلیل بازار", icon: "🔍" },
  { href: "/screener", label: "غربالگر", icon: "🎯" },
  { href: "/heatmap", label: "نقشه بازار", icon: "🗺️" },
  { href: "/alerts", label: "اطلاعیه‌ها", icon: "🔔" },
  { href: "/macro", label: "داده‌های کلان", icon: "🏛️" },
  { href: "/watchlist", label: "دیده‌بان", icon: "👁️" },
  { href: "/market-watch", label: "دیدبان بازار", icon: "📋" },
  { href: "/alpha", label: "آلفا", icon: "⚡" },
  { href: "/backtest", label: "بک‌تست", icon: "🧪", children: [
    { href: "/backtest/full-scan", label: "اسکن کامل", icon: "🔬" },
    { href: "/backtest/generate", label: "تولید خودکار", icon: "🚀" },
    { href: "/backtest/compose", label: "ترکیب استراتژی", icon: "🔧" },
    { href: "/backtest/walk-forward", label: "Walk-Forward", icon: "📊" },
    { href: "/backtest/monte-carlo", label: "Monte Carlo", icon: "🎲" },
  ]},
  { href: "/signals", label: "سیگنال‌ها", icon: "📡" },
  { href: "/signals/dashboard", label: "🎯 سیگنال‌یاب چندبازاره", icon: "🌐" },
  { href: "/paper-trading", label: "📒 معاملات آزمایشی", icon: "📒" },
  { href: "/risk", label: "ریسک", icon: "🛡️" },
  { href: "/ml", label: "یادگیری ماشین", icon: "🧠" },
  { href: "/admin", label: "پنل مدیریت", icon: "🛡️" },
  { href: "/crypto-market", label: "بازار رمز ارز", icon: "🪙" },
  { href: "/crypto-exchange", label: "صرافی ارز دیجیتال", icon: "🔄" },
  { href: "/tabdeal-api", label: "API تبدیل", icon: "🔑" },
];

export default function Sidebar({ collapsed = false, onToggle = () => {} }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [symbolQuery, setSymbolQuery] = useState("");

  function handleSymbolSearch(e: FormEvent) {
    e.preventDefault();
    if (symbolQuery.trim()) {
      router.push(`/symbol/${encodeURIComponent(symbolQuery.trim())}`);
    }
  }

  return (
    <aside
      className={`${
        collapsed ? "w-16" : "w-56"
      } transition-all duration-300 bg-surface-900/80 border-l border-surface-800 flex flex-col shrink-0`}
    >
      <div className="h-14 flex items-center justify-center gap-2 border-b border-surface-800 px-3">
        {collapsed ? (
          <CandlestickChart className="size-5 text-primary-300" aria-hidden />
        ) : (
          <>
            <CandlestickChart className="size-5 text-primary-300" aria-hidden />
            <span className="font-bold text-sm text-white">بازار سرمایه</span>
          </>
        )}
      </div>

      {!collapsed && (
        <form onSubmit={handleSymbolSearch} className="px-2 py-2 border-b border-surface-800">
          <div className="flex items-center gap-2 bg-surface-800 rounded-lg px-2.5 py-2">
            <Search className="size-3.5 text-surface-500 shrink-0" aria-hidden />
            <input
              type="text"
              value={symbolQuery}
              onChange={(e) => setSymbolQuery(e.target.value)}
              placeholder="جستجوی نماد..."
              className="bg-transparent text-sm text-white placeholder-surface-500 outline-none flex-1 min-w-0"
            />
            {symbolQuery && (
              <button type="submit" className="text-xs text-primary-400 hover:text-primary-300 shrink-0">→</button>
            )}
          </div>
        </form>
      )}

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const hasChildren = item.children && item.children.length > 0;
          return (
            <div key={item.href}>
              <Link
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                  active
                    ? "bg-primary-600/20 text-primary-300 border border-primary-600/20"
                    : "text-surface-400 hover:text-surface-200 hover:bg-white/5"
                }`}
              >
                <span className="text-lg shrink-0">{item.icon}</span>
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
              {hasChildren && (active || pathname.startsWith(item.href + "/")) && !collapsed && (
                <div className="ml-8 mt-1 space-y-0.5">
                  {item.children!.map((child) => {
                    const childActive = pathname === child.href;
                    return (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                          childActive
                            ? "bg-primary-600/20 text-primary-300"
                            : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
                        }`}
                      >
                        <span>{child.icon}</span>
                        <span>{child.label}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="border-t border-surface-800 py-2 px-2 space-y-1">
        <Link
          href="/signals"
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-surface-400 hover:text-surface-200 hover:bg-white/5 transition-all"
        >
          <Bot className="size-4 shrink-0" aria-hidden />
          {!collapsed && <span className="truncate">دستیار هوشمند</span>}
        </Link>
        <Link
          href="/alerts"
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-surface-400 hover:text-surface-200 hover:bg-white/5 transition-all"
        >
          <Bell className="size-4 shrink-0" aria-hidden />
          {!collapsed && <span className="truncate">هشدارها</span>}
        </Link>
      </div>

      <button
        onClick={onToggle}
        className="h-10 flex items-center justify-center border-t border-surface-800 text-surface-500 hover:text-surface-300 transition-colors"
        aria-label={collapsed ? "باز کردن منو" : "جمع کردن منو"}
      >
        {collapsed ? "←" : "→"}
      </button>
    </aside>
  );
}
