"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import TopNavbar from "./TopNavbar";
import TickerBar from "./TickerBar";
import Sidebar from "@/components/Sidebar";

export default function DashboardShell({ children, sidebar = true }: { children: ReactNode; sidebar?: boolean }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="dash-field min-h-screen bg-canvas text-ink transition-colors duration-300">
      <TopNavbar
        sidebarCollapsed={sidebarCollapsed}
        onSidebarToggle={() => setSidebarCollapsed((c) => !c)}
      />
      {/* TopNavbar is fixed; reserve its 56px so ticker/content dont slide under */}
      <div className="h-14 shrink-0" aria-hidden="true" />
      <div className="flex">
        {sidebar && (
          <Sidebar
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed((c) => !c)}
          />
        )}
        <div className="flex-1 min-w-0">
          <TickerBar />
          <main className="relative z-10 mx-auto max-w-[1600px] px-3 pb-20 pt-8 lg:px-5">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}