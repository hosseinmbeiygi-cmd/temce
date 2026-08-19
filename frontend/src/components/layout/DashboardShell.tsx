"use client";

import type { ReactNode } from "react";
import TopNavbar from "./TopNavbar";
import TickerBar from "./TickerBar";
import SmartScreenerFab from "./SmartScreenerFab";

export default function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <div className="dash-field min-h-screen bg-canvas text-ink transition-colors duration-300">
      <TopNavbar />
      <TickerBar />
      <main className="relative z-10 mx-auto max-w-[1600px] px-3 pb-20 pt-6 lg:px-5">
        {children}
      </main>
      <SmartScreenerFab />
    </div>
  );
}
