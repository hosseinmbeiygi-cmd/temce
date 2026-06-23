"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import MarketIndices from "./MarketIndices";
import NavTabs from "./NavTabs";
import { useTheme } from "@/hooks/useTheme";

interface AppLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
}

export default function AppLayout({ children, title, subtitle }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const { toggleTheme, isDark } = useTheme();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />

      <main className="flex-1 overflow-y-auto">
        <div className="container">
          {/* Header */}
          <div className="header">
            <div className="logo">
              <span className="material-icons">trending_up</span>
              {!collapsed && "داشبورد بازار سرمایه ایران"}
            </div>
            <div className="header-actions">
              <div className="theme-toggle" onClick={toggleTheme}>
                <span className="material-icons">{isDark ? "light_mode" : "dark_mode"}</span>
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <NavTabs />

          {/* Market Indices Bar */}
          <MarketIndices />

          {/* Page Content */}
          <div className="dashboard-content">
            {title && (
              <div className="mb-4">
                <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary-light)" }}>{title}</h1>
                {subtitle && <p className="text-sm" style={{ color: "var(--text-secondary-light)" }}>{subtitle}</p>}
              </div>
            )}
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
