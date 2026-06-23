"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

interface NavTabsProps {
  onNavigate?: (page: string) => void;
  currentPage?: string;
}

const TABS = [
  { id: "dashboard", label: "داشبورد", icon: "dashboard", href: "/" },
  { id: "heatmap", label: "نقشه حرارتی", icon: "grid_view", href: "/heatmap" },
  { id: "portfolio", label: "پرتفوی", icon: "account_balance_wallet", href: "/portfolio" },
  { id: "market-depth", label: "عمق بازار", icon: "bar_chart", href: "/market-depth" },
  { id: "news", label: "اخبار و نظرات", icon: "article", href: "/news" },
  { id: "analysis", label: "تحلیل و پیش‌بینی", icon: "analytics", href: "/analysis" },
  { id: "watchlist", label: "علاقه‌مندی‌ها", icon: "star", href: "/watchlist" },
  { id: "smart-money", label: "پول هوشمند", icon: "psychology", href: "/smart-money" },
  { id: "signals", label: "سیگنال‌ها", icon: "trending_up", href: "/signals" },
  { id: "backtest", label: "بک‌تست", icon: "science", href: "/backtest" },
  { id: "settings", label: "تنظیمات", icon: "settings", href: "/settings" },
];

export default function NavTabs({ onNavigate, currentPage }: NavTabsProps) {
  const pathname = usePathname();

  return (
    <div className="nav-tabs">
      {TABS.map((tab) => {
        const isActive = pathname === tab.href || currentPage === tab.id;
        return (
          <Link
            key={tab.id}
            href={tab.href}
            className={`nav-tab ${isActive ? "active" : ""}`}
            onClick={() => onNavigate?.(tab.id)}
          >
            <span className="material-icons text-lg">{tab.icon}</span>
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
