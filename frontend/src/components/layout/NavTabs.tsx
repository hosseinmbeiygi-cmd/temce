"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavTabsProps {
  onNavigate?: (page: string) => void;
  currentPage?: string;
}

const TABS = [
  { id: "dashboard", label: "داشبورد", icon: "dashboard", href: "/" },
  { id: "heatmap", label: "نقشه حرارتی", icon: "grid_view", href: "/heatmap" },
  { id: "portfolio", label: "پرتفوی", icon: "account_balance_wallet", href: "/portfolio" },
  { id: "commodities", label: "کامودیتی", icon: "travel_explore", href: "/commodities" },
  { id: "crypto", label: "ارز دیجیتال", icon: "account_balance", href: "/crypto" },
  { id: "market-depth", label: "عمق بازار", icon: "bar_chart", href: "/market-depth" },
  { id: "news", label: "اخبار و نظرات", icon: "article", href: "/news" },
  { id: "analysis", label: "تحلیل و پیش‌بینی", icon: "analytics", href: "/analysis" },
  { id: "watchlist", label: "علاقه‌مندی‌ها", icon: "star", href: "/watchlist" },
  { id: "smart-money", label: "پول هوشمند", icon: "psychology", href: "/smart-money" },
  { id: "signals", label: "سیگنال‌ها", icon: "trending_up", href: "/signals" },
  { id: "backtest", label: "بک‌تست", icon: "science", href: "/backtest", children: [
    { id: "backtest-methods", label: "چارچوب بک‌تست", icon: "menu_book", href: "/backtest/methods" },
    { id: "backtest-decision", label: "مرکز تصمیم", icon: "hub", href: "/backtest/decision" },
    { id: "backtest-adaptive", label: "سیستم انطباقی", icon: "psychology", href: "/backtest/adaptive" },
    { id: "backtest-cascade", label: "موتور کاسکاد", icon: "waterfall", href: "/backtest/cascade" },
    { id: "backtest-engine", label: "موتور استراتژی", icon: "memory", href: "/backtest/engine" },
    { id: "backtest-generate", label: "تولید خودکار", icon: "rocket_launch", href: "/backtest/generate" },
    { id: "backtest-compose", label: "ترکیب استراتژی", icon: "biotech", href: "/backtest/compose" },
    { id: "backtest-walk-forward", label: "Walk-Forward", icon: "compare_arrows", href: "/backtest/walk-forward" },
    { id: "backtest-monte-carlo", label: "Monte Carlo", icon: "casino", href: "/backtest/monte-carlo" },
  ]},
  { id: "risk", label: "ریسک", icon: "shield", href: "/risk" },
  { id: "alpha", label: "آلفا", icon: "auto_awesome", href: "/alpha" },
  { id: "fundamental", label: "بنیادی", icon: "account_balance", href: "/fundamental" },
  { id: "results", label: "نتایج", icon: "assignment", href: "/results" },
  { id: "data", label: "مدیریت API", icon: "storage", href: "/data" },
  { id: "settings", label: "تنظیمات", icon: "settings", href: "/settings" },
];

export default function NavTabs({ onNavigate, currentPage }: NavTabsProps) {
  const pathname = usePathname();

  return (
    <div className="nav-tabs">
      {TABS.map((tab) => {
        const isActive = pathname === tab.href || currentPage === tab.id;
        const hasChildren = tab.children && tab.children.length > 0;
        return (
          <div key={tab.id}>
            <Link
              href={tab.href}
              className={`nav-tab ${isActive ? "active" : ""}`}
              onClick={() => onNavigate?.(tab.id)}
            >
              <span className="material-icons text-lg">{tab.icon}</span>
              {tab.label}
            </Link>
            {hasChildren && isActive && (
              <div className="ml-6 mt-1 space-y-0.5">
                {tab.children!.map((child) => {
                  const childActive = pathname === child.href;
                  return (
                    <Link
                      key={child.id}
                      href={child.href}
                      className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                        childActive
                          ? "bg-primary-600/20 text-primary-300"
                          : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
                      }`}
                    >
                      <span className="material-icons text-sm">{child.icon}</span>
                      {child.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
